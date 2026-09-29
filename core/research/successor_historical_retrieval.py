from dataclasses import dataclass
from typing import Protocol

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.market_data.historical_coverage import (
    TimeRange,
    find_missing_ranges,
)
from core.market_data.historical_retrieval import (
    HistoricalFetchResult,
    IncompleteHistoricalCoverageError,
    validate_historical_fetch_result,
)
from core.market_data.instrument_registry import (
    StaticInstrumentRegistry,
)
from core.market_data.provider_instrument_binding import (
    ProviderInstrumentBinding,
)
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.research.models.dataset import (
    DatasetAcquisitionStreamIdentity,
    PriceAdjustmentBasis,
    ProviderBindingProvenance,
)
from core.runtime.dataset_context import DatasetContext


class BindingAwareHistoricalProvider(Protocol):
    def fetch(
        self,
        context: DatasetContext,
        request: TimeRange,
        *,
        provider_binding: ProviderInstrumentBinding,
    ) -> HistoricalFetchResult:
        ...


@dataclass(frozen=True)
class AcquisitionStreamUsage:
    """
    Physical acquisition stream used for one resolved binding segment.
    """

    identity: DatasetAcquisitionStreamIdentity
    applied_range: TimeRange
    fetched_ranges: tuple[TimeRange, ...]


@dataclass(frozen=True)
class SuccessorHistoricalRetrievalResult:
    """
    Exact candles plus evidence needed for successor dataset provenance.
    """

    candles: tuple[Candle, ...]
    source: str
    binding_segments: tuple[
        ProviderBindingProvenance,
        ...,
    ]
    coverage: tuple[TimeRange, ...]
    stream_usages: tuple[
        AcquisitionStreamUsage,
        ...,
    ]


def _require_context_value(
    value: str | None,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"{field_name} must be a non-empty string"
        )

    return value


def _request_has_cached_coverage(
    request: TimeRange,
    missing_ranges: list[TimeRange],
) -> bool:
    if not missing_ranges:
        return True

    return not (
        len(missing_ranges) == 1
        and missing_ranges[0] == request
    )


def _source_label(
    *,
    provider: str,
    used_cache: bool,
    used_provider: bool,
) -> str:
    if used_cache and used_provider:
        return (
            "mixed:"
            "acquisition_stream_cache+"
            f"provider:{provider}"
        )

    if used_provider:
        return f"provider:{provider}"

    return "acquisition_stream_cache"


class SuccessorHistoricalRetrievalService:
    """
    Retrieve one canonical request across one or more provider bindings.

    Every provider binding uses a physically distinct acquisition stream.
    The legacy V1 candle cache is intentionally not consulted.
    """

    def __init__(
        self,
        *,
        store: SQLiteCandleStore,
        provider: BindingAwareHistoricalProvider,
        registry: StaticInstrumentRegistry,
    ):
        self.store = store
        self.provider = provider
        self.registry = registry

    def retrieve(
        self,
        context: DatasetContext,
        request: TimeRange,
        *,
        instrument_id: str,
        provider: str,
        price_adjustment_basis: PriceAdjustmentBasis,
    ) -> SuccessorHistoricalRetrievalResult:
        symbol = _require_context_value(
            context.symbol,
            "context.symbol",
        )

        timeframe = _require_context_value(
            context.timeframe,
            "context.timeframe",
        )

        timezone = _require_context_value(
            context.timezone,
            "context.timezone",
        )

        if not isinstance(
            price_adjustment_basis,
            PriceAdjustmentBasis,
        ):
            raise TypeError(
                "price_adjustment_basis must be "
                "a PriceAdjustmentBasis"
            )

        retrieval_context = DatasetContext(
            symbol=symbol,
            timeframe=timeframe,
            timezone=timezone,
        )

        resolved_bindings = self.registry.resolve_bindings(
            instrument_id=instrument_id,
            provider=provider,
            request=request,
        )

        combined_candles: list[Candle] = []
        binding_segments: list[
            ProviderBindingProvenance
        ] = []
        coverage: list[TimeRange] = []
        stream_usages: list[
            AcquisitionStreamUsage
        ] = []

        used_cache = False
        used_provider = False

        for resolved in resolved_bindings:
            binding = resolved.binding
            applied_range = resolved.applied_range

            stream_identity = (
                DatasetAcquisitionStreamIdentity(
                    instrument_id=instrument_id,
                    provider=binding.provider,
                    binding_id=binding.binding_id,
                    timeframe=timeframe,
                    timezone=timezone,
                    price_adjustment_basis=(
                        price_adjustment_basis
                    ),
                )
            )

            existing_coverage = (
                self.store
                .load_acquisition_stream_coverage(
                    stream_identity.stream_id
                )
            )

            missing_ranges = find_missing_ranges(
                applied_range,
                existing_coverage,
            )

            if _request_has_cached_coverage(
                applied_range,
                missing_ranges,
            ):
                used_cache = True

            fetched_ranges: list[TimeRange] = []

            for missing_range in missing_ranges:
                used_provider = True

                result = self.provider.fetch(
                    retrieval_context,
                    missing_range,
                    provider_binding=binding,
                )

                validate_historical_fetch_result(
                    missing_range,
                    result,
                )

                self.store.save_acquisition_stream_retrieval(
                    stream_identity.stream_id,
                    list(result.candles),
                    list(result.coverage),
                )

                fetched_ranges.append(
                    missing_range
                )

            remaining = find_missing_ranges(
                applied_range,
                self.store.load_acquisition_stream_coverage(
                    stream_identity.stream_id
                ),
            )

            if remaining:
                raise IncompleteHistoricalCoverageError(
                    remaining
                )

            inclusive_candles = (
                self.store.load_acquisition_stream(
                    stream_identity.stream_id,
                    start=applied_range.start,
                    end=applied_range.end,
                )
            )

            segment_candles = [
                candle
                for candle in inclusive_candles
                if candle.timestamp < applied_range.end
            ]

            CandleSeries(segment_candles)

            combined_candles.extend(
                segment_candles
            )

            binding_segments.append(
                ProviderBindingProvenance(
                    binding_id=binding.binding_id,
                    provider=binding.provider,
                    applied_range=applied_range,
                )
            )

            coverage.append(
                applied_range
            )

            stream_usages.append(
                AcquisitionStreamUsage(
                    identity=stream_identity,
                    applied_range=applied_range,
                    fetched_ranges=tuple(
                        fetched_ranges
                    ),
                )
            )

        CandleSeries(combined_candles)

        return SuccessorHistoricalRetrievalResult(
            candles=tuple(combined_candles),
            source=_source_label(
                provider=provider,
                used_cache=used_cache,
                used_provider=used_provider,
            ),
            binding_segments=tuple(
                binding_segments
            ),
            coverage=tuple(coverage),
            stream_usages=tuple(
                stream_usages
            ),
        )

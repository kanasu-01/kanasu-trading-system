"""Versioned successor dataset identity and provenance contracts."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import re

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.market_data.historical_coverage import (
    TimeRange,
    find_missing_ranges,
)
from core.research.reproducibility import canonical_fingerprint


DATASET_V2_SCHEMA_ID = "kanasu.dataset.v2"
DATASET_ACQUISITION_STREAM_SCHEMA_ID = (
    "kanasu.dataset-acquisition-stream.v1"
)

_SHA256_FINGERPRINT_PATTERN = re.compile(
    r"^sha256:[0-9a-f]{64}$"
)


class PriceAdjustmentBasis(str, Enum):
    """Declared price/corporate-action treatment."""

    RAW = "RAW"
    ADJUSTED = "ADJUSTED"
    UNKNOWN = "UNKNOWN"


class DatasetCoverageStatus(str, Enum):
    """Coverage claim derived only from explicit coverage evidence."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


def _require_nonempty_string(
    value: str,
    field_name: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"{field_name} must be a non-empty string"
        )


def _require_sha256_fingerprint(
    value: str,
    field_name: str,
) -> None:
    if (
        not isinstance(value, str)
        or not _SHA256_FINGERPRINT_PATTERN.fullmatch(value)
    ):
        raise ValueError(
            f"{field_name} must use "
            "sha256:<64 lowercase hexadecimal>"
        )


def _require_time_range(
    value: TimeRange,
    field_name: str,
) -> None:
    if not isinstance(value, TimeRange):
        raise TypeError(
            f"{field_name} must be a TimeRange"
        )


def _require_optional_aware_datetime(
    value: datetime | None,
    field_name: str,
) -> None:
    if value is None:
        return

    if not isinstance(value, datetime):
        raise TypeError(
            f"{field_name} must be a datetime or None"
        )

    if value.utcoffset() is None:
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )


def _same_awareness(
    left: datetime,
    right: datetime,
) -> bool:
    return (
        left.utcoffset() is not None
    ) == (
        right.utcoffset() is not None
    )


def _validate_range_against_request(
    request: TimeRange,
    value: TimeRange,
    field_name: str,
) -> None:
    if not _same_awareness(
        request.start,
        value.start,
    ):
        raise ValueError(
            f"{field_name} timezone awareness must "
            "match requested_range"
        )

    if (
        value.start < request.start
        or value.end > request.end
    ):
        raise ValueError(
            f"{field_name} must be contained within "
            "requested_range"
        )


def _range_payload(
    value: TimeRange,
) -> dict[str, datetime]:
    return {
        "start": value.start,
        "end": value.end,
    }


def _candle_payload(
    candle: Candle,
) -> dict:
    return {
        "timestamp": candle.timestamp,
        "open": candle.open,
        "high": candle.high,
        "low": candle.low,
        "close": candle.close,
        "volume": candle.volume,
    }


@dataclass(frozen=True)
class DatasetIdentityV2:
    """
    Canonical identity of one exact successor dataset.

    Provider/source/retrieval details deliberately do not participate.
    """

    instrument_id: str
    requested_range: TimeRange
    timeframe: str
    timezone: str
    price_adjustment_basis: PriceAdjustmentBasis
    candles: tuple[Candle, ...] | list[Candle]
    dataset_id: str = field(init=False)

    def __post_init__(self) -> None:
        _require_nonempty_string(
            self.instrument_id,
            "instrument_id",
        )
        _require_time_range(
            self.requested_range,
            "requested_range",
        )
        _require_nonempty_string(
            self.timeframe,
            "timeframe",
        )
        _require_nonempty_string(
            self.timezone,
            "timezone",
        )

        if not isinstance(
            self.price_adjustment_basis,
            PriceAdjustmentBasis,
        ):
            raise TypeError(
                "price_adjustment_basis must be "
                "a PriceAdjustmentBasis"
            )

        if not isinstance(
            self.candles,
            (list, tuple),
        ):
            raise TypeError(
                "candles must be a list or tuple"
            )

        normalized_candles = tuple(self.candles)

        if any(
            not isinstance(candle, Candle)
            for candle in normalized_candles
        ):
            raise TypeError(
                "dataset identity requires Candle values"
            )

        CandleSeries(list(normalized_candles))

        request_aware = (
            self.requested_range.start.utcoffset()
            is not None
        )

        for candle in normalized_candles:
            candle_aware = (
                candle.timestamp.utcoffset()
                is not None
            )

            if candle_aware != request_aware:
                raise ValueError(
                    "request and candle timestamp timezone "
                    "awareness must match"
                )

            if not (
                self.requested_range.start
                <= candle.timestamp
                < self.requested_range.end
            ):
                raise ValueError(
                    "dataset candle must be inside the "
                    "half-open requested_range"
                )

        object.__setattr__(
            self,
            "candles",
            normalized_candles,
        )

        dataset_id = canonical_fingerprint(
            {
                "instrument_id": self.instrument_id,
                "requested_range": _range_payload(
                    self.requested_range
                ),
                "timeframe": self.timeframe,
                "timezone": self.timezone,
                "price_adjustment_basis": (
                    self.price_adjustment_basis.value
                ),
                "candles": [
                    _candle_payload(candle)
                    for candle in normalized_candles
                ],
            },
            schema=DATASET_V2_SCHEMA_ID,
        )

        object.__setattr__(
            self,
            "dataset_id",
            dataset_id,
        )


@dataclass(frozen=True)
class ProviderBindingProvenance:
    """One exact provider binding used over one applied subrange."""

    binding_id: str
    provider: str
    applied_range: TimeRange

    def __post_init__(self) -> None:
        _require_nonempty_string(
            self.binding_id,
            "binding_id",
        )
        _require_nonempty_string(
            self.provider,
            "provider",
        )
        _require_time_range(
            self.applied_range,
            "applied_range",
        )


@dataclass(frozen=True)
class DatasetProvenance:
    """
    Inspectable acquisition evidence kept outside canonical dataset identity.
    """

    dataset_id: str
    instrument_id: str
    requested_range: TimeRange
    timeframe: str
    timezone: str
    price_adjustment_basis: PriceAdjustmentBasis
    source: str
    binding_segments: (
        tuple[ProviderBindingProvenance, ...]
        | list[ProviderBindingProvenance]
    ) = ()
    coverage: (
        tuple[TimeRange, ...]
        | list[TimeRange]
    ) = ()
    retrieved_at: datetime | None = None
    as_of: datetime | None = None
    limitations: (
        tuple[str, ...]
        | list[str]
    ) = ()

    def __post_init__(self) -> None:
        _require_sha256_fingerprint(
            self.dataset_id,
            "dataset_id",
        )
        _require_nonempty_string(
            self.instrument_id,
            "instrument_id",
        )
        _require_time_range(
            self.requested_range,
            "requested_range",
        )
        _require_nonempty_string(
            self.timeframe,
            "timeframe",
        )
        _require_nonempty_string(
            self.timezone,
            "timezone",
        )
        _require_nonempty_string(
            self.source,
            "source",
        )

        if not isinstance(
            self.price_adjustment_basis,
            PriceAdjustmentBasis,
        ):
            raise TypeError(
                "price_adjustment_basis must be "
                "a PriceAdjustmentBasis"
            )

        if not isinstance(
            self.binding_segments,
            (list, tuple),
        ):
            raise TypeError(
                "binding_segments must be a list or tuple"
            )

        normalized_segments = tuple(
            self.binding_segments
        )

        if any(
            not isinstance(
                segment,
                ProviderBindingProvenance,
            )
            for segment in normalized_segments
        ):
            raise TypeError(
                "binding_segments must contain "
                "ProviderBindingProvenance values"
            )

        for segment in normalized_segments:
            _validate_range_against_request(
                self.requested_range,
                segment.applied_range,
                "binding applied_range",
            )

        normalized_segments = tuple(
            sorted(
                normalized_segments,
                key=lambda segment: (
                    segment.applied_range.start,
                    segment.applied_range.end,
                    segment.provider,
                    segment.binding_id,
                ),
            )
        )

        for previous, current in zip(
            normalized_segments,
            normalized_segments[1:],
        ):
            if (
                current.applied_range.start
                < previous.applied_range.end
            ):
                raise ValueError(
                    "provider binding provenance "
                    "segments must not overlap"
                )

        if not isinstance(
            self.coverage,
            (list, tuple),
        ):
            raise TypeError(
                "coverage must be a list or tuple"
            )

        normalized_coverage = tuple(
            self.coverage
        )

        if any(
            not isinstance(interval, TimeRange)
            for interval in normalized_coverage
        ):
            raise TypeError(
                "coverage must contain TimeRange values"
            )

        for interval in normalized_coverage:
            _validate_range_against_request(
                self.requested_range,
                interval,
                "coverage interval",
            )

        normalized_coverage = tuple(
            sorted(
                normalized_coverage,
                key=lambda interval: (
                    interval.start,
                    interval.end,
                ),
            )
        )

        _require_optional_aware_datetime(
            self.retrieved_at,
            "retrieved_at",
        )
        _require_optional_aware_datetime(
            self.as_of,
            "as_of",
        )

        if not isinstance(
            self.limitations,
            (list, tuple),
        ):
            raise TypeError(
                "limitations must be a list or tuple"
            )

        raw_limitations = tuple(
            self.limitations
        )

        for limitation in raw_limitations:
            _require_nonempty_string(
                limitation,
                "limitation",
            )

        if (
            len(set(raw_limitations))
            != len(raw_limitations)
        ):
            raise ValueError(
                "limitations contains duplicates"
            )

        normalized_limitations = tuple(
            sorted(raw_limitations)
        )

        object.__setattr__(
            self,
            "binding_segments",
            normalized_segments,
        )
        object.__setattr__(
            self,
            "coverage",
            normalized_coverage,
        )
        object.__setattr__(
            self,
            "limitations",
            normalized_limitations,
        )

    @property
    def coverage_status(
        self,
    ) -> DatasetCoverageStatus:
        if not self.coverage:
            return DatasetCoverageStatus.UNKNOWN

        missing = find_missing_ranges(
            self.requested_range,
            list(self.coverage),
        )

        if not missing:
            return DatasetCoverageStatus.COMPLETE

        return DatasetCoverageStatus.PARTIAL


@dataclass(frozen=True)
class DatasetAcquisitionStreamIdentity:
    """
    Physical acquisition-stream identity.

    Unlike canonical dataset identity, provider binding participates here
    so incompatible provider streams cannot be silently merged.
    """

    instrument_id: str
    provider: str
    binding_id: str
    timeframe: str
    timezone: str
    price_adjustment_basis: PriceAdjustmentBasis
    stream_id: str = field(init=False)

    def __post_init__(self) -> None:
        for field_name, value in (
            ("instrument_id", self.instrument_id),
            ("provider", self.provider),
            ("binding_id", self.binding_id),
            ("timeframe", self.timeframe),
            ("timezone", self.timezone),
        ):
            _require_nonempty_string(
                value,
                field_name,
            )

        if not isinstance(
            self.price_adjustment_basis,
            PriceAdjustmentBasis,
        ):
            raise TypeError(
                "price_adjustment_basis must be "
                "a PriceAdjustmentBasis"
            )

        stream_id = canonical_fingerprint(
            {
                "instrument_id": self.instrument_id,
                "provider": self.provider,
                "binding_id": self.binding_id,
                "timeframe": self.timeframe,
                "timezone": self.timezone,
                "price_adjustment_basis": (
                    self.price_adjustment_basis.value
                ),
            },
            schema=(
                DATASET_ACQUISITION_STREAM_SCHEMA_ID
            ),
        )

        object.__setattr__(
            self,
            "stream_id",
            stream_id,
        )

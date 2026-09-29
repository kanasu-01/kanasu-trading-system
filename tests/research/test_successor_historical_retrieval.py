from datetime import datetime, timedelta

import pytest

from core.entities.candle import Candle
from core.entities.instrument import Instrument
from core.market_data.historical_coverage import (
    TimeRange,
    find_missing_ranges,
)
from core.market_data.historical_retrieval import (
    HistoricalFetchResult,
    IncompleteHistoricalCoverageError,
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
)
from core.research.successor_historical_retrieval import (
    SuccessorHistoricalRetrievalService,
)
from core.runtime.dataset_context import DatasetContext


START = datetime(2026, 1, 2, 9, 0)
MID = datetime(2026, 1, 2, 10, 0)
END = datetime(2026, 1, 2, 11, 0)

INSTRUMENT_ID = "NSE-EQ-ABC"

CONTEXT = DatasetContext(
    symbol="ABC",
    timeframe="15m",
    timezone="Asia/Kolkata",
)


def candle_at(
    timestamp: datetime,
    close: float,
) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1000.0,
    )


def binding(
    *,
    binding_id: str,
    token: str,
    start: datetime,
    end: datetime,
) -> ProviderInstrumentBinding:
    return ProviderInstrumentBinding(
        binding_id=binding_id,
        instrument_id=INSTRUMENT_ID,
        provider="angelone",
        provider_instrument_id=token,
        provider_exchange="NSE",
        provider_segment="EQ",
        provider_symbol="ABC",
        effective_from=start,
        effective_to=end,
    )


def registry_for(
    *bindings: ProviderInstrumentBinding,
) -> StaticInstrumentRegistry:
    return StaticInstrumentRegistry(
        instruments=(
            Instrument(
                instrument_id=INSTRUMENT_ID,
                symbol="ABC",
                exchange="NSE",
                segment="EQ",
                effective_from=START,
                effective_to=END,
            ),
        ),
        provider_bindings=tuple(bindings),
    )


def stream_identity(
    provider_binding: ProviderInstrumentBinding,
    *,
    basis: PriceAdjustmentBasis = (
        PriceAdjustmentBasis.UNKNOWN
    ),
) -> DatasetAcquisitionStreamIdentity:
    return DatasetAcquisitionStreamIdentity(
        instrument_id=INSTRUMENT_ID,
        provider=provider_binding.provider,
        binding_id=provider_binding.binding_id,
        timeframe="15m",
        timezone="Asia/Kolkata",
        price_adjustment_basis=basis,
    )


class RecordingProvider:
    def __init__(
        self,
        candles_by_binding=None,
    ):
        self.candles_by_binding = (
            candles_by_binding or {}
        )
        self.calls = []

    def fetch(
        self,
        context,
        request,
        *,
        provider_binding,
    ):
        self.calls.append(
            (
                provider_binding.binding_id,
                request,
            )
        )

        candidates = self.candles_by_binding.get(
            provider_binding.binding_id,
            (),
        )

        candles = tuple(
            candle
            for candle in candidates
            if (
                request.start
                <= candle.timestamp
                < request.end
            )
        )

        return HistoricalFetchResult(
            candles=candles,
            coverage=(request,),
        )


class PartialCoverageProvider(RecordingProvider):
    def fetch(
        self,
        context,
        request,
        *,
        provider_binding,
    ):
        self.calls.append(
            (
                provider_binding.binding_id,
                request,
            )
        )

        midpoint = (
            request.start
            + ((request.end - request.start) / 2)
        )

        return HistoricalFetchResult(
            candles=(),
            coverage=(
                TimeRange(
                    request.start,
                    midpoint,
                ),
            ),
        )


def service_for(
    tmp_path,
    *,
    provider,
    registry,
):
    store = SQLiteCandleStore(
        tmp_path / "candles.db"
    )

    service = SuccessorHistoricalRetrievalService(
        store=store,
        provider=provider,
        registry=registry,
    )

    return store, service


def test_cold_single_binding_fetches_and_persists_stream(
    tmp_path,
):
    provider_binding = binding(
        binding_id="angelone-abc-100",
        token="100",
        start=START,
        end=MID,
    )

    first = candle_at(
        START + timedelta(minutes=15),
        100.0,
    )

    provider = RecordingProvider(
        {
            provider_binding.binding_id: (
                first,
            )
        }
    )

    store, service = service_for(
        tmp_path,
        provider=provider,
        registry=registry_for(
            provider_binding
        ),
    )

    request = TimeRange(
        START,
        MID,
    )

    result = service.retrieve(
        CONTEXT,
        request,
        instrument_id=INSTRUMENT_ID,
        provider="angelone",
        price_adjustment_basis=(
            PriceAdjustmentBasis.UNKNOWN
        ),
    )

    assert result.candles == (
        first,
    )

    assert result.source == (
        "provider:angelone"
    )

    assert result.coverage == (
        request,
    )

    assert len(result.binding_segments) == 1
    assert (
        result.binding_segments[0].binding_id
        == provider_binding.binding_id
    )

    assert provider.calls == [
        (
            provider_binding.binding_id,
            request,
        )
    ]

    usage = result.stream_usages[0]

    assert usage.applied_range == request
    assert usage.fetched_ranges == (
        request,
    )

    assert store.load_acquisition_stream(
        usage.identity.stream_id,
        START,
        MID,
    ) == [
        first,
    ]


def test_warm_stream_reuses_saved_data_without_provider_call(
    tmp_path,
):
    provider_binding = binding(
        binding_id="angelone-abc-100",
        token="100",
        start=START,
        end=MID,
    )

    request = TimeRange(
        START,
        MID,
    )

    cached = candle_at(
        START + timedelta(minutes=15),
        100.0,
    )

    provider = RecordingProvider()

    store, service = service_for(
        tmp_path,
        provider=provider,
        registry=registry_for(
            provider_binding
        ),
    )

    identity = stream_identity(
        provider_binding
    )

    store.save_acquisition_stream_retrieval(
        identity.stream_id,
        [cached],
        [request],
    )

    result = service.retrieve(
        CONTEXT,
        request,
        instrument_id=INSTRUMENT_ID,
        provider="angelone",
        price_adjustment_basis=(
            PriceAdjustmentBasis.UNKNOWN
        ),
    )

    assert result.candles == (
        cached,
    )

    assert result.source == (
        "acquisition_stream_cache"
    )

    assert provider.calls == []

    assert (
        result.stream_usages[0].fetched_ranges
        == ()
    )


def test_partial_stream_fetches_only_missing_part(
    tmp_path,
):
    provider_binding = binding(
        binding_id="angelone-abc-100",
        token="100",
        start=START,
        end=END,
    )

    request = TimeRange(
        START,
        END,
    )

    cached = candle_at(
        START + timedelta(minutes=15),
        100.0,
    )

    fetched = candle_at(
        MID + timedelta(minutes=15),
        101.0,
    )

    provider = RecordingProvider(
        {
            provider_binding.binding_id: (
                fetched,
            )
        }
    )

    store, service = service_for(
        tmp_path,
        provider=provider,
        registry=registry_for(
            provider_binding
        ),
    )

    identity = stream_identity(
        provider_binding
    )

    store.save_acquisition_stream_retrieval(
        identity.stream_id,
        [cached],
        [
            TimeRange(
                START,
                MID,
            )
        ],
    )

    result = service.retrieve(
        CONTEXT,
        request,
        instrument_id=INSTRUMENT_ID,
        provider="angelone",
        price_adjustment_basis=(
            PriceAdjustmentBasis.UNKNOWN
        ),
    )

    assert result.candles == (
        cached,
        fetched,
    )

    assert result.source == (
        "mixed:"
        "acquisition_stream_cache+"
        "provider:angelone"
    )

    expected_gap = TimeRange(
        MID,
        END,
    )

    assert provider.calls == [
        (
            provider_binding.binding_id,
            expected_gap,
        )
    ]

    assert (
        result.stream_usages[0].fetched_ranges
        == (expected_gap,)
    )


def test_multi_binding_request_uses_separate_streams(
    tmp_path,
):
    old_binding = binding(
        binding_id="angelone-abc-old",
        token="100",
        start=START,
        end=MID,
    )

    new_binding = binding(
        binding_id="angelone-abc-new",
        token="200",
        start=MID,
        end=END,
    )

    old_candle = candle_at(
        START + timedelta(minutes=15),
        100.0,
    )

    new_candle = candle_at(
        MID + timedelta(minutes=15),
        200.0,
    )

    provider = RecordingProvider(
        {
            old_binding.binding_id: (
                old_candle,
            ),
            new_binding.binding_id: (
                new_candle,
            ),
        }
    )

    store, service = service_for(
        tmp_path,
        provider=provider,
        registry=registry_for(
            old_binding,
            new_binding,
        ),
    )

    request = TimeRange(
        START,
        END,
    )

    result = service.retrieve(
        CONTEXT,
        request,
        instrument_id=INSTRUMENT_ID,
        provider="angelone",
        price_adjustment_basis=(
            PriceAdjustmentBasis.UNKNOWN
        ),
    )

    assert result.candles == (
        old_candle,
        new_candle,
    )

    assert provider.calls == [
        (
            old_binding.binding_id,
            TimeRange(
                START,
                MID,
            ),
        ),
        (
            new_binding.binding_id,
            TimeRange(
                MID,
                END,
            ),
        ),
    ]

    assert [
        segment.binding_id
        for segment in result.binding_segments
    ] == [
        old_binding.binding_id,
        new_binding.binding_id,
    ]

    stream_ids = [
        usage.identity.stream_id
        for usage in result.stream_usages
    ]

    assert len(stream_ids) == 2
    assert len(set(stream_ids)) == 2

    assert (
        store.load_acquisition_stream(
            stream_ids[0],
            START,
            MID,
        )
        == [old_candle]
    )

    assert (
        store.load_acquisition_stream(
            stream_ids[1],
            MID,
            END,
        )
        == [new_candle]
    )


def test_price_basis_uses_different_physical_stream(
    tmp_path,
):
    provider_binding = binding(
        binding_id="angelone-abc-100",
        token="100",
        start=START,
        end=MID,
    )

    request = TimeRange(
        START,
        MID,
    )

    unknown_candle = candle_at(
        START + timedelta(minutes=15),
        100.0,
    )

    raw_candle = candle_at(
        START + timedelta(minutes=15),
        150.0,
    )

    provider = RecordingProvider(
        {
            provider_binding.binding_id: (
                raw_candle,
            )
        }
    )

    store, service = service_for(
        tmp_path,
        provider=provider,
        registry=registry_for(
            provider_binding
        ),
    )

    unknown_identity = stream_identity(
        provider_binding,
        basis=PriceAdjustmentBasis.UNKNOWN,
    )

    store.save_acquisition_stream_retrieval(
        unknown_identity.stream_id,
        [unknown_candle],
        [request],
    )

    result = service.retrieve(
        CONTEXT,
        request,
        instrument_id=INSTRUMENT_ID,
        provider="angelone",
        price_adjustment_basis=(
            PriceAdjustmentBasis.RAW
        ),
    )

    raw_identity = (
        result.stream_usages[0].identity
    )

    assert (
        raw_identity.stream_id
        != unknown_identity.stream_id
    )

    assert result.candles == (
        raw_candle,
    )

    assert result.source == (
        "provider:angelone"
    )

    assert len(provider.calls) == 1


def test_incomplete_provider_coverage_fails_closed(
    tmp_path,
):
    provider_binding = binding(
        binding_id="angelone-abc-100",
        token="100",
        start=START,
        end=END,
    )

    provider = PartialCoverageProvider()

    store, service = service_for(
        tmp_path,
        provider=provider,
        registry=registry_for(
            provider_binding
        ),
    )

    request = TimeRange(
        START,
        END,
    )

    with pytest.raises(
        IncompleteHistoricalCoverageError
    ):
        service.retrieve(
            CONTEXT,
            request,
            instrument_id=INSTRUMENT_ID,
            provider="angelone",
            price_adjustment_basis=(
                PriceAdjustmentBasis.UNKNOWN
            ),
        )

    identity = stream_identity(
        provider_binding
    )

    remaining = find_missing_ranges(
        request,
        store.load_acquisition_stream_coverage(
            identity.stream_id
        ),
    )

    assert remaining


def test_successor_retrieval_ignores_legacy_v1_cache(
    tmp_path,
):
    provider_binding = binding(
        binding_id="angelone-abc-100",
        token="100",
        start=START,
        end=MID,
    )

    request = TimeRange(
        START,
        MID,
    )

    timestamp = (
        START + timedelta(minutes=15)
    )

    legacy_candle = candle_at(
        timestamp,
        50.0,
    )

    successor_candle = candle_at(
        timestamp,
        150.0,
    )

    provider = RecordingProvider(
        {
            provider_binding.binding_id: (
                successor_candle,
            )
        }
    )

    store, service = service_for(
        tmp_path,
        provider=provider,
        registry=registry_for(
            provider_binding
        ),
    )

    store.save_retrieval(
        CONTEXT,
        [legacy_candle],
        [request],
    )

    result = service.retrieve(
        CONTEXT,
        request,
        instrument_id=INSTRUMENT_ID,
        provider="angelone",
        price_adjustment_basis=(
            PriceAdjustmentBasis.UNKNOWN
        ),
    )

    assert result.candles == (
        successor_candle,
    )

    assert result.candles != (
        legacy_candle,
    )

    assert provider.calls == [
        (
            provider_binding.binding_id,
            request,
        )
    ]

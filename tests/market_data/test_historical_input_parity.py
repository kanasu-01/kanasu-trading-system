from datetime import datetime, timedelta, timezone

import pytest

from core.config.historical_source_policy import HistoricalSourcePolicy
from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_retrieval import (
    HistoricalFetchResult,
    IncompleteHistoricalCoverageError,
)
from core.market_data.historical_source import HistoricalSource
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.runtime.dataset_context import DatasetContext


INDIA = timezone(timedelta(hours=5, minutes=30))
BASE = datetime(2026, 1, 2, 9, 0, 0, 123456, tzinfo=INDIA)
CONTEXT = DatasetContext(
    symbol="RELIANCE",
    timeframe="15m",
    timezone="Asia/Kolkata",
)


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def candle_at(minutes: int, value: float) -> Candle:
    return Candle(
        timestamp=at(minutes),
        open=value,
        high=value + 4.25,
        low=value - 3.5,
        close=value + 1.75,
        volume=value * 17.0 + minutes,
    )


class RecordingProvider:
    def __init__(self, result: HistoricalFetchResult):
        self.result = result
        self.requests: list[tuple[DatasetContext, TimeRange]] = []

    def fetch(
        self,
        context: DatasetContext,
        request: TimeRange,
    ) -> HistoricalFetchResult:
        self.requests.append((context, request))
        return self.result


class ProviderFactory:
    def __init__(self, provider=None):
        self.provider = provider
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.provider is None:
            pytest.fail("warm local path constructed a provider")
        return self.provider


def assert_candle_parity(
    fresh: list[Candle],
    warm: list[Candle],
) -> None:
    assert len(warm) == len(fresh)
    assert warm == fresh
    assert [candle.timestamp.isoformat() for candle in warm] == [
        candle.timestamp.isoformat() for candle in fresh
    ]
    assert [candle.open for candle in warm] == [
        candle.open for candle in fresh
    ]
    assert [candle.high for candle in warm] == [
        candle.high for candle in fresh
    ]
    assert [candle.low for candle in warm] == [
        candle.low for candle in fresh
    ]
    assert [candle.close for candle in warm] == [
        candle.close for candle in fresh
    ]
    assert [candle.volume for candle in warm] == [
        candle.volume for candle in fresh
    ]


@pytest.mark.parametrize(
    "warm_policy",
    [
        pytest.param(HistoricalSourcePolicy.LOCAL_ONLY, id="local-only"),
        pytest.param(HistoricalSourcePolicy.LOCAL_FIRST, id="local-first"),
    ],
)
def test_provider_fresh_and_durable_local_candles_are_identical(
    tmp_path,
    warm_policy,
):
    database_path = tmp_path / "candles.sqlite"
    request = TimeRange(at(0), at(60))
    accepted = [
        candle_at(0, 101.125),
        candle_at(15, 213.25),
        candle_at(45, 347.875),
    ]
    provider = RecordingProvider(
        HistoricalFetchResult(
            candles=tuple(accepted),
            coverage=(request,),
        )
    )
    fresh_factory = ProviderFactory(provider)

    fresh = HistoricalSource(
        SQLiteCandleStore(database_path),
        HistoricalSourcePolicy.PROVIDER_BACKED,
        fresh_factory,
    ).retrieve(CONTEXT, request)

    warm_factory = ProviderFactory()
    warm = HistoricalSource(
        SQLiteCandleStore(database_path),
        warm_policy,
        warm_factory,
    ).retrieve(CONTEXT, request)

    assert provider.requests == [(CONTEXT, request)]
    assert fresh_factory.calls == 1
    assert warm_factory.calls == 0
    assert fresh == accepted
    assert [candle.timestamp for candle in fresh] == sorted(
        candle.timestamp for candle in fresh
    )
    assert_candle_parity(fresh, warm)


def test_provider_fresh_and_warm_local_results_share_half_open_boundaries(
    tmp_path,
):
    database_path = tmp_path / "candles.sqlite"
    request = TimeRange(at(0), at(60))
    start_candle = candle_at(0, 111.0)
    interior_candle = candle_at(30, 222.0)
    end_candle = candle_at(60, 333.0)
    initial_store = SQLiteCandleStore(database_path)
    initial_store.save(CONTEXT, [end_candle])
    provider = RecordingProvider(
        HistoricalFetchResult(
            candles=(start_candle, interior_candle),
            coverage=(request,),
        )
    )

    fresh = HistoricalSource(
        initial_store,
        HistoricalSourcePolicy.PROVIDER_BACKED,
        ProviderFactory(provider),
    ).retrieve(CONTEXT, request)
    warm_factory = ProviderFactory()
    warm = HistoricalSource(
        SQLiteCandleStore(database_path),
        HistoricalSourcePolicy.LOCAL_ONLY,
        warm_factory,
    ).retrieve(CONTEXT, request)

    assert fresh == [start_candle, interior_candle]
    assert warm == fresh
    assert fresh[0].timestamp == request.start
    assert all(candle.timestamp != request.end for candle in fresh)
    assert all(candle.timestamp != request.end for candle in warm)
    assert warm_factory.calls == 0


def test_confirmed_empty_provider_and_warm_local_paths_are_identical(
    tmp_path,
):
    database_path = tmp_path / "candles.sqlite"
    request = TimeRange(at(0), at(60))
    provider = RecordingProvider(
        HistoricalFetchResult(candles=(), coverage=(request,))
    )

    fresh = HistoricalSource(
        SQLiteCandleStore(database_path),
        HistoricalSourcePolicy.PROVIDER_BACKED,
        ProviderFactory(provider),
    ).retrieve(CONTEXT, request)
    durable_store = SQLiteCandleStore(database_path)
    local_only_factory = ProviderFactory()
    local_first_factory = ProviderFactory()
    local_only = HistoricalSource(
        durable_store,
        HistoricalSourcePolicy.LOCAL_ONLY,
        local_only_factory,
    ).retrieve(CONTEXT, request)
    local_first = HistoricalSource(
        SQLiteCandleStore(database_path),
        HistoricalSourcePolicy.LOCAL_FIRST,
        local_first_factory,
    ).retrieve(CONTEXT, request)

    assert provider.requests == [(CONTEXT, request)]
    assert fresh == local_only == local_first == []
    assert durable_store.load_coverage(CONTEXT) == [request]
    assert local_only_factory.calls == 0
    assert local_first_factory.calls == 0


def test_persisted_parity_state_is_isolated_by_dataset_context(tmp_path):
    database_path = tmp_path / "candles.sqlite"
    request = TimeRange(at(0), at(60))
    candle = candle_at(15, 145.5)
    provider = RecordingProvider(
        HistoricalFetchResult(candles=(candle,), coverage=(request,))
    )

    result = HistoricalSource(
        SQLiteCandleStore(database_path),
        HistoricalSourcePolicy.PROVIDER_BACKED,
        ProviderFactory(provider),
    ).retrieve(CONTEXT, request)

    unrelated_context = DatasetContext(
        symbol="TCS",
        timeframe=CONTEXT.timeframe,
        timezone=CONTEXT.timezone,
    )
    unrelated_factory = ProviderFactory()
    with pytest.raises(IncompleteHistoricalCoverageError) as error:
        HistoricalSource(
            SQLiteCandleStore(database_path),
            HistoricalSourcePolicy.LOCAL_ONLY,
            unrelated_factory,
        ).retrieve(unrelated_context, request)

    assert provider.requests == [(CONTEXT, request)]
    assert result == [candle]
    assert error.value.missing_ranges == (request,)
    assert unrelated_factory.calls == 0
    assert SQLiteCandleStore(database_path).load_coverage(
        unrelated_context
    ) == []

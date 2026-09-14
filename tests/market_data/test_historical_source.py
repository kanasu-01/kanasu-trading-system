from datetime import datetime, timedelta

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


CONTEXT = DatasetContext(
    symbol="RELIANCE",
    timeframe="15m",
    timezone="Asia/Kolkata",
)
BASE = datetime(2026, 1, 2, 9, 0)


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def time_range(start: int, end: int) -> TimeRange:
    return TimeRange(at(start), at(end))


def candle_at(minutes: int, *, close: float = 100.5) -> Candle:
    return Candle(
        timestamp=at(minutes),
        open=100.0,
        high=110.0,
        low=90.0,
        close=close,
        volume=1000.0,
    )


def fetch_result(*, candles=(), coverage=()) -> HistoricalFetchResult:
    return HistoricalFetchResult(
        candles=tuple(candles),
        coverage=tuple(coverage),
    )


class FakeProvider:
    def __init__(self, outcomes=()):
        self.outcomes = list(outcomes)
        self.requests: list[tuple[DatasetContext, TimeRange]] = []

    def fetch(
        self,
        context: DatasetContext,
        request: TimeRange,
    ) -> HistoricalFetchResult:
        self.requests.append((context, request))
        if not self.outcomes:
            raise AssertionError("provider was called unexpectedly")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class ProviderFactory:
    def __init__(self, provider=None):
        self.provider = provider
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.provider is None:
            raise AssertionError("provider factory was called unexpectedly")
        return self.provider


def test_historical_source_policy_values_are_stable():
    assert HistoricalSourcePolicy.LOCAL_ONLY.value == "LOCAL_ONLY"
    assert HistoricalSourcePolicy.LOCAL_FIRST.value == "LOCAL_FIRST"
    assert HistoricalSourcePolicy.PROVIDER_BACKED.value == "PROVIDER_BACKED"


def test_local_only_returns_fully_covered_local_candles_without_factory(
    tmp_path,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    candles = [candle_at(0), candle_at(30), candle_at(60)]
    store.save_retrieval(CONTEXT, candles, [request])
    factory = ProviderFactory()

    result = HistoricalSource(
        store,
        HistoricalSourcePolicy.LOCAL_ONLY,
        factory,
    ).retrieve(CONTEXT, request)

    assert result == candles[:2]
    assert factory.calls == 0


def test_local_only_returns_confirmed_empty_without_factory(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    store.save_retrieval(CONTEXT, [], [request])
    factory = ProviderFactory()

    result = HistoricalSource(
        store,
        HistoricalSourcePolicy.LOCAL_ONLY,
        factory,
    ).retrieve(CONTEXT, request)

    assert result == []
    assert factory.calls == 0


def test_local_only_reports_exact_missing_ranges_without_factory(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    store.save_retrieval(CONTEXT, [], [time_range(0, 20), time_range(40, 60)])
    factory = ProviderFactory()

    with pytest.raises(IncompleteHistoricalCoverageError) as error:
        HistoricalSource(
            store,
            HistoricalSourcePolicy.LOCAL_ONLY,
            factory,
        ).retrieve(CONTEXT, request)

    assert error.value.missing_ranges == (time_range(20, 40),)
    assert factory.calls == 0


def test_local_only_does_not_treat_stored_candles_as_coverage(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    store.save(CONTEXT, [candle_at(15), candle_at(45)])
    factory = ProviderFactory()

    with pytest.raises(IncompleteHistoricalCoverageError) as error:
        HistoricalSource(
            store,
            HistoricalSourcePolicy.LOCAL_ONLY,
            factory,
        ).retrieve(CONTEXT, request)

    assert error.value.missing_ranges == (request,)
    assert factory.calls == 0


def test_local_first_returns_warm_cache_without_factory(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    candle = candle_at(15)
    store.save_retrieval(CONTEXT, [candle], [request])
    factory = ProviderFactory()

    result = HistoricalSource(
        store,
        HistoricalSourcePolicy.LOCAL_FIRST,
        factory,
    ).retrieve(CONTEXT, request)

    assert result == [candle]
    assert factory.calls == 0


def test_local_first_constructs_one_provider_for_one_missing_gap(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    local = candle_at(15)
    fetched = candle_at(45)
    missing = time_range(30, 60)
    store.save_retrieval(CONTEXT, [local], [time_range(0, 30)])
    provider = FakeProvider(
        [fetch_result(candles=[fetched], coverage=[missing])]
    )
    factory = ProviderFactory(provider)

    result = HistoricalSource(
        store,
        HistoricalSourcePolicy.LOCAL_FIRST,
        factory,
    ).retrieve(CONTEXT, request)

    assert factory.calls == 1
    assert provider.requests == [(CONTEXT, missing)]
    assert result == [local, fetched]
    assert SQLiteCandleStore(tmp_path / "candles.sqlite").load_coverage(
        CONTEXT
    ) == [time_range(0, 30), missing]


def test_local_first_uses_one_provider_instance_for_multiple_gaps(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 100)
    store.save_retrieval(
        CONTEXT,
        [],
        [time_range(20, 40), time_range(60, 80)],
    )
    gaps = [time_range(0, 20), time_range(40, 60), time_range(80, 100)]
    provider = FakeProvider(
        [
            fetch_result(candles=[candle_at(10)], coverage=[gaps[0]]),
            fetch_result(candles=[candle_at(50)], coverage=[gaps[1]]),
            fetch_result(candles=[candle_at(90)], coverage=[gaps[2]]),
        ]
    )
    factory = ProviderFactory(provider)

    HistoricalSource(
        store,
        HistoricalSourcePolicy.LOCAL_FIRST,
        factory,
    ).retrieve(CONTEXT, request)

    assert factory.calls == 1
    assert provider.requests == [(CONTEXT, gap) for gap in gaps]


def test_provider_backed_full_local_cache_cannot_suppress_provider(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    existing = candle_at(15)
    fetched = candle_at(45)
    store.save_retrieval(CONTEXT, [existing], [request])
    provider = FakeProvider(
        [fetch_result(candles=[fetched], coverage=[request])]
    )
    factory = ProviderFactory(provider)

    result = HistoricalSource(
        store,
        HistoricalSourcePolicy.PROVIDER_BACKED,
        factory,
    ).retrieve(CONTEXT, request)

    assert factory.calls == 1
    assert provider.requests == [(CONTEXT, request)]
    assert result == [existing, fetched]


def test_provider_backed_accepts_confirmed_empty_full_evidence(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    provider = FakeProvider([fetch_result(coverage=[request])])
    factory = ProviderFactory(provider)

    result = HistoricalSource(
        store,
        HistoricalSourcePolicy.PROVIDER_BACKED,
        factory,
    ).retrieve(CONTEXT, request)

    assert result == []
    assert factory.calls == 1
    assert provider.requests == [(CONTEXT, request)]
    assert store.load_coverage(CONTEXT) == [request]


def test_old_local_coverage_cannot_mask_partial_provider_evidence(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    existing = candle_at(15)
    store.save_retrieval(CONTEXT, [existing], [request])
    provider_coverage = time_range(0, 30)
    provider_candle = candle_at(20)
    provider = FakeProvider(
        [
            fetch_result(
                candles=[provider_candle],
                coverage=[provider_coverage],
            )
        ]
    )
    factory = ProviderFactory(provider)

    with pytest.raises(IncompleteHistoricalCoverageError) as error:
        HistoricalSource(
            store,
            HistoricalSourcePolicy.PROVIDER_BACKED,
            factory,
        ).retrieve(CONTEXT, request)

    assert error.value.missing_ranges == (time_range(30, 60),)
    assert factory.calls == 1
    assert provider.requests == [(CONTEXT, request)]
    assert store.load(CONTEXT, request.start, request.end) == [existing]


@pytest.mark.parametrize(
    "policy",
    [
        pytest.param(HistoricalSourcePolicy.LOCAL_FIRST, id="local-first"),
        pytest.param(
            HistoricalSourcePolicy.PROVIDER_BACKED,
            id="provider-backed",
        ),
    ],
)
def test_required_provider_factory_missing_raises_clear_error(tmp_path, policy):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)

    with pytest.raises(RuntimeError, match="provider is required"):
        HistoricalSource(store, policy).retrieve(CONTEXT, request)


@pytest.mark.parametrize(
    "policy",
    [
        pytest.param(HistoricalSourcePolicy.LOCAL_ONLY, id="local-only"),
        pytest.param(HistoricalSourcePolicy.LOCAL_FIRST, id="local-first"),
    ],
)
def test_provider_factory_is_optional_for_complete_local_coverage(
    tmp_path,
    policy,
):
    store = SQLiteCandleStore(tmp_path / f"{policy.value}.sqlite")
    request = time_range(0, 60)
    candle = candle_at(15)
    store.save_retrieval(CONTEXT, [candle], [request])

    assert HistoricalSource(store, policy).retrieve(CONTEXT, request) == [
        candle
    ]


def test_provider_backed_reuses_existing_result_validation(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    provider = FakeProvider(
        [
            fetch_result(
                candles=[candle_at(45)],
                coverage=[time_range(0, 30)],
            )
        ]
    )

    with pytest.raises(ValueError, match="explicit coverage"):
        HistoricalSource(
            store,
            HistoricalSourcePolicy.PROVIDER_BACKED,
            ProviderFactory(provider),
        ).retrieve(CONTEXT, request)

    assert store.load(CONTEXT, request.start, request.end) == []
    assert store.load_coverage(CONTEXT) == []

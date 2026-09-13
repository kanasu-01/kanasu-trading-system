from datetime import datetime, timedelta, timezone

import pytest

from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_retrieval import (
    HistoricalFetchResult,
    IncompleteHistoricalCoverageError,
    LocalFirstHistoricalService,
)
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.runtime.dataset_context import DatasetContext


BASE = datetime(2026, 1, 2, 9, 0)
CONTEXT = DatasetContext(
    symbol="RELIANCE",
    timeframe="15m",
    timezone="Asia/Kolkata",
)


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def time_range(start_minutes: int, end_minutes: int) -> TimeRange:
    return TimeRange(at(start_minutes), at(end_minutes))


def candle_at(
    minutes: int,
    *,
    close: float = 100.5,
    timestamp: datetime | None = None,
) -> Candle:
    return Candle(
        timestamp=timestamp or at(minutes),
        open=100.0,
        high=110.0,
        low=90.0,
        close=close,
        volume=1000.0,
    )


class FakeHistoricalProvider:
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


def result(
    *,
    candles=(),
    coverage=(),
) -> HistoricalFetchResult:
    return HistoricalFetchResult(
        candles=tuple(candles),
        coverage=tuple(coverage),
    )


@pytest.mark.parametrize(
    "stored_candles",
    [
        pytest.param([], id="confirmed-empty"),
        pytest.param([candle_at(15)], id="sparse"),
    ],
)
def test_fully_covered_local_request_does_not_call_provider(
    tmp_path,
    stored_candles,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    store.save_retrieval(CONTEXT, stored_candles, [request])
    provider = FakeHistoricalProvider()

    loaded = LocalFirstHistoricalService(store, provider).retrieve(
        CONTEXT,
        request,
    )

    assert loaded == stored_candles
    assert provider.requests == []


def test_stored_candles_without_coverage_still_call_provider(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    candle = candle_at(15)
    store.save(CONTEXT, [candle])
    provider = FakeHistoricalProvider(
        [result(candles=[candle], coverage=[request])]
    )

    assert LocalFirstHistoricalService(store, provider).retrieve(
        CONTEXT,
        request,
    ) == [candle]
    assert provider.requests == [(CONTEXT, request)]


def test_partial_persisted_coverage_fetches_only_missing_range(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    stored_coverage = time_range(0, 30)
    missing = time_range(30, 60)
    stored = candle_at(15)
    fetched = candle_at(45)
    store.save_retrieval(CONTEXT, [stored], [stored_coverage])
    provider = FakeHistoricalProvider(
        [result(candles=[fetched], coverage=[missing])]
    )

    loaded = LocalFirstHistoricalService(store, provider).retrieve(
        CONTEXT,
        request,
    )

    assert provider.requests == [(CONTEXT, missing)]
    assert loaded == [stored, fetched]


def test_multiple_coverage_islands_fetch_only_each_missing_gap(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    store.save_retrieval(
        CONTEXT,
        [],
        [time_range(10, 20), time_range(30, 40)],
    )
    gaps = [
        time_range(0, 10),
        time_range(20, 30),
        time_range(40, 60),
    ]
    provider = FakeHistoricalProvider(
        [result(coverage=[gap]) for gap in gaps]
    )

    assert LocalFirstHistoricalService(store, provider).retrieve(
        CONTEXT,
        request,
    ) == []
    assert provider.requests == [(CONTEXT, gap) for gap in gaps]


def test_fresh_service_instance_reuses_persisted_retrieval(tmp_path):
    database_path = tmp_path / "candles.sqlite"
    request = time_range(0, 60)
    candles = [candle_at(15), candle_at(30)]
    first_provider = FakeHistoricalProvider(
        [result(candles=candles, coverage=[request])]
    )

    first_loaded = LocalFirstHistoricalService(
        SQLiteCandleStore(database_path),
        first_provider,
    ).retrieve(CONTEXT, request)

    second_provider = FakeHistoricalProvider()
    second_loaded = LocalFirstHistoricalService(
        SQLiteCandleStore(database_path),
        second_provider,
    ).retrieve(CONTEXT, request)

    assert first_loaded == candles
    assert second_loaded == candles
    assert second_provider.requests == []


def test_full_provider_success_persists_candles_and_coverage(tmp_path):
    database_path = tmp_path / "candles.sqlite"
    request = time_range(0, 60)
    candles = [candle_at(15), candle_at(30)]
    provider = FakeHistoricalProvider(
        [result(candles=candles, coverage=[request])]
    )

    assert LocalFirstHistoricalService(
        SQLiteCandleStore(database_path),
        provider,
    ).retrieve(CONTEXT, request) == candles

    fresh_store = SQLiteCandleStore(database_path)
    assert fresh_store.load_coverage(CONTEXT) == [request]
    assert fresh_store.load(CONTEXT, request.start, request.end) == candles


def test_confirmed_empty_result_persists_coverage(tmp_path):
    database_path = tmp_path / "candles.sqlite"
    request = time_range(0, 60)
    provider = FakeHistoricalProvider([result(coverage=[request])])

    assert LocalFirstHistoricalService(
        SQLiteCandleStore(database_path),
        provider,
    ).retrieve(CONTEXT, request) == []

    fresh_store = SQLiteCandleStore(database_path)
    assert fresh_store.load_coverage(CONTEXT) == [request]


def test_partial_result_persists_claim_and_reports_remaining_range(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    covered = time_range(0, 30)
    candle = candle_at(15)
    provider = FakeHistoricalProvider(
        [result(candles=[candle], coverage=[covered])]
    )

    with pytest.raises(IncompleteHistoricalCoverageError) as error:
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    assert error.value.missing_ranges == (time_range(30, 60),)
    assert store.load_coverage(CONTEXT) == [covered]
    assert store.load(CONTEXT, request.start, request.end) == [candle]


def test_request_after_partial_result_fetches_only_remaining_range(tmp_path):
    database_path = tmp_path / "candles.sqlite"
    request = time_range(0, 60)
    first_coverage = time_range(0, 30)
    first_provider = FakeHistoricalProvider(
        [result(candles=[candle_at(15)], coverage=[first_coverage])]
    )

    with pytest.raises(IncompleteHistoricalCoverageError):
        LocalFirstHistoricalService(
            SQLiteCandleStore(database_path),
            first_provider,
        ).retrieve(CONTEXT, request)

    remaining = time_range(30, 60)
    second_provider = FakeHistoricalProvider(
        [result(candles=[candle_at(45)], coverage=[remaining])]
    )
    loaded = LocalFirstHistoricalService(
        SQLiteCandleStore(database_path),
        second_provider,
    ).retrieve(CONTEXT, request)

    assert second_provider.requests == [(CONTEXT, remaining)]
    assert loaded == [candle_at(15), candle_at(45)]


def test_provider_exception_creates_no_persisted_state(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    provider = FakeHistoricalProvider([RuntimeError("provider failed")])

    with pytest.raises(RuntimeError, match="provider failed"):
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    assert store.load_coverage(CONTEXT) == []
    assert store.load(CONTEXT, request.start, request.end) == []


def test_provider_result_without_coverage_is_rejected_without_persistence(
    tmp_path,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    provider = FakeHistoricalProvider(
        [result(candles=[candle_at(15)])]
    )

    with pytest.raises(ValueError, match="coverage"):
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    assert store.load_coverage(CONTEXT) == []
    assert store.load(CONTEXT, request.start, request.end) == []


@pytest.mark.parametrize(
    "invalid_coverage",
    [
        pytest.param(time_range(-15, 30), id="starts-before-gap"),
        pytest.param(time_range(30, 75), id="ends-after-gap"),
        pytest.param(time_range(60, 75), id="entirely-after-gap"),
    ],
)
def test_provider_coverage_outside_requested_gap_is_rejected(
    tmp_path,
    invalid_coverage,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    provider = FakeHistoricalProvider(
        [result(coverage=[invalid_coverage])]
    )

    with pytest.raises(ValueError, match="coverage.*gap|contained"):
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    assert store.load_coverage(CONTEXT) == []


@pytest.mark.parametrize(
    "outside_candle",
    [
        pytest.param(candle_at(-15), id="before-gap"),
        pytest.param(candle_at(60), id="at-exclusive-end"),
    ],
)
def test_provider_candle_outside_requested_gap_is_rejected(
    tmp_path,
    outside_candle,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    provider = FakeHistoricalProvider(
        [result(candles=[outside_candle], coverage=[request])]
    )

    with pytest.raises(ValueError, match="candle.*gap"):
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    assert store.load_coverage(CONTEXT) == []


def test_provider_candle_must_be_inside_explicit_coverage(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    provider = FakeHistoricalProvider(
        [
            result(
                candles=[candle_at(45)],
                coverage=[time_range(0, 30)],
            )
        ]
    )

    with pytest.raises(ValueError, match="candle.*coverage"):
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    assert store.load_coverage(CONTEXT) == []


@pytest.mark.parametrize(
    "candles",
    [
        pytest.param(
            [candle_at(15), candle_at(15)],
            id="duplicate",
        ),
        pytest.param(
            [candle_at(30), candle_at(15)],
            id="out-of-order",
        ),
    ],
)
def test_malformed_provider_candle_sequence_is_rejected(
    tmp_path,
    candles,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    provider = FakeHistoricalProvider(
        [result(candles=candles, coverage=[request])]
    )

    with pytest.raises(ValueError, match="duplicate|chronological|older"):
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    assert store.load_coverage(CONTEXT) == []
    assert store.load(CONTEXT, request.start, request.end) == []


def test_provider_coverage_timezone_awareness_must_match_gap(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    aware_coverage = TimeRange(
        at(0).replace(tzinfo=timezone.utc),
        at(60).replace(tzinfo=timezone.utc),
    )
    provider = FakeHistoricalProvider(
        [result(coverage=[aware_coverage])]
    )

    with pytest.raises(ValueError, match="timezone"):
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    assert store.load_coverage(CONTEXT) == []


def test_provider_candle_timezone_awareness_must_match_gap(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    aware_candle = candle_at(
        15,
        timestamp=at(15).replace(tzinfo=timezone.utc),
    )
    provider = FakeHistoricalProvider(
        [result(candles=[aware_candle], coverage=[request])]
    )

    with pytest.raises(ValueError, match="timezone"):
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    assert store.load_coverage(CONTEXT) == []


def test_identical_existing_candle_is_idempotent(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    candle = candle_at(15)
    store.save(CONTEXT, [candle])
    provider = FakeHistoricalProvider(
        [result(candles=[candle], coverage=[request])]
    )

    assert LocalFirstHistoricalService(store, provider).retrieve(
        CONTEXT,
        request,
    ) == [candle]
    assert store.load(CONTEXT, request.start, request.end) == [candle]


def test_conflicting_overlap_rolls_back_candles_and_coverage(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    existing = candle_at(30, close=100.5)
    new_candle = candle_at(15, close=101.0)
    conflicting = candle_at(30, close=102.0)
    store.save(CONTEXT, [existing])
    provider = FakeHistoricalProvider(
        [
            result(
                candles=[new_candle, conflicting],
                coverage=[request],
            )
        ]
    )

    with pytest.raises(ValueError, match="conflict"):
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    assert store.load(
        CONTEXT,
        request.start,
        request.end,
    ) == [existing]
    assert store.load_coverage(CONTEXT) == []


def test_service_adapts_inclusive_store_read_to_half_open_request(
    tmp_path,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    at_start = candle_at(0)
    at_end = candle_at(60)
    store.save_retrieval(
        CONTEXT,
        [at_start, at_end],
        [request],
    )
    provider = FakeHistoricalProvider()

    loaded = LocalFirstHistoricalService(store, provider).retrieve(
        CONTEXT,
        request,
    )

    assert loaded == [at_start]
    assert provider.requests == []


def test_candle_and_coverage_state_are_isolated_by_dataset(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    other_context = DatasetContext(
        symbol="TCS",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )
    first_candle = candle_at(15, close=101.0)
    other_candle = candle_at(15, close=102.0)
    store.save_retrieval(CONTEXT, [first_candle], [request])
    provider = FakeHistoricalProvider(
        [result(candles=[other_candle], coverage=[request])]
    )

    loaded = LocalFirstHistoricalService(store, provider).retrieve(
        other_context,
        request,
    )

    assert provider.requests == [(other_context, request)]
    assert loaded == [other_candle]
    assert store.load(CONTEXT, request.start, request.end) == [
        first_candle
    ]


def test_aware_timestamps_keep_offsets_without_conversion(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    india = timezone(timedelta(hours=5, minutes=30))
    request = TimeRange(
        datetime(2026, 1, 2, 9, 0, tzinfo=india),
        datetime(2026, 1, 2, 10, 0, tzinfo=india),
    )
    candle = candle_at(
        0,
        timestamp=datetime(2026, 1, 2, 3, 45, tzinfo=timezone.utc),
    )
    coverage = TimeRange(
        datetime(2026, 1, 2, 3, 30, tzinfo=timezone.utc),
        datetime(2026, 1, 2, 4, 30, tzinfo=timezone.utc),
    )
    provider = FakeHistoricalProvider(
        [result(candles=[candle], coverage=[coverage])]
    )

    loaded = LocalFirstHistoricalService(store, provider).retrieve(
        CONTEXT,
        request,
    )

    assert loaded == [candle]
    assert loaded[0].timestamp.utcoffset() == timedelta(0)
    assert provider.requests == [(CONTEXT, request)]


def test_service_reuses_identical_cross_offset_candle(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    india = timezone(timedelta(hours=5, minutes=30))
    request = TimeRange(
        datetime(2026, 1, 2, 9, 0, tzinfo=india),
        datetime(2026, 1, 2, 10, 0, tzinfo=india),
    )
    stored = candle_at(
        0,
        timestamp=datetime(2026, 1, 2, 9, 15, tzinfo=india),
    )
    equivalent_provider_candle = candle_at(
        0,
        timestamp=datetime(2026, 1, 2, 3, 45, tzinfo=timezone.utc),
    )
    store.save(CONTEXT, [stored])
    provider = FakeHistoricalProvider(
        [
            result(
                candles=[equivalent_provider_candle],
                coverage=[request],
            )
        ]
    )

    loaded = LocalFirstHistoricalService(store, provider).retrieve(
        CONTEXT,
        request,
    )

    assert loaded == [stored]
    assert loaded[0].timestamp.isoformat() == stored.timestamp.isoformat()

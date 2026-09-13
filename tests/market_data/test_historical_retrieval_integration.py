from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.market_data.historical_coverage import (
    TimeRange,
    find_missing_ranges,
)
from core.market_data.historical_retrieval import (
    HistoricalFetchResult,
    IncompleteHistoricalCoverageError,
    LocalFirstHistoricalService,
)
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.runtime.dataset_context import DatasetContext


CONTEXT = DatasetContext(
    symbol="RELIANCE",
    timeframe="15m",
    timezone="Asia/Kolkata",
)
BASE = datetime(2026, 1, 2, 9, 0)


def at(minutes: int) -> datetime:
    return BASE.replace(minute=0) + timedelta(minutes=minutes)


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


def fetch_result(
    *,
    candles=(),
    coverage=(),
) -> HistoricalFetchResult:
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


def test_complex_cold_retrieval_becomes_durable_warm_retrieval(tmp_path):
    database_path = tmp_path / "candles.sqlite"
    request = time_range(0, 120)
    local_coverage = [time_range(30, 60), time_range(90, 105)]
    local_candles = [candle_at(45), candle_at(95)]
    gaps = [time_range(0, 30), time_range(60, 90), time_range(105, 120)]
    fetched = [candle_at(15), candle_at(75), candle_at(110)]
    store = SQLiteCandleStore(database_path)
    store.save_retrieval(CONTEXT, local_candles, local_coverage)
    assert find_missing_ranges(request, store.load_coverage(CONTEXT)) == gaps
    provider = FakeProvider(
        [
            fetch_result(candles=[candle], coverage=[gap])
            for gap, candle in zip(gaps, fetched)
        ]
    )

    cold_result = LocalFirstHistoricalService(store, provider).retrieve(
        CONTEXT,
        request,
    )

    expected = [fetched[0], local_candles[0], fetched[1], local_candles[1], fetched[2]]
    assert provider.requests == [(CONTEXT, gap) for gap in gaps]
    assert cold_result == expected
    assert list(CandleSeries(cold_result)) == expected
    assert find_missing_ranges(request, store.load_coverage(CONTEXT)) == []

    warm_provider = FakeProvider()
    warm_result = LocalFirstHistoricalService(
        SQLiteCandleStore(database_path),
        warm_provider,
    ).retrieve(CONTEXT, request)

    assert warm_result == expected
    assert warm_provider.requests == []


def test_earlier_gap_success_survives_later_provider_failure(tmp_path):
    database_path = tmp_path / "candles.sqlite"
    request = time_range(0, 120)
    store = SQLiteCandleStore(database_path)
    store.save_retrieval(
        CONTEXT,
        [],
        [time_range(30, 60), time_range(90, 105)],
    )
    gaps = [time_range(0, 30), time_range(60, 90), time_range(105, 120)]
    first_candle = candle_at(15)
    provider = FakeProvider(
        [
            fetch_result(candles=[first_candle], coverage=[gaps[0]]),
            RuntimeError("second gap failed"),
            fetch_result(candles=[candle_at(110)], coverage=[gaps[2]]),
        ]
    )

    with pytest.raises(RuntimeError, match="second gap failed"):
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    assert provider.requests == [
        (CONTEXT, gaps[0]),
        (CONTEXT, gaps[1]),
    ]
    assert find_missing_ranges(request, store.load_coverage(CONTEXT)) == gaps[1:]
    assert store.load(CONTEXT, request.start, request.end) == [first_candle]

    remaining_candles = [candle_at(75), candle_at(110)]
    retry_provider = FakeProvider(
        [
            fetch_result(candles=[candle], coverage=[gap])
            for gap, candle in zip(gaps[1:], remaining_candles)
        ]
    )
    result = LocalFirstHistoricalService(
        SQLiteCandleStore(database_path),
        retry_provider,
    ).retrieve(CONTEXT, request)

    assert retry_provider.requests == [
        (CONTEXT, gaps[1]),
        (CONTEXT, gaps[2]),
    ]
    assert result == [first_candle, *remaining_candles]


def test_partial_gap_result_resumes_only_actual_remaining_range(tmp_path):
    database_path = tmp_path / "candles.sqlite"
    request = time_range(0, 90)
    store = SQLiteCandleStore(database_path)
    store.save_retrieval(CONTEXT, [], [time_range(30, 60)])
    initial_gaps = [time_range(0, 30), time_range(60, 90)]
    partial_coverage = time_range(0, 15)
    first_candle = candle_at(5)
    second_candle = candle_at(75)
    provider = FakeProvider(
        [
            fetch_result(
                candles=[first_candle],
                coverage=[partial_coverage],
            ),
            fetch_result(
                candles=[second_candle],
                coverage=[initial_gaps[1]],
            ),
        ]
    )

    with pytest.raises(IncompleteHistoricalCoverageError) as error:
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    remaining = time_range(15, 30)
    assert provider.requests == [
        (CONTEXT, initial_gaps[0]),
        (CONTEXT, initial_gaps[1]),
    ]
    assert error.value.missing_ranges == (remaining,)
    assert find_missing_ranges(request, store.load_coverage(CONTEXT)) == [
        remaining
    ]

    resumed_candle = candle_at(20)
    retry_provider = FakeProvider(
        [fetch_result(candles=[resumed_candle], coverage=[remaining])]
    )
    result = LocalFirstHistoricalService(
        SQLiteCandleStore(database_path),
        retry_provider,
    ).retrieve(CONTEXT, request)

    assert retry_provider.requests == [(CONTEXT, remaining)]
    assert result == [first_candle, resumed_candle, second_candle]


def test_later_gap_conflict_rolls_back_only_that_provider_result(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 90)
    middle_coverage = time_range(30, 60)
    first_gap = time_range(0, 30)
    second_gap = time_range(60, 90)
    existing = candle_at(75, close=100.5)
    first_gap_candle = candle_at(15)
    new_second_gap_candle = candle_at(65)
    conflicting = candle_at(75, close=105.0)
    store.save_retrieval(CONTEXT, [], [middle_coverage])
    store.save(CONTEXT, [existing])
    provider = FakeProvider(
        [
            fetch_result(
                candles=[first_gap_candle],
                coverage=[first_gap],
            ),
            fetch_result(
                candles=[new_second_gap_candle, conflicting],
                coverage=[second_gap],
            ),
        ]
    )

    with pytest.raises(ValueError, match="conflict"):
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    assert provider.requests == [
        (CONTEXT, first_gap),
        (CONTEXT, second_gap),
    ]
    assert store.load(CONTEXT, request.start, request.end) == [
        first_gap_candle,
        existing,
    ]
    assert store.load_coverage(CONTEXT) == [first_gap, middle_coverage]
    assert find_missing_ranges(request, store.load_coverage(CONTEXT)) == [
        second_gap
    ]


def test_raw_coverage_islands_are_reconciled_by_planner(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    request = time_range(0, 60)
    raw_coverage = [
        time_range(0, 20),
        time_range(10, 30),
        time_range(30, 45),
        time_range(45, 60),
    ]
    store.save_retrieval(CONTEXT, [], raw_coverage)
    provider = FakeProvider()

    result = LocalFirstHistoricalService(store, provider).retrieve(
        CONTEXT,
        request,
    )

    assert store.load_coverage(CONTEXT) == raw_coverage
    assert find_missing_ranges(request, raw_coverage) == []
    assert result == []
    assert provider.requests == []


@pytest.mark.parametrize(
    ("persisted_aware", "request_aware"),
    [
        pytest.param(False, True, id="persisted-naive-request-aware"),
        pytest.param(True, False, id="persisted-aware-request-naive"),
    ],
)
def test_incompatible_persisted_request_awareness_fails_before_provider(
    tmp_path,
    persisted_aware,
    request_aware,
):
    persisted_timezone = timezone.utc if persisted_aware else None
    request_timezone = timezone.utc if request_aware else None
    persisted_range = TimeRange(
        datetime(2026, 1, 2, 9, 0, tzinfo=persisted_timezone),
        datetime(2026, 1, 2, 10, 0, tzinfo=persisted_timezone),
    )
    request = TimeRange(
        datetime(2026, 1, 2, 9, 0, tzinfo=request_timezone),
        datetime(2026, 1, 2, 10, 0, tzinfo=request_timezone),
    )
    candle = candle_at(
        0,
        timestamp=datetime(
            2026,
            1,
            2,
            9,
            15,
            tzinfo=persisted_timezone,
        ),
    )
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    store.save_retrieval(CONTEXT, [candle], [persisted_range])
    provider = FakeProvider()

    with pytest.raises(ValueError, match="timezone"):
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    assert provider.requests == []
    assert store.load_coverage(CONTEXT) == [persisted_range]
    assert store.load(
        CONTEXT,
        persisted_range.start,
        persisted_range.end,
    ) == [candle]


def test_legacy_cross_offset_duplicate_is_rejected_without_repair(tmp_path):
    database_path = tmp_path / "candles.sqlite"
    store = SQLiteCandleStore(database_path)
    india = timezone(timedelta(hours=5, minutes=30))
    request = TimeRange(
        datetime(2026, 1, 2, 9, 0, tzinfo=india),
        datetime(2026, 1, 2, 10, 0, tzinfo=india),
    )
    store.save_retrieval(CONTEXT, [], [request])
    timestamps = [
        datetime(2026, 1, 2, 9, 15, tzinfo=india),
        datetime(2026, 1, 2, 3, 45, tzinfo=timezone.utc),
    ]

    with sqlite3.connect(database_path) as connection:
        dataset_key = connection.execute(
            "SELECT dataset_key FROM retrieval_coverage LIMIT 1"
        ).fetchone()[0]
        for timestamp in timestamps:
            connection.execute(
                """
                INSERT INTO candles (
                    dataset_key,
                    timestamp_iso,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    dataset_key,
                    timestamp.isoformat(timespec="microseconds"),
                    100.0,
                    110.0,
                    90.0,
                    100.5,
                    1000.0,
                ),
            )

    provider = FakeProvider()
    with pytest.raises(ValueError, match="duplicate"):
        LocalFirstHistoricalService(store, provider).retrieve(
            CONTEXT,
            request,
        )

    assert provider.requests == []
    with sqlite3.connect(database_path) as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM candles"
        ).fetchone()[0] == 2


def test_half_open_boundary_survives_durable_reload(tmp_path):
    database_path = tmp_path / "candles.sqlite"
    request = time_range(0, 60)
    at_start = candle_at(0)
    inside = candle_at(30)
    at_end = candle_at(60)
    SQLiteCandleStore(database_path).save_retrieval(
        CONTEXT,
        [at_start, inside, at_end],
        [request],
    )
    provider = FakeProvider()

    result = LocalFirstHistoricalService(
        SQLiteCandleStore(database_path),
        provider,
    ).retrieve(CONTEXT, request)

    assert result == [at_start, inside]
    assert provider.requests == []


def test_confirmed_empty_coverage_is_reused_durably(tmp_path):
    database_path = tmp_path / "candles.sqlite"
    request = time_range(0, 60)
    first_provider = FakeProvider([fetch_result(coverage=[request])])

    assert LocalFirstHistoricalService(
        SQLiteCandleStore(database_path),
        first_provider,
    ).retrieve(CONTEXT, request) == []

    second_provider = FakeProvider()
    assert LocalFirstHistoricalService(
        SQLiteCandleStore(database_path),
        second_provider,
    ).retrieve(CONTEXT, request) == []
    assert second_provider.requests == []


def test_dataset_isolation_across_complete_retrieval_lifecycles(tmp_path):
    database_path = tmp_path / "candles.sqlite"
    request = time_range(0, 60)
    second_context = DatasetContext(
        symbol="TCS",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )
    first_candle = candle_at(15, close=101.0)
    second_candle = candle_at(15, close=102.0)
    first_provider = FakeProvider(
        [fetch_result(candles=[first_candle], coverage=[request])]
    )
    second_provider = FakeProvider(
        [fetch_result(candles=[second_candle], coverage=[request])]
    )

    first_result = LocalFirstHistoricalService(
        SQLiteCandleStore(database_path),
        first_provider,
    ).retrieve(CONTEXT, request)
    second_result = LocalFirstHistoricalService(
        SQLiteCandleStore(database_path),
        second_provider,
    ).retrieve(second_context, request)

    assert first_result == [first_candle]
    assert second_result == [second_candle]
    assert first_provider.requests == [(CONTEXT, request)]
    assert second_provider.requests == [(second_context, request)]
    store = SQLiteCandleStore(database_path)
    assert store.load(CONTEXT, request.start, request.end) == [first_candle]
    assert store.load(
        second_context,
        request.start,
        request.end,
    ) == [second_candle]

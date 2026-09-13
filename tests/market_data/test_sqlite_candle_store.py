from datetime import datetime, timedelta, timezone

import pytest

from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.runtime.dataset_context import DatasetContext


DATASET_CONTEXT = DatasetContext(
    symbol="RELIANCE",
    timeframe="15m",
    timezone="Asia/Kolkata",
)


def candle_at(
    timestamp: datetime,
    *,
    close: float = 100.5,
    volume: float = 1000.0,
) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=100.0,
        high=110.0,
        low=90.0,
        close=close,
        volume=volume,
    )


def test_sqlite_candle_store_round_trip(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    candles = [
        candle_at(datetime(2026, 1, 2, 9, 15)),
        candle_at(datetime(2026, 1, 2, 9, 30)),
        candle_at(datetime(2026, 1, 2, 9, 45)),
    ]

    store.save(DATASET_CONTEXT, candles)
    loaded = store.load(
        DATASET_CONTEXT,
        start=candles[0].timestamp,
        end=candles[-1].timestamp,
    )

    assert loaded == candles


def test_sqlite_candle_store_persists_across_instances(tmp_path):
    database_path = tmp_path / "candles.sqlite"
    candles = [
        candle_at(datetime(2026, 1, 2, 9, 15)),
        candle_at(datetime(2026, 1, 2, 9, 30)),
    ]
    first_store = SQLiteCandleStore(database_path)
    first_store.save(DATASET_CONTEXT, candles)

    second_store = SQLiteCandleStore(database_path)
    loaded = second_store.load(
        DATASET_CONTEXT,
        start=candles[0].timestamp,
        end=candles[-1].timestamp,
    )

    assert loaded == candles


def test_sqlite_candle_store_preserves_timestamp_fidelity(tmp_path):
    india_offset = timezone(timedelta(hours=5, minutes=30))
    cases = [
        (
            "naive",
            DatasetContext(symbol="RELIANCE", timeframe="15m"),
            datetime(2026, 1, 2, 9, 15, 0, 123456),
        ),
        (
            "aware",
            DATASET_CONTEXT,
            datetime(2026, 1, 2, 9, 15, 0, 654321, tzinfo=india_offset),
        ),
    ]

    for label, context, timestamp in cases:
        store = SQLiteCandleStore(tmp_path / f"{label}.sqlite")
        candle = candle_at(timestamp)

        store.save(context, [candle])
        loaded = store.load(context, start=timestamp, end=timestamp)

        assert loaded == [candle]
        assert loaded[0].timestamp.microsecond == timestamp.microsecond
        assert loaded[0].timestamp.utcoffset() == timestamp.utcoffset()


def test_sqlite_candle_store_isolates_dataset_identity(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    timestamp = datetime(2026, 1, 2, 9, 15)
    datasets = [
        (
            DatasetContext("RELIANCE", "15m", "Asia/Kolkata"),
            candle_at(timestamp, close=101.0),
        ),
        (
            DatasetContext("TCS", "15m", "Asia/Kolkata"),
            candle_at(timestamp, close=102.0),
        ),
        (
            DatasetContext("RELIANCE", "5m", "Asia/Kolkata"),
            candle_at(timestamp, close=103.0),
        ),
        (
            DatasetContext("RELIANCE", "15m", "UTC"),
            candle_at(timestamp, close=104.0),
        ),
    ]

    for context, candle in datasets:
        store.save(context, [candle])

    for context, expected_candle in datasets:
        assert store.load(context, start=timestamp, end=timestamp) == [
            expected_candle
        ]


def test_sqlite_candle_store_load_range_is_inclusive(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    start = datetime(2026, 1, 2, 9, 30)
    end = datetime(2026, 1, 2, 10, 0)
    candles = [
        candle_at(start - timedelta(minutes=15)),
        candle_at(start),
        candle_at(start + timedelta(minutes=15)),
        candle_at(end),
        candle_at(end + timedelta(minutes=15)),
    ]

    store.save(DATASET_CONTEXT, candles)

    assert store.load(DATASET_CONTEXT, start=start, end=end) == candles[1:4]


def test_sqlite_candle_store_loads_in_chronological_order(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    expected = [
        candle_at(datetime(2026, 1, 2, 9, 15)),
        candle_at(datetime(2026, 1, 2, 9, 30)),
        candle_at(datetime(2026, 1, 2, 9, 45)),
    ]

    store.save(DATASET_CONTEXT, [expected[2], expected[0], expected[1]])

    assert store.load(
        DATASET_CONTEXT,
        start=expected[0].timestamp,
        end=expected[-1].timestamp,
    ) == expected


def test_sqlite_candle_store_exact_duplicate_save_is_idempotent(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    candle = candle_at(datetime(2026, 1, 2, 9, 15))

    store.save(DATASET_CONTEXT, [candle])
    store.save(DATASET_CONTEXT, [candle])

    assert store.load(
        DATASET_CONTEXT,
        start=candle.timestamp,
        end=candle.timestamp,
    ) == [candle]


def test_sqlite_candle_store_rejects_conflicting_duplicate(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    timestamp = datetime(2026, 1, 2, 9, 15)
    original = candle_at(timestamp, close=100.5)
    conflicting = candle_at(timestamp, close=101.5)
    store.save(DATASET_CONTEXT, [original])

    with pytest.raises(ValueError, match="conflict"):
        store.save(DATASET_CONTEXT, [conflicting])

    assert store.load(DATASET_CONTEXT, start=timestamp, end=timestamp) == [
        original
    ]


def test_sqlite_candle_store_batch_write_is_atomic(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    existing_timestamp = datetime(2026, 1, 2, 9, 15)
    existing = candle_at(existing_timestamp, close=100.5)
    new_candle = candle_at(datetime(2026, 1, 2, 9, 30), close=101.0)
    conflicting = candle_at(existing_timestamp, close=101.5)
    store.save(DATASET_CONTEXT, [existing])

    with pytest.raises(ValueError, match="conflict"):
        store.save(DATASET_CONTEXT, [new_candle, conflicting])

    assert store.load(
        DATASET_CONTEXT,
        start=existing_timestamp,
        end=new_candle.timestamp,
    ) == [existing]


def test_sqlite_candle_store_persists_idempotent_coverage_by_dataset(
    tmp_path,
):
    database_path = tmp_path / "candles.sqlite"
    first_context = DATASET_CONTEXT
    second_context = DatasetContext(
        symbol="TCS",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )
    first_coverage = TimeRange(
        datetime(2026, 1, 2, 9, 0),
        datetime(2026, 1, 2, 10, 0),
    )
    second_coverage = TimeRange(
        datetime(2026, 1, 2, 10, 0),
        datetime(2026, 1, 2, 11, 0),
    )
    first_store = SQLiteCandleStore(database_path)

    first_store.save_retrieval(first_context, [], [first_coverage])
    first_store.save_retrieval(first_context, [], [first_coverage])
    first_store.save_retrieval(second_context, [], [second_coverage])

    second_store = SQLiteCandleStore(database_path)

    assert second_store.load_coverage(first_context) == [first_coverage]
    assert second_store.load_coverage(second_context) == [second_coverage]


def test_sqlite_candle_store_retrieval_write_is_atomic(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    existing_timestamp = datetime(2026, 1, 2, 9, 15)
    existing = candle_at(existing_timestamp, close=100.5)
    new_candle = candle_at(datetime(2026, 1, 2, 9, 30), close=101.0)
    conflicting = candle_at(existing_timestamp, close=101.5)
    coverage = TimeRange(
        datetime(2026, 1, 2, 9, 0),
        datetime(2026, 1, 2, 10, 0),
    )
    store.save(DATASET_CONTEXT, [existing])

    with pytest.raises(ValueError, match="conflict"):
        store.save_retrieval(
            DATASET_CONTEXT,
            [new_candle, conflicting],
            [coverage],
        )

    assert store.load(
        DATASET_CONTEXT,
        start=existing_timestamp,
        end=new_candle.timestamp,
    ) == [existing]
    assert store.load_coverage(DATASET_CONTEXT) == []


def test_sqlite_candle_store_compares_aware_offsets_chronologically(
    tmp_path,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    india = timezone(timedelta(hours=5, minutes=30))
    first = candle_at(
        datetime(2026, 1, 2, 9, 0, tzinfo=india),
        close=101.0,
    )
    second = candle_at(
        datetime(2026, 1, 2, 4, 0, tzinfo=timezone.utc),
        close=102.0,
    )
    store.save(DATASET_CONTEXT, [second, first])

    loaded = store.load(
        DATASET_CONTEXT,
        start=datetime(2026, 1, 2, 3, 0, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, 4, 30, tzinfo=timezone.utc),
    )

    assert loaded == [first, second]
    assert loaded[0].timestamp.utcoffset() == india.utcoffset(None)
    assert loaded[1].timestamp.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    ("stored_timestamp", "start", "end"),
    [
        pytest.param(
            datetime(2026, 1, 2, 9, 15, tzinfo=timezone.utc),
            datetime(2026, 1, 2, 9, 0),
            datetime(2026, 1, 2, 10, 0),
            id="naive-bounds-aware-storage",
        ),
        pytest.param(
            datetime(2026, 1, 2, 9, 15),
            datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
            id="aware-bounds-naive-storage",
        ),
    ],
)
def test_sqlite_candle_store_rejects_incompatible_stored_awareness(
    tmp_path,
    stored_timestamp,
    start,
    end,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    store.save(DATASET_CONTEXT, [candle_at(stored_timestamp)])

    with pytest.raises(ValueError, match="timezone"):
        store.load(DATASET_CONTEXT, start=start, end=end)


def test_sqlite_candle_store_rejects_mixed_request_bound_awareness(
    tmp_path,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")

    with pytest.raises(ValueError, match="timezone"):
        store.load(
            DATASET_CONTEXT,
            start=datetime(2026, 1, 2, 9, 0),
            end=datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
        )


def test_sqlite_candle_store_orders_coverage_by_datetime_semantics(
    tmp_path,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    india = timezone(timedelta(hours=5, minutes=30))
    earlier = TimeRange(
        datetime(2026, 1, 2, 9, 0, tzinfo=india),
        datetime(2026, 1, 2, 9, 15, tzinfo=india),
    )
    later = TimeRange(
        datetime(2026, 1, 2, 4, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 2, 4, 15, tzinfo=timezone.utc),
    )

    store.save_retrieval(DATASET_CONTEXT, [], [later, earlier])

    assert store.load_coverage(DATASET_CONTEXT) == [earlier, later]


@pytest.mark.parametrize(
    ("stored_timestamp", "incoming_timestamp"),
    [
        pytest.param(
            datetime(
                2026,
                1,
                2,
                9,
                15,
                tzinfo=timezone(timedelta(hours=5, minutes=30)),
            ),
            datetime(2026, 1, 2, 3, 45, tzinfo=timezone.utc),
            id="india-then-utc",
        ),
        pytest.param(
            datetime(2026, 1, 2, 3, 45, tzinfo=timezone.utc),
            datetime(
                2026,
                1,
                2,
                9,
                15,
                tzinfo=timezone(timedelta(hours=5, minutes=30)),
            ),
            id="utc-then-india",
        ),
    ],
)
def test_sqlite_candle_store_equivalent_aware_offsets_are_idempotent(
    tmp_path,
    stored_timestamp,
    incoming_timestamp,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    stored = candle_at(stored_timestamp)
    equivalent = candle_at(incoming_timestamp)

    store.save(DATASET_CONTEXT, [stored])
    store.save(DATASET_CONTEXT, [equivalent])

    loaded = store.load(
        DATASET_CONTEXT,
        start=datetime(2026, 1, 2, 3, 30, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, 4, 0, tzinfo=timezone.utc),
    )
    assert loaded == [stored]
    assert loaded[0].timestamp.isoformat() == stored_timestamp.isoformat()


def test_sqlite_candle_store_rejects_cross_offset_conflict(tmp_path):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    india = timezone(timedelta(hours=5, minutes=30))
    stored = candle_at(
        datetime(2026, 1, 2, 9, 15, tzinfo=india),
        close=100.5,
    )
    conflicting = candle_at(
        datetime(2026, 1, 2, 3, 45, tzinfo=timezone.utc),
        close=101.5,
    )
    store.save(DATASET_CONTEXT, [stored])

    with pytest.raises(ValueError, match="conflict"):
        store.save(DATASET_CONTEXT, [conflicting])

    assert store.load(
        DATASET_CONTEXT,
        start=datetime(2026, 1, 2, 3, 30, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, 4, 0, tzinfo=timezone.utc),
    ) == [stored]


def test_sqlite_candle_store_rolls_back_cross_offset_retrieval_conflict(
    tmp_path,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    india = timezone(timedelta(hours=5, minutes=30))
    existing = candle_at(
        datetime(2026, 1, 2, 9, 30, tzinfo=india),
        close=100.5,
    )
    new_candle = candle_at(
        datetime(2026, 1, 2, 3, 45, tzinfo=timezone.utc),
        close=101.0,
    )
    conflicting = candle_at(
        datetime(2026, 1, 2, 4, 0, tzinfo=timezone.utc),
        close=102.0,
    )
    coverage = TimeRange(
        datetime(2026, 1, 2, 3, 30, tzinfo=timezone.utc),
        datetime(2026, 1, 2, 4, 30, tzinfo=timezone.utc),
    )
    store.save(DATASET_CONTEXT, [existing])

    with pytest.raises(ValueError, match="conflict"):
        store.save_retrieval(
            DATASET_CONTEXT,
            [new_candle, conflicting],
            [coverage],
        )

    assert store.load(
        DATASET_CONTEXT,
        start=coverage.start,
        end=coverage.end,
    ) == [existing]
    assert store.load_coverage(DATASET_CONTEXT) == []


@pytest.mark.parametrize(
    ("existing_timestamp", "incoming_timestamp"),
    [
        pytest.param(
            datetime(2026, 1, 2, 9, 15),
            datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc),
            id="naive-then-aware",
        ),
        pytest.param(
            datetime(2026, 1, 2, 9, 15, tzinfo=timezone.utc),
            datetime(2026, 1, 2, 9, 30),
            id="aware-then-naive",
        ),
    ],
)
def test_sqlite_candle_store_write_awareness_rejects_candle_mismatch(
    tmp_path,
    existing_timestamp,
    incoming_timestamp,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    existing = candle_at(existing_timestamp)
    store.save(DATASET_CONTEXT, [existing])

    with pytest.raises(ValueError, match="timezone|awareness"):
        store.save(DATASET_CONTEXT, [candle_at(incoming_timestamp)])

    assert store.load(
        DATASET_CONTEXT,
        start=existing_timestamp,
        end=existing_timestamp,
    ) == [existing]


def test_sqlite_candle_store_write_awareness_rejects_mixed_batch_atomically(
    tmp_path,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    naive = candle_at(datetime(2026, 1, 2, 9, 15))
    aware = candle_at(
        datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc)
    )

    with pytest.raises(ValueError, match="timezone|awareness"):
        store.save(DATASET_CONTEXT, [naive, aware])

    assert store.load(
        DATASET_CONTEXT,
        start=datetime(2026, 1, 2, 9, 0),
        end=datetime(2026, 1, 2, 10, 0),
    ) == []


@pytest.mark.parametrize(
    ("candle_timestamp", "coverage"),
    [
        pytest.param(
            datetime(2026, 1, 2, 9, 15),
            TimeRange(
                datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
            ),
            id="naive-candle-aware-coverage",
        ),
        pytest.param(
            datetime(2026, 1, 2, 9, 15, tzinfo=timezone.utc),
            TimeRange(
                datetime(2026, 1, 2, 9, 0),
                datetime(2026, 1, 2, 10, 0),
            ),
            id="aware-candle-naive-coverage",
        ),
    ],
)
def test_sqlite_candle_store_write_awareness_rejects_coverage_after_candle(
    tmp_path,
    candle_timestamp,
    coverage,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    existing = candle_at(candle_timestamp)
    store.save(DATASET_CONTEXT, [existing])

    with pytest.raises(ValueError, match="timezone|awareness"):
        store.save_retrieval(DATASET_CONTEXT, [], [coverage])

    assert store.load_coverage(DATASET_CONTEXT) == []
    assert store.load(
        DATASET_CONTEXT,
        start=candle_timestamp,
        end=candle_timestamp,
    ) == [existing]


@pytest.mark.parametrize(
    ("existing_coverage", "incoming_coverage"),
    [
        pytest.param(
            TimeRange(
                datetime(2026, 1, 2, 9, 0),
                datetime(2026, 1, 2, 9, 30),
            ),
            TimeRange(
                datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc),
                datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
            ),
            id="naive-then-aware",
        ),
        pytest.param(
            TimeRange(
                datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc),
            ),
            TimeRange(
                datetime(2026, 1, 2, 9, 30),
                datetime(2026, 1, 2, 10, 0),
            ),
            id="aware-then-naive",
        ),
    ],
)
def test_sqlite_candle_store_write_awareness_rejects_coverage_mismatch(
    tmp_path,
    existing_coverage,
    incoming_coverage,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    store.save_retrieval(DATASET_CONTEXT, [], [existing_coverage])

    with pytest.raises(ValueError, match="timezone|awareness"):
        store.save_retrieval(DATASET_CONTEXT, [], [incoming_coverage])

    assert store.load_coverage(DATASET_CONTEXT) == [existing_coverage]


def test_sqlite_candle_store_write_awareness_rejects_candle_coverage_mismatch(
    tmp_path,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    candle = candle_at(datetime(2026, 1, 2, 9, 15))
    aware_coverage = TimeRange(
        datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc),
        datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(ValueError, match="timezone|awareness"):
        store.save_retrieval(
            DATASET_CONTEXT,
            [candle],
            [aware_coverage],
        )

    assert store.load(
        DATASET_CONTEXT,
        start=datetime(2026, 1, 2, 9, 0),
        end=datetime(2026, 1, 2, 10, 0),
    ) == []
    assert store.load_coverage(DATASET_CONTEXT) == []


def test_sqlite_candle_store_write_awareness_accepts_different_aware_offsets(
    tmp_path,
):
    store = SQLiteCandleStore(tmp_path / "candles.sqlite")
    india = timezone(timedelta(hours=5, minutes=30))
    candle = candle_at(datetime(2026, 1, 2, 9, 15, tzinfo=india))
    utc_coverage = TimeRange(
        datetime(2026, 1, 2, 3, 30, tzinfo=timezone.utc),
        datetime(2026, 1, 2, 4, 0, tzinfo=timezone.utc),
    )

    store.save_retrieval(DATASET_CONTEXT, [candle], [utc_coverage])

    assert store.load(
        DATASET_CONTEXT,
        start=utc_coverage.start,
        end=utc_coverage.end,
    ) == [candle]
    assert store.load_coverage(DATASET_CONTEXT) == [utc_coverage]

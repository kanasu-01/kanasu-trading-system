from datetime import datetime, timedelta, timezone

import pytest

from core.entities.candle import Candle
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

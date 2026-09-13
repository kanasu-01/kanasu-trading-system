from datetime import datetime, timedelta, timezone

import pytest

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries


def candle_at(timestamp: datetime) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000.0,
    )


def test_empty_candle_series_is_valid():
    series = CandleSeries()

    assert len(series) == 0
    assert list(series) == []


def test_first_candle_can_be_appended():
    candle = candle_at(datetime(2026, 1, 2, 9, 15))
    series = CandleSeries()

    series.append(candle)

    assert len(series) == 1
    assert series[0] == candle


def test_strictly_increasing_naive_timestamps_are_accepted():
    candles = [
        candle_at(datetime(2026, 1, 2, 9, 15)),
        candle_at(datetime(2026, 1, 2, 9, 30)),
        candle_at(datetime(2026, 1, 2, 9, 45)),
    ]
    series = CandleSeries()

    for candle in candles:
        series.append(candle)

    assert list(series) == candles


def test_append_rejects_duplicate_timestamp():
    timestamp = datetime(2026, 1, 2, 9, 15)
    series = CandleSeries([candle_at(timestamp)])

    with pytest.raises(ValueError, match="duplicate"):
        series.append(candle_at(timestamp))


def test_append_rejects_older_timestamp():
    series = CandleSeries([candle_at(datetime(2026, 1, 2, 9, 30))])

    with pytest.raises(ValueError, match="chronological|older"):
        series.append(candle_at(datetime(2026, 1, 2, 9, 15)))


def test_append_rejects_duplicate_timestamp_seen_earlier_in_series():
    series = CandleSeries(
        [
            candle_at(datetime(2026, 1, 2, 9, 15)),
            candle_at(datetime(2026, 1, 2, 9, 20)),
            candle_at(datetime(2026, 1, 2, 9, 30)),
            candle_at(datetime(2026, 1, 2, 9, 45)),
        ]
    )

    with pytest.raises(ValueError, match="duplicate"):
        series.append(candle_at(datetime(2026, 1, 2, 9, 20)))


def test_append_rejects_never_seen_delayed_timestamp_as_out_of_order():
    series = CandleSeries(
        [
            candle_at(datetime(2026, 1, 2, 9, 15)),
            candle_at(datetime(2026, 1, 2, 9, 30)),
            candle_at(datetime(2026, 1, 2, 9, 45)),
        ]
    )

    with pytest.raises(ValueError, match="chronological|older|out-of-order"):
        series.append(candle_at(datetime(2026, 1, 2, 9, 20)))


def test_constructor_rejects_duplicate_timestamps():
    timestamp = datetime(2026, 1, 2, 9, 15)

    with pytest.raises(ValueError, match="duplicate"):
        CandleSeries([candle_at(timestamp), candle_at(timestamp)])


def test_constructor_rejects_out_of_order_timestamps():
    candles = [
        candle_at(datetime(2026, 1, 2, 9, 30)),
        candle_at(datetime(2026, 1, 2, 9, 15)),
    ]

    with pytest.raises(ValueError, match="chronological|older"):
        CandleSeries(candles)


def test_strictly_increasing_timezone_aware_timestamps_are_accepted():
    start = datetime(2026, 1, 2, 9, 15, tzinfo=timezone.utc)
    candles = [
        candle_at(start),
        candle_at(start + timedelta(minutes=15)),
        candle_at(start + timedelta(minutes=30)),
    ]

    series = CandleSeries(candles)

    assert list(series) == candles


def test_append_rejects_naive_then_aware_timestamp():
    series = CandleSeries([candle_at(datetime(2026, 1, 2, 9, 15))])
    aware_timestamp = datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="timezone"):
        series.append(candle_at(aware_timestamp))


def test_append_rejects_aware_then_naive_timestamp():
    aware_timestamp = datetime(2026, 1, 2, 9, 15, tzinfo=timezone.utc)
    series = CandleSeries([candle_at(aware_timestamp)])

    with pytest.raises(ValueError, match="timezone"):
        series.append(candle_at(datetime(2026, 1, 2, 9, 30)))

from datetime import datetime, time, timedelta, timezone

import pytest

from core.market_data.live_candle_builder import LiveCandleBuilder
from core.market_data.live_market_update import LiveMarketUpdate


IST = timezone(timedelta(hours=5, minutes=30))
SESSION_START = time(9, 15)


def _ts(hour: int, minute: int, second: int = 0) -> datetime:
    return datetime(
        2026,
        1,
        1,
        hour,
        minute,
        second,
        tzinfo=IST,
    )


def _update(
    hour: int,
    minute: int,
    price: float,
    cumulative_volume: float,
    sequence: int,
    second: int = 0,
) -> LiveMarketUpdate:
    return LiveMarketUpdate(
        timestamp=_ts(hour, minute, second),
        price=price,
        cumulative_volume=cumulative_volume,
        sequence=sequence,
    )


def test_live_market_update_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        LiveMarketUpdate(
            timestamp=datetime(2026, 1, 1, 9, 15),
            price=100.0,
            cumulative_volume=10.0,
            sequence=1,
        )


@pytest.mark.parametrize(
    ("price", "cumulative_volume"),
    [
        (0.0, 10.0),
        (100.0, -1.0),
    ],
)
def test_live_market_update_rejects_invalid_numeric_values(
    price: float,
    cumulative_volume: float,
) -> None:
    with pytest.raises(ValueError):
        LiveMarketUpdate(
            timestamp=_ts(9, 15),
            price=price,
            cumulative_volume=cumulative_volume,
            sequence=1,
        )


def test_daily_timeframe_is_deferred() -> None:
    with pytest.raises(ValueError, match="unsupported live timeframe"):
        LiveCandleBuilder(
            timeframe="1d",
            session_start=SESSION_START,
        )


def test_cold_start_partial_is_discarded_then_full_candle_emits() -> None:
    builder = LiveCandleBuilder("15m", SESSION_START)

    assert builder.on_update(_update(10, 7, 100.0, 100.0, 1)) is None
    assert builder.on_update(_update(10, 14, 101.0, 120.0, 2)) is None

    # 10:15 belongs to the new interval. The earlier partial candle is dropped.
    assert builder.on_update(_update(10, 15, 102.0, 130.0, 3)) is None
    assert builder.on_update(_update(10, 20, 105.0, 150.0, 4)) is None
    assert builder.on_update(_update(10, 29, 99.0, 180.0, 5)) is None

    candle = builder.on_update(_update(10, 30, 103.0, 190.0, 6))

    assert candle is not None
    assert candle.timestamp == _ts(10, 15)
    assert candle.open == 102.0
    assert candle.high == 105.0
    assert candle.low == 99.0
    assert candle.close == 99.0
    assert candle.volume == pytest.approx(60.0)


def test_thirty_minute_buckets_are_session_anchored() -> None:
    builder = LiveCandleBuilder("30m", SESSION_START)

    assert builder.on_update(_update(9, 20, 100.0, 100.0, 1)) is None

    # Session anchoring gives 09:15-09:45, then 09:45-10:15.
    assert builder.on_update(_update(9, 45, 101.0, 110.0, 2)) is None
    assert builder.on_update(_update(10, 0, 102.0, 125.0, 3)) is None

    candle = builder.advance_time(_ts(10, 15))

    assert candle is not None
    assert candle.timestamp == _ts(9, 45)
    assert candle.volume == pytest.approx(25.0)


def test_advance_time_does_not_create_synthetic_candles() -> None:
    builder = LiveCandleBuilder("15m", SESSION_START)

    assert builder.on_update(_update(10, 7, 100.0, 100.0, 1)) is None
    assert builder.on_update(_update(10, 15, 101.0, 110.0, 2)) is None

    candle = builder.advance_time(_ts(10, 30))
    assert candle is not None
    assert candle.timestamp == _ts(10, 15)

    assert builder.advance_time(_ts(10, 45)) is None
    assert builder.advance_time(_ts(11, 0)) is None


def test_identical_sequence_retransmission_is_ignored() -> None:
    builder = LiveCandleBuilder("15m", SESSION_START)
    update = _update(10, 7, 100.0, 100.0, 1)

    assert builder.on_update(update) is None
    assert builder.on_update(update) is None

    assert builder.on_update(_update(10, 15, 101.0, 110.0, 2)) is None
    candle = builder.advance_time(_ts(10, 30))

    assert candle is not None
    assert candle.volume == pytest.approx(10.0)


def test_conflicting_same_sequence_is_rejected() -> None:
    builder = LiveCandleBuilder("15m", SESSION_START)

    assert builder.on_update(_update(10, 7, 100.0, 100.0, 1)) is None

    with pytest.raises(ValueError, match="conflicting live update"):
        builder.on_update(_update(10, 7, 101.0, 100.0, 1))


def test_lower_sequence_is_rejected() -> None:
    builder = LiveCandleBuilder("15m", SESSION_START)

    assert builder.on_update(_update(10, 7, 100.0, 100.0, 2)) is None

    with pytest.raises(ValueError, match="sequence is older"):
        builder.on_update(_update(10, 8, 101.0, 110.0, 1))


def test_backwards_event_time_is_rejected() -> None:
    builder = LiveCandleBuilder("15m", SESSION_START)

    assert builder.on_update(_update(10, 7, 100.0, 100.0, 1)) is None

    with pytest.raises(ValueError, match="event time is older"):
        builder.on_update(_update(10, 6, 101.0, 110.0, 2))


def test_cumulative_volume_decrease_is_rejected() -> None:
    builder = LiveCandleBuilder("15m", SESSION_START)

    assert builder.on_update(_update(10, 7, 100.0, 100.0, 1)) is None

    with pytest.raises(ValueError, match="cannot decrease"):
        builder.on_update(_update(10, 8, 101.0, 99.0, 2))


def test_equal_event_time_with_higher_sequence_is_valid() -> None:
    builder = LiveCandleBuilder("1m", SESSION_START)

    assert builder.on_update(_update(9, 15, 100.0, 10.0, 1)) is None
    assert builder.on_update(_update(9, 15, 101.0, 15.0, 2)) is None

    candle = builder.advance_time(_ts(9, 16))

    assert candle is not None
    assert candle.timestamp == _ts(9, 15)
    assert candle.open == 100.0
    assert candle.high == 101.0
    assert candle.low == 100.0
    assert candle.close == 101.0
    assert candle.volume == pytest.approx(15.0)


def test_update_before_session_start_is_rejected() -> None:
    builder = LiveCandleBuilder("15m", SESSION_START)

    with pytest.raises(ValueError, match="before the trading session"):
        builder.on_update(_update(9, 14, 100.0, 10.0, 1))


def test_first_update_on_later_boundary_is_full_candle() -> None:
    builder = LiveCandleBuilder("15m", SESSION_START)

    assert builder.on_update(_update(10, 15, 100.0, 500.0, 1)) is None
    assert builder.on_update(_update(10, 20, 103.0, 520.0, 2)) is None
    assert builder.on_update(_update(10, 29, 99.0, 550.0, 3)) is None

    candle = builder.advance_time(_ts(10, 30))

    assert candle is not None
    assert candle.timestamp == _ts(10, 15)
    assert candle.open == 100.0
    assert candle.high == 103.0
    assert candle.low == 99.0
    assert candle.close == 99.0
    assert candle.volume == pytest.approx(50.0)

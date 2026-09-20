from datetime import datetime, time, timedelta, timezone

import pytest

from core.market_data.live_candle_pipeline import LiveCandlePipeline
from core.market_data.live_market_update import LiveMarketUpdate


IST = timezone(timedelta(hours=5, minutes=30))
SESSION_START = time(9, 15)


def _ts(
    hour: int,
    minute: int,
) -> datetime:
    return datetime(
        2026,
        1,
        2,
        hour,
        minute,
        tzinfo=IST,
    )


def _update(
    hour: int,
    minute: int,
    price: float,
    cumulative_volume: float,
    sequence: int,
) -> LiveMarketUpdate:
    return LiveMarketUpdate(
        timestamp=_ts(hour, minute),
        price=price,
        cumulative_volume=cumulative_volume,
        sequence=sequence,
    )


def test_initial_connection_emits_completed_candle() -> None:
    pipeline = LiveCandlePipeline(
        timeframe="15m",
        session_start=SESSION_START,
    )
    pipeline.begin_connection()

    assert pipeline.on_update(
        _update(10, 15, 100.0, 500.0, 1)
    ) is None
    assert pipeline.on_update(
        _update(10, 20, 105.0, 520.0, 2)
    ) is None

    candle = pipeline.on_update(
        _update(10, 30, 103.0, 530.0, 3)
    )

    assert candle is not None
    assert candle.timestamp == _ts(10, 15)
    assert candle.open == 100.0
    assert candle.high == 105.0
    assert candle.low == 100.0
    assert candle.close == 105.0
    assert candle.volume == pytest.approx(20.0)


def test_disconnect_discards_active_interval_and_allows_sequence_restart() -> None:
    pipeline = LiveCandlePipeline(
        timeframe="15m",
        session_start=SESSION_START,
    )
    pipeline.begin_connection()

    assert pipeline.on_update(
        _update(10, 15, 100.0, 500.0, 100)
    ) is None
    assert pipeline.on_update(
        _update(10, 20, 101.0, 520.0, 101)
    ) is None

    pipeline.mark_disconnected()
    pipeline.begin_connection()

    # Sequence restarts at 1 in the new provider connection epoch.
    assert pipeline.on_update(
        _update(10, 25, 102.0, 540.0, 1)
    ) is None

    # The interrupted 10:15 candle is discarded.
    assert pipeline.on_update(
        _update(10, 30, 103.0, 550.0, 2)
    ) is None

    assert pipeline.on_update(
        _update(10, 35, 104.0, 560.0, 3)
    ) is None

    candle = pipeline.on_update(
        _update(10, 45, 105.0, 570.0, 4)
    )

    assert candle is not None
    assert candle.timestamp == _ts(10, 30)
    assert candle.open == 103.0
    assert candle.close == 104.0
    assert candle.volume == pytest.approx(20.0)


def test_first_reconnect_update_on_boundary_is_still_partial() -> None:
    pipeline = LiveCandlePipeline(
        timeframe="15m",
        session_start=SESSION_START,
    )
    pipeline.begin_connection()

    assert pipeline.on_update(
        _update(10, 15, 100.0, 500.0, 50)
    ) is None

    pipeline.mark_disconnected()
    pipeline.begin_connection()

    # Even on an exact boundary, the first reconnect interval is not valid.
    assert pipeline.on_update(
        _update(10, 30, 102.0, 550.0, 1)
    ) is None
    assert pipeline.on_update(
        _update(10, 40, 103.0, 560.0, 2)
    ) is None

    # 10:30-10:45 is discarded.
    assert pipeline.on_update(
        _update(10, 45, 104.0, 570.0, 3)
    ) is None

    assert pipeline.on_update(
        _update(10, 50, 105.0, 580.0, 4)
    ) is None

    candle = pipeline.on_update(
        _update(11, 0, 106.0, 590.0, 5)
    )

    assert candle is not None
    assert candle.timestamp == _ts(10, 45)
    assert candle.open == 104.0
    assert candle.close == 105.0
    assert candle.volume == pytest.approx(20.0)


def test_reconnect_rejects_stale_event_time() -> None:
    pipeline = LiveCandlePipeline(
        timeframe="15m",
        session_start=SESSION_START,
    )
    pipeline.begin_connection()

    assert pipeline.on_update(
        _update(10, 20, 100.0, 500.0, 20)
    ) is None

    pipeline.mark_disconnected()
    pipeline.begin_connection()

    with pytest.raises(
        ValueError,
        match="older than the current watermark",
    ):
        pipeline.on_update(
            _update(10, 19, 101.0, 510.0, 1)
        )


def test_reconnect_rejects_cumulative_volume_regression() -> None:
    pipeline = LiveCandlePipeline(
        timeframe="15m",
        session_start=SESSION_START,
    )
    pipeline.begin_connection()

    assert pipeline.on_update(
        _update(10, 20, 100.0, 500.0, 20)
    ) is None

    pipeline.mark_disconnected()
    pipeline.begin_connection()

    with pytest.raises(
        ValueError,
        match="cannot decrease across connections",
    ):
        pipeline.on_update(
            _update(10, 21, 101.0, 499.0, 1)
        )


def test_latest_update_retransmission_after_reconnect_is_idempotent() -> None:
    pipeline = LiveCandlePipeline(
        timeframe="15m",
        session_start=SESSION_START,
    )
    pipeline.begin_connection()

    latest = _update(
        10,
        20,
        100.0,
        500.0,
        100,
    )

    assert pipeline.on_update(latest) is None

    pipeline.mark_disconnected()
    pipeline.begin_connection()

    assert pipeline.on_update(latest) is None

    # A restarted source sequence is valid in the new epoch.
    assert pipeline.on_update(
        _update(10, 21, 101.0, 510.0, 1)
    ) is None


def test_disconnected_clock_never_emits_and_advances_watermark() -> None:
    pipeline = LiveCandlePipeline(
        timeframe="15m",
        session_start=SESSION_START,
    )
    pipeline.begin_connection()

    assert pipeline.on_update(
        _update(10, 15, 100.0, 500.0, 1)
    ) is None
    assert pipeline.on_update(
        _update(10, 20, 101.0, 520.0, 2)
    ) is None

    pipeline.mark_disconnected()

    # The interrupted candle must not be completed by the wall clock.
    assert pipeline.advance_time(_ts(10, 30)) is None

    pipeline.begin_connection()

    with pytest.raises(
        ValueError,
        match="older than the current watermark",
    ):
        pipeline.on_update(
            _update(10, 29, 102.0, 530.0, 1)
        )

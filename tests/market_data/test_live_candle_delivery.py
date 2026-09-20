from datetime import datetime, timedelta, timezone

import pytest

from core.entities.candle import Candle
from core.market_data.completed_candle_delivery import CompletedCandleDelivery
from core.market_data.live_candle_feed import LiveCandleFeed
from core.market_data.mock_live_feed import MockLiveFeed


BASE_TIME = datetime(2026, 1, 1, 9, 15, tzinfo=timezone.utc)


def _candle(timestamp: datetime, close: float = 100.0) -> Candle:
    open_price = 100.0
    return Candle(
        timestamp=timestamp,
        open=open_price,
        high=max(open_price, close) + 1.0,
        low=min(open_price, close) - 1.0,
        close=close,
        volume=10.0,
    )


def test_identical_completed_candle_is_idempotent() -> None:
    delivery = CompletedCandleDelivery()
    candle = _candle(BASE_TIME)

    assert delivery.accept(candle) is True
    assert delivery.accept(candle) is False


def test_identical_delayed_retransmission_is_idempotent() -> None:
    delivery = CompletedCandleDelivery()
    first = _candle(BASE_TIME)
    second = _candle(BASE_TIME + timedelta(minutes=15), close=101.0)

    assert delivery.accept(first) is True
    assert delivery.accept(second) is True
    assert delivery.accept(first) is False


def test_conflicting_completed_candle_is_rejected() -> None:
    delivery = CompletedCandleDelivery()
    delivery.accept(_candle(BASE_TIME))

    with pytest.raises(ValueError, match="conflicting completed candle"):
        delivery.accept(_candle(BASE_TIME, close=101.0))


def test_unseen_out_of_order_completed_candle_is_rejected() -> None:
    delivery = CompletedCandleDelivery()
    delivery.accept(_candle(BASE_TIME + timedelta(minutes=15)))

    with pytest.raises(ValueError, match="older than the latest"):
        delivery.accept(_candle(BASE_TIME))


def test_timezone_awareness_must_remain_consistent() -> None:
    delivery = CompletedCandleDelivery()
    delivery.accept(_candle(BASE_TIME))

    naive_timestamp = (BASE_TIME + timedelta(minutes=15)).replace(tzinfo=None)

    with pytest.raises(ValueError, match="timezone awareness must match"):
        delivery.accept(_candle(naive_timestamp))


def test_mock_live_feed_delivers_unique_completed_candles_once() -> None:
    first = _candle(BASE_TIME)
    second = _candle(BASE_TIME + timedelta(minutes=15), close=101.0)
    feed = MockLiveFeed(
        candles=[first, first, second],
        interval_seconds=0.0,
    )
    delivered: list[Candle] = []

    assert isinstance(feed, LiveCandleFeed)

    feed.subscribe(delivered.append)

    assert delivered == [first, second]


def test_mock_live_feed_does_not_redeliver_across_subscriptions() -> None:
    first = _candle(BASE_TIME)
    second = _candle(BASE_TIME + timedelta(minutes=15), close=101.0)
    feed = MockLiveFeed(
        candles=[first, second],
        interval_seconds=0.0,
    )
    delivered: list[Candle] = []

    feed.subscribe(delivered.append)
    feed.subscribe(delivered.append)

    assert delivered == [first, second]

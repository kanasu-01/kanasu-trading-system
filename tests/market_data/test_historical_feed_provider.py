from datetime import datetime, timedelta, timezone

import pytest

from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_feed import HistoricalFeed
from core.market_data.historical_feed_provider import HistoricalFeedProvider
from core.runtime.dataset_context import DatasetContext


CONTEXT = DatasetContext(
    symbol="RELIANCE",
    timeframe="15m",
    timezone="Asia/Kolkata",
)
START = datetime(2026, 1, 2, 9, 15)


def candle_at(
    timestamp: datetime,
    *,
    close: float = 100.5,
) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=100.0,
        high=101.0,
        low=99.0,
        close=close,
        volume=1000.0,
    )


class FakeHistoricalBroker:
    def __init__(self, outcomes, *, max_days: int = 1):
        self.outcomes = list(outcomes)
        self.max_days = max_days
        self.requests = []

    def get_historical_limits(self) -> dict:
        return {"15m": self.max_days}

    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        self.requests.append((symbol, timeframe, start, end))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return list(outcome)


def provider_for(outcomes, *, max_days: int = 1):
    broker = FakeHistoricalBroker(outcomes, max_days=max_days)
    feed = HistoricalFeed(broker=broker, request_delay_sec=0)
    return HistoricalFeedProvider(feed), broker


def test_successful_feed_returns_canonical_candles_and_full_coverage():
    request = TimeRange(START, START + timedelta(hours=1))
    candles = [candle_at(START), candle_at(START + timedelta(minutes=30))]
    provider, broker = provider_for([candles])

    result = provider.fetch(CONTEXT, request)

    assert result.candles == tuple(candles)
    assert result.coverage == (request,)
    assert broker.requests == [
        (CONTEXT.symbol, CONTEXT.timeframe, request.start, request.end)
    ]


def test_successful_empty_feed_is_confirmed_empty_full_coverage():
    request = TimeRange(START, START + timedelta(hours=1))
    provider, _ = provider_for([[]])

    result = provider.fetch(CONTEXT, request)

    assert result.candles == ()
    assert result.coverage == (request,)


def test_sparse_feed_still_returns_full_request_coverage():
    request = TimeRange(START, START + timedelta(hours=8))
    sparse = [candle_at(START + timedelta(hours=4))]
    provider, _ = provider_for([sparse])

    result = provider.fetch(CONTEXT, request)

    assert result.candles == tuple(sparse)
    assert result.coverage == (request,)


def test_candle_exactly_at_request_start_is_included():
    request = TimeRange(START, START + timedelta(hours=1))
    start_candle = candle_at(request.start)
    provider, _ = provider_for([[start_candle]])

    assert provider.fetch(CONTEXT, request).candles == (start_candle,)


def test_candle_exactly_at_request_end_is_excluded():
    request = TimeRange(START, START + timedelta(hours=1))
    inside = candle_at(START + timedelta(minutes=30))
    exact_end = candle_at(request.end)
    provider, _ = provider_for([[inside, exact_end]])

    assert provider.fetch(CONTEXT, request).candles == (inside,)


def test_candle_before_request_is_rejected_instead_of_clipped():
    request = TimeRange(START, START + timedelta(hours=1))
    provider, _ = provider_for(
        [[candle_at(START - timedelta(minutes=15))]]
    )

    with pytest.raises(ValueError, match="within the requested gap"):
        provider.fetch(CONTEXT, request)


def test_candle_after_request_is_rejected_instead_of_clipped():
    request = TimeRange(START, START + timedelta(hours=1))
    provider, _ = provider_for(
        [[candle_at(request.end + timedelta(minutes=15))]]
    )

    with pytest.raises(ValueError, match="within the requested gap"):
        provider.fetch(CONTEXT, request)


def test_request_and_candle_awareness_mismatch_is_rejected():
    request = TimeRange(START, START + timedelta(hours=1))
    aware_candle = candle_at(START.replace(tzinfo=timezone.utc))
    provider, _ = provider_for([[aware_candle]])

    with pytest.raises(ValueError, match="timezone awareness"):
        provider.fetch(CONTEXT, request)


def test_feed_failure_before_completion_is_propagated():
    request = TimeRange(START, START + timedelta(hours=1))
    provider, _ = provider_for([RuntimeError("broker failed")])

    with pytest.raises(RuntimeError, match="broker failed"):
        provider.fetch(CONTEXT, request)


def test_feed_failure_after_partial_emission_returns_no_result():
    request = TimeRange(START, START + timedelta(days=2))
    first_chunk = [candle_at(START + timedelta(minutes=15))]
    provider, broker = provider_for(
        [first_chunk, RuntimeError("later chunk failed")],
        max_days=1,
    )

    with pytest.raises(RuntimeError, match="later chunk failed"):
        provider.fetch(CONTEXT, request)

    assert len(broker.requests) == 2

from datetime import datetime, timedelta

import pytest

from core.entities.candle import Candle
from core.market_data.binding_aware_historical_feed_provider import (
    BindingAwareHistoricalFeedProvider,
)
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_feed import HistoricalFeed
from core.market_data.provider_instrument_binding import (
    ProviderInstrumentBinding,
)
from core.runtime.dataset_context import DatasetContext


START = datetime(2026, 1, 2, 9, 15)
ONE_DAY = timedelta(days=1)

CONTEXT = DatasetContext(
    symbol="ABC",
    timeframe="15m",
    timezone="Asia/Kolkata",
)


def candle_at(
    timestamp: datetime,
    *,
    close: float = 100.0,
) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=close,
        high=close + 1.0,
        low=close - 1.0,
        close=close,
        volume=1000.0,
    )


def binding_for(
    start: datetime,
    end: datetime,
) -> ProviderInstrumentBinding:
    return ProviderInstrumentBinding(
        binding_id="angelone-abc-v1",
        instrument_id="NSE-EQ-ABC",
        provider="angelone",
        provider_instrument_id="100",
        provider_exchange="NSE",
        provider_segment="EQ",
        provider_symbol="ABC",
        effective_from=start,
        effective_to=end,
    )


class RecordingBindingBroker:
    def __init__(
        self,
        responses=(),
    ):
        self.responses = list(responses)
        self.requests = []

    def get_historical_limits(self):
        return {
            "15m": 1,
        }

    def get_historical_candles(
        self,
        symbol,
        timeframe,
        start,
        end,
        *,
        provider_binding,
    ):
        self.requests.append(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "start": start,
                "end": end,
                "provider_binding": provider_binding,
            }
        )

        index = len(self.requests) - 1

        if index >= len(self.responses):
            return []

        response = self.responses[index]

        if isinstance(response, Exception):
            raise response

        return list(response)


class LegacyBroker:
    def __init__(self):
        self.requests = []

    def get_historical_limits(self):
        return {
            "15m": 1,
        }

    def get_historical_candles(
        self,
        symbol,
        timeframe,
        start,
        end,
    ):
        self.requests.append(
            (
                symbol,
                timeframe,
                start,
                end,
            )
        )

        return []


def test_binding_stream_passes_same_binding_to_every_chunk():
    end = START + (2 * ONE_DAY)
    provider_binding = binding_for(
        START,
        end,
    )

    broker = RecordingBindingBroker(
        responses=(
            (),
            (),
        )
    )

    feed = HistoricalFeed(
        broker,
        request_delay_sec=0,
    )

    assert list(
        feed.stream_with_binding(
            symbol="ABC",
            timeframe="15m",
            start=START,
            end=end,
            provider_binding=provider_binding,
        )
    ) == []

    assert len(broker.requests) == 2

    assert all(
        request["provider_binding"]
        is provider_binding
        for request in broker.requests
    )

    assert [
        (
            request["start"],
            request["end"],
        )
        for request in broker.requests
    ] == [
        (
            START,
            START + ONE_DAY,
        ),
        (
            START + ONE_DAY,
            end,
        ),
    ]


def test_binding_stream_reuses_exact_overlap_deduplication():
    boundary = START + ONE_DAY
    end = START + (2 * ONE_DAY)

    first = candle_at(
        START + timedelta(hours=1),
        close=100.0,
    )
    shared = candle_at(
        boundary,
        close=101.0,
    )
    last = candle_at(
        boundary + timedelta(hours=1),
        close=102.0,
    )

    broker = RecordingBindingBroker(
        responses=(
            (
                first,
                shared,
            ),
            (
                shared,
                last,
            ),
        )
    )

    feed = HistoricalFeed(
        broker,
        request_delay_sec=0,
    )

    result = list(
        feed.stream_with_binding(
            symbol="ABC",
            timeframe="15m",
            start=START,
            end=end,
            provider_binding=binding_for(
                START,
                end,
            ),
        )
    )

    assert result == [
        first,
        shared,
        last,
    ]


def test_binding_provider_returns_full_coverage_and_half_open_candles():
    end = START + timedelta(hours=1)

    first = candle_at(
        START,
        close=100.0,
    )
    exact_end = candle_at(
        end,
        close=101.0,
    )

    broker = RecordingBindingBroker(
        responses=(
            (
                first,
                exact_end,
            ),
        )
    )

    provider = BindingAwareHistoricalFeedProvider(
        HistoricalFeed(
            broker,
            request_delay_sec=0,
        )
    )

    request = TimeRange(
        START,
        end,
    )

    result = provider.fetch(
        CONTEXT,
        request,
        provider_binding=binding_for(
            START,
            end,
        ),
    )

    assert result.candles == (
        first,
    )

    assert result.coverage == (
        request,
    )

    assert len(broker.requests) == 1


def test_binding_provider_rejects_incomplete_binding_before_broker_call():
    end = START + timedelta(hours=2)
    binding_end = START + timedelta(hours=1)

    broker = RecordingBindingBroker()

    provider = BindingAwareHistoricalFeedProvider(
        HistoricalFeed(
            broker,
            request_delay_sec=0,
        )
    )

    with pytest.raises(ValueError):
        provider.fetch(
            CONTEXT,
            TimeRange(
                START,
                end,
            ),
            provider_binding=binding_for(
                START,
                binding_end,
            ),
        )

    assert broker.requests == []


def test_binding_provider_propagates_failure_after_partial_emission():
    end = START + (2 * ONE_DAY)

    first = candle_at(
        START + timedelta(hours=1)
    )

    broker = RecordingBindingBroker(
        responses=(
            (
                first,
            ),
            RuntimeError(
                "provider failed"
            ),
        )
    )

    provider = BindingAwareHistoricalFeedProvider(
        HistoricalFeed(
            broker,
            request_delay_sec=0,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="provider failed",
    ):
        provider.fetch(
            CONTEXT,
            TimeRange(
                START,
                end,
            ),
            provider_binding=binding_for(
                START,
                end,
            ),
        )

    assert len(broker.requests) == 2


def test_legacy_stream_still_supports_old_broker_signature():
    broker = LegacyBroker()

    feed = HistoricalFeed(
        broker,
        request_delay_sec=0,
    )

    end = START + timedelta(hours=1)

    assert list(
        feed.stream(
            symbol="ABC",
            timeframe="15m",
            start=START,
            end=end,
        )
    ) == []

    assert broker.requests == [
        (
            "ABC",
            "15m",
            START,
            end,
        )
    ]

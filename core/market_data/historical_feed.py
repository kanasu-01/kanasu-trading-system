# core/market_data/historical_feed.py

from typing import List
from datetime import datetime
from datetime import timedelta
import time

from core.market_data.base_feed import BaseFeed
from core.broker.base_broker import BaseBroker
from core.entities.candle import Candle


def _is_timezone_aware(timestamp: datetime) -> bool:
    return timestamp.utcoffset() is not None


class HistoricalFeed(BaseFeed):
    """
    Broker-agnostic historical market data feed.

    Responsibilities:
    - Ask broker for historical candles
    - Return List[Candle] for backtesting / replay
    """

    def __init__(self, broker: BaseBroker, request_delay_sec):
        self.broker = broker
        self.request_delay_sec = request_delay_sec

    def load(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> List[Candle]:
        """
        Load historical candles via broker.

        Broker must implement:
        get_historical_candles(symbol, timeframe, start, end)
        """

        return self.broker.get_historical_candles(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )

    def stream(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ):
        """
        Stream historical candles in chunks via brokerusing broker limits.

        Candles are yielded one by one in chronological order.

        Broker must implement:
        get_historical_candles(symbol, timeframe, start, end)
        """
        # Ask broker for historical limits
        limits = self.broker.get_historical_limits()

        if timeframe not in limits:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        max_days = limits[timeframe]

        current_start = start
        seen_by_timestamp: dict[datetime, Candle] = {}
        latest_emitted_timestamp: datetime | None = None

        while current_start < end:
            safe_end = current_start + timedelta(days=max_days)
            if safe_end > end:
                safe_end = end

            candles = self.broker.get_historical_candles(
                symbol=symbol,
                timeframe=timeframe,
                start=current_start,
                end=safe_end,
            )
            time.sleep(self.request_delay_sec)

            current_chunk_timestamps: set[datetime] = set()
            previous_chunk_timestamp: datetime | None = None

            for candle in candles:
                timestamp = candle.timestamp

                if previous_chunk_timestamp is not None:
                    if _is_timezone_aware(timestamp) != _is_timezone_aware(
                        previous_chunk_timestamp
                    ):
                        raise ValueError(
                            "historical candle timezone awareness must match"
                        )

                if timestamp in current_chunk_timestamps:
                    raise ValueError(
                        "duplicate timestamp within historical broker chunk"
                    )

                if (
                    previous_chunk_timestamp is not None
                    and timestamp < previous_chunk_timestamp
                ):
                    raise ValueError(
                        "historical broker chunk must be chronological; "
                        "timestamp is older than the previous candle"
                    )

                current_chunk_timestamps.add(timestamp)
                previous_chunk_timestamp = timestamp

                if timestamp in seen_by_timestamp:
                    if candle != seen_by_timestamp[timestamp]:
                        raise ValueError(
                            "conflicting historical candle for previously "
                            "emitted timestamp"
                        )
                    continue

                if latest_emitted_timestamp is not None:
                    if _is_timezone_aware(timestamp) != _is_timezone_aware(
                        latest_emitted_timestamp
                    ):
                        raise ValueError(
                            "historical candle timezone awareness must match"
                        )

                    if timestamp < latest_emitted_timestamp:
                        raise ValueError(
                            "delayed out-of-order historical candle is older "
                            "than the latest emitted candle"
                        )

                seen_by_timestamp[timestamp] = candle
                latest_emitted_timestamp = timestamp
                yield candle

            current_start = safe_end

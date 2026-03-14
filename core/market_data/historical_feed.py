# core/market_data/historical_feed.py

from typing import List
from datetime import datetime
from datetime import timedelta

from core.market_data.base_feed import BaseFeed
from core.broker.base_broker import BaseBroker
from core.entities.candle import Candle


class HistoricalFeed(BaseFeed):
    """
    Broker-agnostic historical market data feed.

    Responsibilities:
    - Ask broker for historical candles
    - Return List[Candle] for backtesting / replay
    """

    def __init__(self, broker: BaseBroker):
        self.broker = broker

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
            
            for candle in candles:
                yield candle
                
            current_start = safe_end
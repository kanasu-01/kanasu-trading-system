# core/market_data/historical_feed.py

from typing import List
from datetime import datetime

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
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
    - Ask broker for historical raw data
    - Convert raw data into Candle objects
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
        get_historical_data(symbol, timeframe, start, end)
        """

        raw_data = self.broker.get_historical_data(
            symbol=symbol,
            timeframe=timeframe,
            start=start,
            end=end,
        )

        candles: List[Candle] = []

        for row in raw_data:
            candles.append(
                Candle(
                    timestamp=row["timestamp"],
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                    symbol=symbol,
                )
            )

        return candles
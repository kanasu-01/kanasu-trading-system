import time
from typing import List, Callable

from core.entities.candle import Candle
from core.market_data.base_feed import MarketDataFeed


class MockLiveFeed(MarketDataFeed):
    """
    Simulated live feed using historical candles.
    """

    def __init__(
        self,
        candles: List[Candle],
        interval_seconds: float = 1.0,
    ):
        self.candles = candles
        self.interval_seconds = interval_seconds

    def subscribe(self, on_candle: Callable[[Candle], None]) -> None:
        for candle in self.candles:
            on_candle(candle)
            time.sleep(self.interval_seconds)

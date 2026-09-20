import time
from typing import List

from core.entities.candle import Candle
from core.market_data.completed_candle_delivery import CompletedCandleDelivery
from core.market_data.live_candle_feed import (
    CompletedCandleHandler,
    LiveCandleFeed,
)


class MockLiveFeed(LiveCandleFeed):
    """
    Simulated live feed using already-completed historical candles.
    """

    def __init__(
        self,
        candles: List[Candle],
        interval_seconds: float = 0.0,
    ):
        self.candles = candles
        self.interval_seconds = interval_seconds
        self._delivery = CompletedCandleDelivery()

    def subscribe(self, on_candle: CompletedCandleHandler) -> None:
        for candle in self.candles:
            if self._delivery.accept(candle):
                on_candle(candle)

            time.sleep(self.interval_seconds)

    def load(
        self,
        symbol,
        timeframe,
        start,
        end,
    ):
        """
        Preserve the existing replay accessor during the M6 transition.

        This method is not part of the live-feed contract.
        """
        return self.candles

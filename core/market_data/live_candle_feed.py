from abc import ABC, abstractmethod
from collections.abc import Callable

from core.entities.candle import Candle
from core.market_data.live_market_update import LiveMarketUpdate


CompletedCandleHandler = Callable[[Candle], None]
LiveMarketUpdateHandler = Callable[[LiveMarketUpdate, bool], None]


class LiveCandleFeed(ABC):
    """
    Contract for live feeds that deliver completed candles only.

    In-progress market updates must not reach the completed-candle consumer.
    """

    @abstractmethod
    def subscribe(self, on_candle: CompletedCandleHandler) -> None:
        pass

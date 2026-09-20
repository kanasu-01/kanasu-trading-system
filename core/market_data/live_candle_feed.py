from abc import ABC, abstractmethod
from collections.abc import Callable

from core.entities.candle import Candle


CompletedCandleHandler = Callable[[Candle], None]


class LiveCandleFeed(ABC):
    """
    Contract for live feeds that deliver completed candles only.

    In-progress market updates must not reach the completed-candle consumer.
    """

    @abstractmethod
    def subscribe(self, on_candle: CompletedCandleHandler) -> None:
        pass

from abc import ABC, abstractmethod
from typing import Callable

from core.entities.candle import Candle


class MarketDataFeed(ABC):
    @abstractmethod
    def subscribe(self, on_candle: Callable[[Candle], None]) -> None:
        pass

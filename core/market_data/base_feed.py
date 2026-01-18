from abc import ABC, abstractmethod
from typing import List
from datetime import datetime

from core.entities.candle import Candle


class BaseFeed(ABC):
    @abstractmethod
    def load(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> List[Candle]:
        pass

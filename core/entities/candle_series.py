from typing import List, Iterator
from core.entities.candle import Candle


class CandleSeries:
    """
    Ordered collection of Candle objects.
    """

    def __init__(self, candles: List[Candle] | None = None):
        self._candles: List[Candle] = candles or []

    def __len__(self) -> int:
        return len(self._candles)

    def __getitem__(self, index):
        """
        Allows indexing like:
        series[-1], series[0], series[1:5]
        """
        return self._candles[index]

    def __iter__(self) -> Iterator[Candle]:
        return iter(self._candles)

    def append(self, candle: Candle) -> None:
        self._candles.append(candle)

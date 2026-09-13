from datetime import datetime
from typing import List, Iterator
from core.entities.candle import Candle


class CandleSeries:
    """
    Ordered collection of Candle objects.
    """

    def __init__(self, candles: List[Candle] | None = None):
        self._candles: List[Candle] = []
        self._timestamps: set[datetime] = set()

        for candle in candles or []:
            self.append(candle)

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
        timestamp = candle.timestamp

        if self._candles:
            latest_timestamp = self._candles[-1].timestamp

            if ((timestamp.utcoffset() is not None) !=
                    (latest_timestamp.utcoffset() is not None)):
                raise ValueError("candle timestamp timezone awareness must match")

            if timestamp in self._timestamps:
                raise ValueError("duplicate candle timestamp")

            if timestamp < latest_timestamp:
                raise ValueError(
                    "candles must remain chronological; "
                    "incoming timestamp is older than the latest candle"
                )

        self._candles.append(candle)
        self._timestamps.add(timestamp)

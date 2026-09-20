from datetime import datetime

from core.entities.candle import Candle


def _is_timezone_aware(timestamp: datetime) -> bool:
    return timestamp.utcoffset() is not None


class CompletedCandleDelivery:
    """
    Session-scoped validity gate for completed candle delivery.

    Returns True for a new valid candle and False for an identical
    retransmission that has already been accepted.
    """

    def __init__(self) -> None:
        self._seen_by_timestamp: dict[datetime, Candle] = {}
        self._latest_timestamp: datetime | None = None

    def accept(self, candle: Candle) -> bool:
        timestamp = candle.timestamp
        previous = self._seen_by_timestamp.get(timestamp)

        if previous is not None:
            if candle != previous:
                raise ValueError(
                    "conflicting completed candle for previously "
                    "accepted timestamp"
                )
            return False

        if self._latest_timestamp is not None:
            if _is_timezone_aware(timestamp) != _is_timezone_aware(
                self._latest_timestamp
            ):
                raise ValueError(
                    "completed candle timestamp timezone awareness must match"
                )

            if timestamp < self._latest_timestamp:
                raise ValueError(
                    "completed candle timestamp is older than the latest "
                    "accepted candle"
                )

        self._seen_by_timestamp[timestamp] = candle
        self._latest_timestamp = timestamp
        return True

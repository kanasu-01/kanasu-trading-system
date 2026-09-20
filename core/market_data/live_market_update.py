from dataclasses import dataclass
from datetime import datetime
from math import isfinite


@dataclass(frozen=True)
class LiveMarketUpdate:
    """
    Broker-neutral live market update.

    cumulative_volume is the source's cumulative traded volume for the
    current trading session.
    """

    timestamp: datetime
    price: float
    cumulative_volume: float
    sequence: int

    def __post_init__(self) -> None:
        if self.timestamp.utcoffset() is None:
            raise ValueError("live market update timestamp must be timezone-aware")

        if not isfinite(self.price) or self.price <= 0:
            raise ValueError("live market update price must be finite and positive")

        if not isfinite(self.cumulative_volume) or self.cumulative_volume < 0:
            raise ValueError(
                "live market update cumulative volume must be finite "
                "and non-negative"
            )

        if (
            isinstance(self.sequence, bool)
            or not isinstance(self.sequence, int)
            or self.sequence < 0
        ):
            raise ValueError(
                "live market update sequence must be a non-negative integer"
            )

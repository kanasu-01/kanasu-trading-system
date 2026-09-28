from dataclasses import dataclass
from datetime import datetime
from math import isfinite


def _validate_optional_effective_range(
    effective_from: datetime | None,
    effective_to: datetime | None,
) -> None:
    if effective_from is not None and not isinstance(
        effective_from,
        datetime,
    ):
        raise TypeError("effective_from must be a datetime or None")

    if effective_to is not None and not isinstance(
        effective_to,
        datetime,
    ):
        raise TypeError("effective_to must be a datetime or None")

    if effective_from is not None and effective_to is not None:
        from_aware = effective_from.utcoffset() is not None
        to_aware = effective_to.utcoffset() is not None

        if from_aware != to_aware:
            raise ValueError(
                "instrument effective bounds must use matching "
                "timezone awareness"
            )

        if effective_from >= effective_to:
            raise ValueError(
                "instrument effective_from must be before effective_to"
            )


@dataclass(frozen=True)
class Instrument:
    """Immutable canonical instrument metadata for one effective period."""

    instrument_id: str
    symbol: str
    exchange: str = "NSE"
    segment: str | None = None
    tick_size: float = 0.05
    lot_size: int = 1
    effective_from: datetime | None = None
    effective_to: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.instrument_id, str) or not self.instrument_id:
            raise ValueError("instrument_id must be a non-empty string")

        if not isinstance(self.symbol, str) or not self.symbol:
            raise ValueError("symbol must be a non-empty string")

        if not isinstance(self.exchange, str) or not self.exchange:
            raise ValueError("exchange must be a non-empty string")

        if self.segment is not None and (
            not isinstance(self.segment, str) or not self.segment
        ):
            raise ValueError("segment must be a non-empty string or None")

        if (
            isinstance(self.tick_size, bool)
            or not isinstance(self.tick_size, (int, float))
            or not isfinite(self.tick_size)
            or self.tick_size <= 0
        ):
            raise ValueError("tick_size must be finite and positive")

        if (
            isinstance(self.lot_size, bool)
            or not isinstance(self.lot_size, int)
            or self.lot_size <= 0
        ):
            raise ValueError("lot_size must be a positive integer")

        _validate_optional_effective_range(
            self.effective_from,
            self.effective_to,
        )

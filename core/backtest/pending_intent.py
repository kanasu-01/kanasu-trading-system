from dataclasses import dataclass
from datetime import datetime

from core.strategies.signal import SignalType


@dataclass(frozen=True)
class PendingIntent:
    """Decision-time data required to execute a Backtest intent next bar."""

    signal: SignalType
    decision_timestamp: datetime
    decision_close: float
    rejection_midpoint: float | None = None

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class ExecutionFeedbackType(str, Enum):
    """Authoritative execution outcomes delivered to a strategy."""

    ENTRY_ACCEPTED = "ENTRY_ACCEPTED"
    ENTRY_REJECTED = "ENTRY_REJECTED"
    STRATEGY_EXIT = "STRATEGY_EXIT"
    PROTECTIVE_EXIT = "PROTECTIVE_EXIT"


class ExecutionRejectionReason(str, Enum):
    """Machine-readable entry rejection reasons owned by M4.2."""

    DRAWDOWN_LIMIT = "DRAWDOWN_LIMIT"
    INVALID_ENTRY = "INVALID_ENTRY"
    INVALID_QUANTITY = "INVALID_QUANTITY"
    PORTFOLIO_RISK_LIMIT = "PORTFOLIO_RISK_LIMIT"


class ExecutionPositionState(str, Enum):
    """Authoritative position state after an execution outcome."""

    FLAT = "FLAT"
    LONG = "LONG"


@dataclass(frozen=True)
class ExecutionFeedback:
    """Immutable execution outcome delivered in authoritative event order."""

    event_type: ExecutionFeedbackType
    symbol: str
    timestamp: datetime
    position_state: ExecutionPositionState
    fill_price: Optional[float] = None
    quantity: Optional[int] = None
    rejection_reason: Optional[ExecutionRejectionReason] = None

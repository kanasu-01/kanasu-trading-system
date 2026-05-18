from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

from core.entities.candle import Candle
from core.logging.logger import get_logger

# ==========================================================
# BAR RECORD (STRATEGY-AGNOSTIC)
# ==========================================================


@dataclass
class BarRecord:
    # -------- Market data --------
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float

    # -------- Strategy outputs --------
    strategy: str
    state: Optional[str]
    signal: Optional[str]
    execution_event: Optional[str]

    execution_price: Optional[float]

    execution_quantity: Optional[int]

    # -------- Generic decision snapshot --------
    decision_snapshot: Dict[str, Any]

    # -------- Portfolio state (optional, can be added later) --------
    equity: float
    cash: float
    position_size: float
    drawdown: float


# ==========================================================
# BAR RECORDER
# ==========================================================


class BarRecorder:
    """
    Records bar-by-bar strategy evaluation.
    Works with ALL strategies (SMA, PivotBoss, future).
    """

    def __init__(self):
        self.records: List[BarRecord] = []
        self.logger = get_logger(__name__)

    def record(
        self,
        candle: Candle,
        strategy,
        signal: Optional[str],
        execution_event: Optional[str],
        execution_price: Optional[float],
        execution_quantity: Optional[int],
        equity: float,
        cash: float,
        position_size: float,
        drawdown: float,
    ) -> None:
        """
        Record a single bar evaluation.
        """

        # Fetch strategy debug / decision snapshot (if available)
        snapshot: Dict[str, Any] = {}
        if hasattr(strategy, "get_debug_state"):
            try:
                snapshot = strategy.get_debug_state() or {}
            except Exception as e:

                self.logger.exception("Failed to fetch strategy debug snapshot")

                snapshot = {}

        # Extract state safely (PivotBoss has state enum, SMA may not)
        state_value: Optional[str] = None
        if hasattr(strategy, "state"):
            try:
                state_value = (
                    strategy.state.value
                    if hasattr(strategy.state, "value")
                    else str(strategy.state)
                )
            except Exception as e:

                self.logger.exception("Failed to extract strategy state")

                state_value = None

        self.records.append(
            BarRecord(
                timestamp=candle.timestamp,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                strategy=strategy.name,
                state=state_value,
                signal=signal,
                execution_event=execution_event,
                execution_price=execution_price,
                execution_quantity=execution_quantity,
                decision_snapshot=snapshot,
                equity=equity,
                cash=cash,
                position_size=position_size,
                drawdown=drawdown,
            )
        )

from typing import Optional

from core.entities.candle_series import CandleSeries
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import SignalType
from core.execution.execution_feedback import (
    ExecutionFeedback,
    ExecutionFeedbackType,
)


class SMACrossOverStrategy(BaseStrategy):
    """
    Simple Moving Average Crossover Strategy.
    First-class strategy used to validate the entire trading system.
    """

    def __init__(self, params=None):
        super().__init__(name="SMACrossOver", params=params)

        # Parameters
        self.fast_period = self.get_param("fast_period", 20)
        self.slow_period = self.get_param("slow_period", 50)

        if self.fast_period >= self.slow_period:
            raise ValueError("fast_period must be < slow_period")

        # Internal state
        self.position_open = False
        self.last_signal: Optional[SignalType] = None

        # Cached values for debug
        self.fast_sma: Optional[float] = None
        self.slow_sma: Optional[float] = None

    # -------------------------------------------------
    # Strategy lifecycle
    # -------------------------------------------------

    def reset(self) -> None:
        self.position_open = False
        self.last_signal = None
        self.fast_sma = None
        self.slow_sma = None

    def warmup_bars(self) -> int:
        """
        Need enough bars to compute the slow SMA.
        """
        return self.slow_period

    def research_parameters(self) -> dict:
        """Return resolved strategy inputs used by this instance."""

        return {
            "fast_period": self.fast_period,
            "slow_period": self.slow_period,
        }

    # -------------------------------------------------
    # Core logic
    # -------------------------------------------------

    def on_new_candle(self, series: CandleSeries) -> Optional[SignalType]:
        if len(series) < self.warmup_bars():
            return None

        closes = [c.close for c in series]

        self.fast_sma = sum(closes[-self.fast_period :]) / self.fast_period
        self.slow_sma = sum(closes[-self.slow_period :]) / self.slow_period

        signal: Optional[SignalType] = None

        # Entry condition
        if not self.position_open and self.fast_sma > self.slow_sma:
            signal = SignalType.BUY

        # Exit condition
        elif self.position_open and self.fast_sma < self.slow_sma:
            signal = SignalType.SELL

        self.last_signal = signal
        return signal

    def on_execution_feedback(self, feedback: ExecutionFeedback) -> None:
        """Reconcile local position belief with authoritative execution."""

        if feedback.event_type == ExecutionFeedbackType.ENTRY_ACCEPTED:
            self.position_open = True
        elif feedback.event_type in {
            ExecutionFeedbackType.ENTRY_REJECTED,
            ExecutionFeedbackType.STRATEGY_EXIT,
            ExecutionFeedbackType.PROTECTIVE_EXIT,
        }:
            self.position_open = False

    # -------------------------------------------------
    # Debug / replay support
    # -------------------------------------------------

    def get_debug_state(self) -> dict:
        """
        Strategy-agnostic debug snapshot.
        Used by backtest recorder and future visualization.
        """
        return {
            "fast_sma": self.fast_sma,
            "slow_sma": self.slow_sma,
            "fast_gt_slow": (
                None
                if self.fast_sma is None or self.slow_sma is None
                else self.fast_sma > self.slow_sma
            ),
            "position_open": self.position_open,
            "last_signal": self.last_signal,
        }

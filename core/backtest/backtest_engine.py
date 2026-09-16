from typing import List
import uuid

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.strategies.strategy_runner import StrategyRunner
from core.strategies.base_strategy import BaseStrategy
from core.backtest.bar_record import BarRecorder
from core.execution.trade_execution_engine import TradeExecutionEngine
from core.runtime.runtime_context import (
    RuntimeContext,
)
from core.runtime.dataset_context import (
    DatasetContext,
)
from core.entities.trade import Trade
from core.logging.logger import get_logger
from core.backtest.backtest_result import BacktestResult
from core.backtest.pending_intent import PendingIntent


class BacktestEngine:
    """
    Runs a candle-by-candle backtest and records bar-level strategy decisions.
    Strategy-agnostic by design.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        initial_capital: float,
        runtime_context: RuntimeContext,
        dataset_context: DatasetContext,
    ):
        self.strategy = strategy
        self.runtime_context = runtime_context
        self.dataset_context = dataset_context
        self.logger = get_logger(__name__)
        self.initial_capital = initial_capital
        self.session_id = str(uuid.uuid4())[:8]
        self.runner = StrategyRunner(strategy)

        self.bar_recorder = BarRecorder()

        self.execution_engine = TradeExecutionEngine(
            strategy=strategy,
            account_capital=initial_capital,
            session_id=self.session_id,
            runtime_context=self.runtime_context,
        )

    # -------------------------------------------------
    # Internal engine (used by both batch & stream)
    # -------------------------------------------------

    def _run_internal(self, candles) -> BacktestResult:
        self.logger.info(
            f"BACKTEST STARTED | "
            f"Session={self.session_id} | "
            f"Strategy={self.strategy.name}"
        )
        series = CandleSeries([])
        self.runner.start(series)
        pending_intent = None

        for candle in candles:

            try:

                feedback_events = self.execution_engine.process_backtest_candle(
                    pending_signal=(
                        pending_intent.signal if pending_intent else None
                    ),
                    decision_close=(
                        pending_intent.decision_close if pending_intent else None
                    ),
                    rejection_midpoint=(
                        pending_intent.rejection_midpoint
                        if pending_intent
                        else None
                    ),
                    candle=candle,
                    execution_index=len(series),
                    symbol=self.dataset_context.symbol,
                )
                self.runner.deliver_execution_feedback(feedback_events)
                self.execution_engine.mark_open_position_to_market(
                    symbol=self.dataset_context.symbol,
                    price=candle.close,
                )

                signal = self.runner.on_new_candle(candle)
                pending_intent = (
                    PendingIntent(
                        signal=signal,
                        decision_timestamp=candle.timestamp,
                        decision_close=candle.close,
                        rejection_midpoint=getattr(
                            self.strategy,
                            "rejection_midpoint",
                            None,
                        ),
                    )
                    if signal is not None
                    else None
                )

                state = self.execution_engine.portfolio_manager.snapshot()

                self.bar_recorder.record(
                    candle=candle,
                    strategy=self.strategy,
                    signal=(signal.value if signal is not None else None),
                    execution_event=self.execution_engine.last_execution_event,
                    execution_price=self.execution_engine.last_execution_price,
                    execution_quantity=self.execution_engine.last_execution_quantity,
                    equity=state.equity,
                    cash=state.cash,
                    position_size=state.position_size,
                    drawdown=state.drawdown,
                )

            except Exception as e:

                self.logger.exception(
                    f"Backtest runtime failure " f"at candle: " f"{candle.timestamp}"
                )

                raise

        trades = self.execution_engine.completed_trades

        self.logger.info(
            f"BACKTEST COMPLETED | "
            f"Session={self.session_id} | "
            f"Strategy={self.strategy.name} | "
            f"Trades={len(trades)}"
        )

        return BacktestResult(
            trades=trades,
            bar_records=self.bar_recorder.records,
            session_id=self.session_id,
        )

    # -------------------------------------------------
    # Public APIs
    # -------------------------------------------------

    def run(self, candles: List[Candle]) -> BacktestResult:
        """
        Backward-compatible bulk backtest method.
        """
        return self._run_internal(candles)

    def run_stream(self, candle_stream) -> BacktestResult:
        """
        Stream-based backtest method.
        """
        return self._run_internal(candle_stream)

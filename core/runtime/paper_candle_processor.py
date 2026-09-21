from core.execution.pending_intent import PendingIntent
from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.execution.trade_execution_engine import TradeExecutionEngine
from core.market_data.live_market_update import LiveMarketUpdate
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy
from core.strategies.strategy_runner import StrategyRunner


class PaperCandleProcessor:
    """
    Stateful completed-candle processor for paper trading.

    Preserves the canonical M5 execution order:
    prior intent execution -> execution feedback -> mark-to-market
    -> current candle strategy decision -> next pending intent.
    """

    def __init__(
        self,
        *,
        strategy: BaseStrategy,
        runtime_context: RuntimeContext,
        dataset_context: DatasetContext,
        initial_capital: float,
        session_id: str,
        history_bars: list[Candle] | None = None,
    ) -> None:
        self.strategy = strategy
        self.runtime_context = runtime_context
        self.dataset_context = dataset_context

        self.series = CandleSeries(
            list(history_bars or [])
        )
        self.strategy_runner = StrategyRunner(strategy)
        self.strategy_runner.start(self.series)

        self.execution_engine = TradeExecutionEngine(
            strategy=strategy,
            account_capital=initial_capital,
            session_id=session_id,
            runtime_context=runtime_context,
            risk_per_trade_pct=runtime_context.risk_per_trade_pct,
            economic_policy=runtime_context.economic_policy,
        )

        self._pending_intent: PendingIntent | None = None

    def on_candle(self, candle: Candle) -> None:
        pending_intent = self._pending_intent

        feedback_events = self.execution_engine.process_backtest_candle(
            pending_signal=(
                pending_intent.signal
                if pending_intent is not None
                else None
            ),
            decision_close=(
                pending_intent.decision_close
                if pending_intent is not None
                else None
            ),
            rejection_midpoint=(
                pending_intent.rejection_midpoint
                if pending_intent is not None
                else None
            ),
            candle=candle,
            execution_index=len(self.series),
            symbol=self.dataset_context.symbol,
        )

        self.strategy_runner.deliver_execution_feedback(
            feedback_events
        )

        self.execution_engine.mark_open_position_to_market(
            symbol=self.dataset_context.symbol,
            price=candle.close,
        )

        self._record_strategy_decision(candle)

    def on_live_completed_candle(
        self,
        candle: Candle,
    ) -> None:
        """
        Decide from a completed live candle without retrospectively
        executing against that same candle.
        """
        self._record_strategy_decision(candle)

    def on_live_market_update(
        self,
        update: LiveMarketUpdate,
        opens_new_bar: bool,
    ) -> None:
        """
        Apply causal live execution from the currently observed source price.

        A pending strategy intent may execute only on the source observation
        that proves a new valid bar has opened. Every accepted live update
        may still enforce protection on an already-open position.
        """
        pending_intent = (
            self._pending_intent
            if opens_new_bar
            else None
        )

        feedback_events = (
            self.execution_engine.process_live_market_update(
                pending_signal=(
                    pending_intent.signal
                    if pending_intent is not None
                    else None
                ),
                decision_close=(
                    pending_intent.decision_close
                    if pending_intent is not None
                    else None
                ),
                rejection_midpoint=(
                    pending_intent.rejection_midpoint
                    if pending_intent is not None
                    else None
                ),
                update=update,
                execution_index=len(self.series),
                symbol=self.dataset_context.symbol,
            )
        )

        self.strategy_runner.deliver_execution_feedback(
            feedback_events
        )

        if opens_new_bar:
            self._pending_intent = None

        self.execution_engine.mark_open_position_to_market(
            symbol=self.dataset_context.symbol,
            price=update.price,
        )

    def _record_strategy_decision(
        self,
        candle: Candle,
    ) -> None:
        signal = self.strategy_runner.on_new_candle(candle)

        self._pending_intent = (
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

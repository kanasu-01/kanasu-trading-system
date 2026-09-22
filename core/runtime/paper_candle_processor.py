from datetime import datetime, timedelta

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
        self._live_reconciliation_start: datetime | None = None
        self._live_reconciliation_first_interval_start: datetime | None = None

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
        Mark the completed live close before strategy evaluation.

        Pending intent execution remains exclusively source-observation
        driven and never occurs retrospectively from this candle's open.
        """
        self.execution_engine.mark_open_position_to_market(
            symbol=self.dataset_context.symbol,
            price=candle.close,
        )

        self._record_strategy_decision(candle)

    def begin_live_reconciliation(self) -> None:
        """
        Enter restricted live reconciliation after a provider-data gap.

        Any pending next-bar intent is no longer causally executable after
        the gap. An already-open position is preserved and may be protected
        only by newly observed live source prices after reconnect.
        """
        if len(self.series) == 0:
            raise RuntimeError(
                "live reconciliation requires completed strategy state"
            )

        self._pending_intent = None
        self._live_reconciliation_start = (
            self.series[-1].timestamp
            + self._live_interval()
        )
        self._live_reconciliation_first_interval_start = None

    def apply_live_reconciliation_candles(
        self,
        candles: list[Candle],
        *,
        expected_start: datetime | None = None,
        expected_end: datetime | None = None,
    ) -> None:
        """
        Replay authoritative completed gap candles into strategy state only.

        Recovered history may rebuild indicator/strategy context, but signals
        produced from those candles are not causally executable and therefore
        must never become pending live intents. Historical OHLC must not
        retrospectively mutate an already-open position.
        """
        if (expected_start is None) != (expected_end is None):
            raise ValueError(
                "live reconciliation history bounds must be provided together"
            )

        recovered = list(candles)

        if expected_start is not None and expected_end is not None:
            if expected_end <= expected_start:
                raise ValueError(
                    "live reconciliation history range must be non-empty"
                )

            interval = self._live_interval()
            expected_timestamps = []
            timestamp = expected_start

            while timestamp < expected_end:
                expected_timestamps.append(timestamp)
                timestamp += interval

            recovered_timestamps = [
                candle.timestamp
                for candle in recovered
            ]

            if recovered_timestamps != expected_timestamps:
                raise RuntimeError(
                    "incomplete live reconciliation history: "
                    "expected exact timeframe coverage "
                    f"for [{expected_start!s}, {expected_end!s})"
                )

        self._pending_intent = None

        for candle in recovered:
            self.strategy_runner.on_new_candle(candle)

        self._pending_intent = None

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
        pending_intent = None
        consume_pending_intent = False

        if (
            opens_new_bar
            and self._pending_intent is not None
            and self._is_immediate_next_live_interval(
                pending_intent=self._pending_intent,
                update=update,
            )
        ):
            pending_intent = self._pending_intent
            consume_pending_intent = True

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

        if consume_pending_intent:
            self._pending_intent = None

        self.execution_engine.mark_open_position_to_market(
            symbol=self.dataset_context.symbol,
            price=update.price,
        )

    def observe_live_reconciliation_update(
        self,
        update: LiveMarketUpdate,
        opens_new_bar: bool,
    ) -> tuple[datetime, datetime] | None:
        """
        Observe reconnect events without authorizing live execution.

        The first interval observed after reconnect is quarantined. The next
        real interval transition proves the completed historical gap range.
        """
        reconciliation_start = self._live_reconciliation_start

        if reconciliation_start is None:
            raise RuntimeError(
                "live reconciliation has not begun"
            )

        if not opens_new_bar:
            return None

        interval = self._live_interval()
        elapsed = update.timestamp - reconciliation_start

        if elapsed.total_seconds() < 0:
            raise ValueError(
                "live reconciliation update precedes recovery start"
            )

        bucket_index = int(
            elapsed.total_seconds()
            // interval.total_seconds()
        )
        interval_start = (
            reconciliation_start
            + interval * bucket_index
        )

        if self._live_reconciliation_first_interval_start is None:
            self._live_reconciliation_first_interval_start = (
                interval_start
            )
            return None

        if (
            interval_start
            <= self._live_reconciliation_first_interval_start
        ):
            return None

        return (
            reconciliation_start,
            interval_start,
        )

    def _live_interval(self) -> timedelta:
        timeframe_minutes = {
            "1m": 1,
            "3m": 3,
            "5m": 5,
            "10m": 10,
            "15m": 15,
            "30m": 30,
            "1h": 60,
        }.get(self.dataset_context.timeframe)

        if timeframe_minutes is None:
            raise RuntimeError(
                "live reconciliation requires a supported "
                f"intraday timeframe, got "
                f"{self.dataset_context.timeframe!r}"
            )

        return timedelta(
            minutes=timeframe_minutes
        )

    def _is_immediate_next_live_interval(
        self,
        *,
        pending_intent: PendingIntent,
        update: LiveMarketUpdate,
    ) -> bool:
        """
        Return whether this observation belongs to the intent's N+1 bar.

        A later observed interval is an unresolved market-data gap. M7.6
        must not reinterpret it as the immediate next bar; reconciliation
        policy is intentionally deferred to M7.7.
        """
        interval = self._live_interval()
        expected_start = (
            pending_intent.decision_timestamp
            + interval
        )
        expected_end = expected_start + interval

        return (
            expected_start
            <= update.timestamp
            < expected_end
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

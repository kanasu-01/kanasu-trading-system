from math import isfinite
from typing import List, Optional

from core.risk.risk_manager import RiskManager
from core.risk.stop_loss_manager import StopLossManager
from core.risk.portfolio_risk_manager import PortfolioRiskManager
from core.risk.drawdown_risk_manager import DrawdownRiskManager

from core.entities.candle import Candle
from core.entities.trade import Trade
from core.strategies.signal import SignalType

from core.journal.trade_journal import TradeJournal

from core.entities.position import Position

from core.execution.trade_builder import TradeBuilder
from core.logging.logger import get_logger

from core.strategies.base_strategy import (
    BaseStrategy,
)

from core.execution.brokerage_model import (
    BrokerageModel,
)

from core.execution.slippage_model import (
    SlippageModel,
)
from core.config.execution_config import (
    EXECUTION_CONFIG,
)
from core.portfolio.portfolio_manager import (
    PortfolioManager,
)
from core.runtime.runtime_context import (
    RuntimeContext,
)
from core.execution.execution_feedback import (
    ExecutionFeedback,
    ExecutionFeedbackType,
    ExecutionPositionState,
    ExecutionRejectionReason,
)


class TradeExecutionEngine:
    """
    Trade execution engine for backtest / paper trading.
    PHASE 8: Execution + journaling + costs.
    """

    def __init__(
        self,
        strategy: BaseStrategy,
        account_capital: float,
        session_id: str,
        runtime_context: RuntimeContext,
        risk_per_trade_pct: float = 1.0,
        economic_policy=None,
    ):

        self.strategy = strategy
        self.session_id = session_id
        self.runtime_context = runtime_context
        self.economic_policy = economic_policy
        self._fallback_long_stop_multiplier = (
            economic_policy.fallback_long_stop_multiplier
            if economic_policy is not None
            else 0.98
        )

        if economic_policy is None:
            self.brokerage_model = BrokerageModel()
        else:
            self.brokerage_model = BrokerageModel(
                brokerage_rate=economic_policy.brokerage_rate,
                brokerage_cap=economic_policy.brokerage_cap,
                tax_rate=economic_policy.tax_rate,
                rounding_digits=economic_policy.cost_rounding_digits,
            )

        self.slippage_model = SlippageModel(
            slippage_pct=(self.runtime_context.execution_config.slippage_pct)
        )

        self.logger = get_logger(__name__)

        self.last_execution_event = None

        self.last_execution_price = None

        self.last_execution_quantity = None
        self.last_transaction_cost = 0.0

        if economic_policy is None:
            self.risk_manager = RiskManager(
                account_capital=account_capital,
                risk_per_trade_pct=risk_per_trade_pct,
            )
            self.stop_manager = StopLossManager()
            self.portfolio_risk_manager = PortfolioRiskManager()
            self.drawdown_manager = DrawdownRiskManager()
        else:
            self.risk_manager = RiskManager(
                account_capital=account_capital,
                risk_per_trade_pct=risk_per_trade_pct,
                max_position_pct=economic_policy.max_position_pct,
            )
            self.stop_manager = StopLossManager(
                buffer_pct=economic_policy.stop_buffer_pct,
                min_tick=economic_policy.stop_min_tick,
            )
            self.portfolio_risk_manager = PortfolioRiskManager(
                max_total_risk_pct=economic_policy.max_total_risk_pct,
                max_open_trades=economic_policy.max_open_trades,
            )
            self.drawdown_manager = DrawdownRiskManager(
                max_daily_loss_pct=economic_policy.max_daily_loss_pct,
                max_weekly_loss_pct=economic_policy.max_weekly_loss_pct,
            )

        self.journal = TradeJournal(session_id=session_id)

        self.completed_trades: List[Trade] = []
        self.portfolio_manager = PortfolioManager(initial_capital=account_capital)

    # -------------------------------------------------
    def _get_open_position(
        self,
        symbol: str,
    ) -> Optional[Position]:

        return self.portfolio_manager.position_book.get_position(symbol)

    def _reset_execution_diagnostics(self) -> None:
        self.last_execution_event = None
        self.last_execution_price = None
        self.last_execution_quantity = None
        self.last_transaction_cost = 0.0

    @staticmethod
    def _require_finite(value: float, name: str) -> None:
        if not isfinite(value):
            raise ValueError(f"{name} must be finite")

    def _entry_cost(self, *, entry_price: float, quantity: int) -> float:
        if not self.runtime_context.execution_config.brokerage_enabled:
            return 0.0

        transaction_cost = self.brokerage_model.calculate(
            turnover=entry_price * quantity,
        ).total_cost
        self._require_finite(transaction_cost, "entry transaction cost")
        return transaction_cost

    def _largest_affordable_quantity(
        self,
        *,
        candidate_quantity: int,
        entry_price: float,
        available_cash: float,
    ) -> Optional[tuple[int, float]]:
        """Return the largest affordable quantity and its final entry cost."""

        self._require_finite(entry_price, "actual entry fill")
        self._require_finite(available_cash, "authoritative cash")

        if candidate_quantity < 1 or available_cash < 0:
            return None

        def required_cash(quantity: int) -> tuple[float, float]:
            transaction_cost = self._entry_cost(
                entry_price=entry_price,
                quantity=quantity,
            )
            required = entry_price * quantity + transaction_cost
            self._require_finite(required, "required entry cash")
            return required, transaction_cost

        full_required, full_cost = required_cash(candidate_quantity)
        if full_required <= available_cash:
            return candidate_quantity, full_cost

        low = 1
        high = candidate_quantity - 1
        best_quantity = 0

        while low <= high:
            midpoint = (low + high) // 2
            required, _ = required_cash(midpoint)
            if required <= available_cash:
                best_quantity = midpoint
                low = midpoint + 1
            else:
                high = midpoint - 1

        if best_quantity < 1:
            return None

        _, final_cost = required_cash(best_quantity)
        return best_quantity, final_cost

    def _entry_rejected(
        self,
        *,
        symbol: str,
        timestamp,
        reason: ExecutionRejectionReason,
    ) -> tuple[ExecutionFeedback, ...]:
        return (
            ExecutionFeedback(
                event_type=ExecutionFeedbackType.ENTRY_REJECTED,
                symbol=symbol,
                timestamp=timestamp,
                position_state=ExecutionPositionState.FLAT,
                rejection_reason=reason,
            ),
        )

    def _open_long(
        self,
        *,
        symbol: str,
        candle: Candle,
        reference_price: float,
        stop_price: Optional[float],
        entry_index: int,
        require_stop_below_fill: bool,
        use_current_equity_sizing: bool,
        observe_equity_risk: bool,
    ) -> tuple[ExecutionFeedback, ...]:
        """Attempt one authoritative long entry at the supplied reference."""

        if not self.drawdown_manager.can_trade():
            self.logger.info("TRADE REJECTED | Drawdown limit reached")
            return self._entry_rejected(
                symbol=symbol,
                timestamp=candle.timestamp,
                reason=ExecutionRejectionReason.DRAWDOWN_LIMIT,
            )

        if self.runtime_context.execution_config.slippage_enabled:
            entry_price = self.slippage_model.apply_buy_slippage(reference_price)
        else:
            entry_price = reference_price

        self._require_finite(entry_price, "actual entry fill")
        if (
            stop_price is None
            or not isfinite(stop_price)
            or entry_price <= 0
            or stop_price <= 0
        ):
            self.logger.info("TRADE REJECTED | Invalid entry price or stop")
            return self._entry_rejected(
                symbol=symbol,
                timestamp=candle.timestamp,
                reason=ExecutionRejectionReason.INVALID_ENTRY,
            )

        if require_stop_below_fill and stop_price >= entry_price:
            self.logger.info("TRADE REJECTED | Stop is not below actual entry fill")
            return self._entry_rejected(
                symbol=symbol,
                timestamp=candle.timestamp,
                reason=ExecutionRejectionReason.INVALID_ENTRY,
            )

        portfolio_state = self.portfolio_manager.snapshot()
        self._require_finite(portfolio_state.equity, "authoritative equity")
        self._require_finite(portfolio_state.cash, "authoritative cash")

        if use_current_equity_sizing:
            qty = self.risk_manager.calculate_position_size_for_equity(
                account_equity=portfolio_state.equity,
                entry_price=entry_price,
                stop_price=stop_price,
            )
        else:
            qty = self.risk_manager.calculate_position_size(
                entry_price=entry_price,
                stop_price=stop_price,
            )
        if qty is None:
            self.logger.info("TRADE REJECTED | Invalid quantity")
            return self._entry_rejected(
                symbol=symbol,
                timestamp=candle.timestamp,
                reason=ExecutionRejectionReason.INVALID_QUANTITY,
            )

        affordable = self._largest_affordable_quantity(
            candidate_quantity=qty,
            entry_price=entry_price,
            available_cash=portfolio_state.cash,
        )
        if affordable is None:
            self.logger.info("TRADE REJECTED | Insufficient cash")
            return self._entry_rejected(
                symbol=symbol,
                timestamp=candle.timestamp,
                reason=ExecutionRejectionReason.INSUFFICIENT_CASH,
            )
        qty, entry_transaction_cost = affordable

        if not self.portfolio_risk_manager.can_open_new_trade(
            open_trade_risks_pct=[],
            new_trade_risk_pct=self.risk_manager.risk_per_trade_pct,
        ):
            self.logger.info("TRADE REJECTED | Portfolio risk limit")
            return self._entry_rejected(
                symbol=symbol,
                timestamp=candle.timestamp,
                reason=ExecutionRejectionReason.PORTFOLIO_RISK_LIMIT,
            )

        self.last_transaction_cost = entry_transaction_cost
        position = Position(
            symbol=symbol,
            entry_price=entry_price,
            entry_transaction_cost=entry_transaction_cost,
            entry_time=candle.timestamp,
            entry_index=entry_index,
            quantity=qty,
            stop_price=stop_price,
            direction="LONG",
        )
        self.portfolio_manager.open_position(position)
        if observe_equity_risk:
            self.drawdown_manager.observe_equity(
                self.portfolio_manager.snapshot().equity
            )
        self.last_execution_event = "BUY"
        self.last_execution_price = entry_price
        self.last_execution_quantity = qty
        self.logger.info(
            f"LONG ENTRY | Price={entry_price:.2f} | "
            f"Qty={qty} | Stop={stop_price:.2f}"
        )
        return (
            ExecutionFeedback(
                event_type=ExecutionFeedbackType.ENTRY_ACCEPTED,
                symbol=symbol,
                timestamp=candle.timestamp,
                position_state=ExecutionPositionState.LONG,
                fill_price=entry_price,
                quantity=qty,
            ),
        )

    def _exit_long(
        self,
        *,
        symbol: str,
        candle: Candle,
        reference_price: float,
        exit_reason: str,
        event_type: ExecutionFeedbackType,
        diagnostic_event: str,
        observe_equity_risk: bool,
    ) -> ExecutionFeedback:
        open_position = self._get_open_position(symbol)
        if open_position is None:
            raise RuntimeError(f"Cannot close absent position for {symbol}")

        if self.runtime_context.execution_config.slippage_enabled:
            exit_price = self.slippage_model.apply_sell_slippage(reference_price)
        else:
            exit_price = reference_price
        self._require_finite(exit_price, "actual exit fill")
        exit_quantity = open_position.quantity
        self._close_position(
            symbol=symbol,
            exit_price=exit_price,
            exit_reason=exit_reason,
            candle=candle,
            observe_equity_risk=observe_equity_risk,
        )
        self.last_execution_event = diagnostic_event
        self.last_execution_price = exit_price
        self.last_execution_quantity = exit_quantity
        return ExecutionFeedback(
            event_type=event_type,
            symbol=symbol,
            timestamp=candle.timestamp,
            position_state=ExecutionPositionState.FLAT,
            fill_price=exit_price,
            quantity=exit_quantity,
        )

    def process_backtest_candle(
        self,
        *,
        pending_signal: Optional[SignalType],
        decision_close: Optional[float],
        rejection_midpoint: Optional[float],
        candle: Candle,
        execution_index: int,
        symbol: str,
    ) -> tuple[ExecutionFeedback, ...]:
        """Execute prior-bar intent and protection before current-bar decisions."""

        self._reset_execution_diagnostics()
        carried_equity = self.portfolio_manager.snapshot().equity
        self.drawdown_manager.update_equity_period(
            candle.timestamp,
            carried_equity,
        )
        open_position = self._get_open_position(symbol)

        if pending_signal == SignalType.SELL and open_position is None:
            raise RuntimeError(
                f"SELL signal received while authoritative position state is FLAT "
                f"for {symbol}"
            )
        if pending_signal == SignalType.BUY and open_position is not None:
            raise RuntimeError(
                f"BUY signal received while authoritative position state is LONG "
                f"for {symbol}"
            )

        if open_position is not None:
            if candle.open <= open_position.stop_price:
                return (
                    self._exit_long(
                        symbol=symbol,
                        candle=candle,
                        reference_price=candle.open,
                        exit_reason="STOP_LOSS",
                        event_type=ExecutionFeedbackType.PROTECTIVE_EXIT,
                        diagnostic_event="STOP_EXIT",
                        observe_equity_risk=True,
                    ),
                )
            if pending_signal == SignalType.SELL:
                return (
                    self._exit_long(
                        symbol=symbol,
                        candle=candle,
                        reference_price=candle.open,
                        exit_reason="STRATEGY_EXIT",
                        event_type=ExecutionFeedbackType.STRATEGY_EXIT,
                        diagnostic_event="SELL",
                        observe_equity_risk=True,
                    ),
                )
            if candle.low <= open_position.stop_price:
                return (
                    self._exit_long(
                        symbol=symbol,
                        candle=candle,
                        reference_price=open_position.stop_price,
                        exit_reason="STOP_LOSS",
                        event_type=ExecutionFeedbackType.PROTECTIVE_EXIT,
                        diagnostic_event="STOP_EXIT",
                        observe_equity_risk=True,
                    ),
                )
            return ()

        if pending_signal != SignalType.BUY:
            return ()

        if decision_close is None:
            stop_price = None
        elif rejection_midpoint is not None:
            stop_price = (
                self.stop_manager.compute_long_stop(rejection_midpoint)
                if isfinite(rejection_midpoint)
                else rejection_midpoint
            )
        else:
            stop_price = (
                decision_close
                * self._fallback_long_stop_multiplier
            )

        entry_feedback = self._open_long(
            symbol=symbol,
            candle=candle,
            reference_price=candle.open,
            stop_price=stop_price,
            entry_index=execution_index,
            require_stop_below_fill=True,
            use_current_equity_sizing=True,
            observe_equity_risk=True,
        )
        if entry_feedback[0].event_type is not ExecutionFeedbackType.ENTRY_ACCEPTED:
            return entry_feedback

        accepted_position = self._get_open_position(symbol)
        if accepted_position is None:
            raise RuntimeError("Accepted entry did not create authoritative position")
        if candle.low <= accepted_position.stop_price:
            protective_feedback = self._exit_long(
                symbol=symbol,
                candle=candle,
                reference_price=accepted_position.stop_price,
                exit_reason="STOP_LOSS",
                event_type=ExecutionFeedbackType.PROTECTIVE_EXIT,
                diagnostic_event="STOP_EXIT",
                observe_equity_risk=True,
            )
            return entry_feedback + (protective_feedback,)
        return entry_feedback

    def mark_open_position_to_market(self, *, symbol: str, price: float) -> None:
        """Mark an existing position after current-bar execution processing."""

        if self._get_open_position(symbol) is not None:
            self.portfolio_manager.mark_to_market({symbol: price})
            self.drawdown_manager.observe_equity(
                self.portfolio_manager.snapshot().equity
            )

    def on_signal(
        self,
        signal: Optional[SignalType],
        candle: Candle,
        series,
        symbol: str,
    ) -> tuple[ExecutionFeedback, ...]:

        self._reset_execution_diagnostics()

        open_position = self._get_open_position(symbol)

        if signal == SignalType.SELL and open_position is None:
            raise RuntimeError(
                f"SELL signal received while authoritative position state is FLAT "
                f"for {symbol}"
            )

        if signal == SignalType.BUY and open_position is not None:
            raise RuntimeError(
                f"BUY signal received while authoritative position state is LONG "
                f"for {symbol}"
            )

        self.drawdown_manager.update_period(candle.timestamp)

        # ---------------- NO POSITION ----------------

        if open_position is None:

            if signal != SignalType.BUY:
                return ()

            rejection_midpoint = getattr(
                self.strategy,
                "rejection_midpoint",
                None,
            )

            if rejection_midpoint is not None:

                stop_price = self.stop_manager.compute_long_stop(rejection_midpoint)

            else:

                stop_price = (
                    candle.close
                    * self._fallback_long_stop_multiplier
                )

            feedback = self._open_long(
                symbol=symbol,
                candle=candle,
                reference_price=candle.close,
                stop_price=stop_price,
                entry_index=len(series) - 1,
                require_stop_below_fill=False,
                use_current_equity_sizing=False,
                observe_equity_risk=False,
            )
            if feedback[0].event_type is ExecutionFeedbackType.ENTRY_ACCEPTED:
                self.portfolio_manager.mark_to_market({symbol: candle.close})
            return feedback

        # ---------------- POSITION OPEN ----------------
        open_position = self._get_open_position(symbol)

        if open_position is not None:

            self.portfolio_manager.mark_to_market(
                {
                    symbol: candle.close,
                }
            )

            if candle.low <= open_position.stop_price:

                return (
                    self._exit_long(
                        symbol=symbol,
                        candle=candle,
                        reference_price=open_position.stop_price,
                        exit_reason="STOP_LOSS",
                        event_type=ExecutionFeedbackType.PROTECTIVE_EXIT,
                        diagnostic_event="STOP_EXIT",
                        observe_equity_risk=False,
                    ),
                )

            if signal == SignalType.SELL:

                return (
                    self._exit_long(
                        symbol=symbol,
                        candle=candle,
                        reference_price=candle.close,
                        exit_reason="STRATEGY_EXIT",
                        event_type=ExecutionFeedbackType.STRATEGY_EXIT,
                        diagnostic_event="SELL",
                        observe_equity_risk=False,
                    ),
                )

        return ()

    # -------------------------------------------------

    def _close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_reason: str,
        candle: Candle,
        observe_equity_risk: bool,
    ) -> None:

        open_position = self._get_open_position(symbol)

        if open_position is None:
            return

        exit_transaction_cost = 0.0

        if self.runtime_context.execution_config.brokerage_enabled:
            turnover = exit_price * open_position.quantity
            exit_transaction_cost = self.brokerage_model.calculate(
                turnover=turnover,
            ).total_cost
        self._require_finite(exit_transaction_cost, "exit transaction cost")

        total_transaction_cost = (
            open_position.entry_transaction_cost + exit_transaction_cost
        )

        trade = TradeBuilder.build_long_trade(
            position=open_position,
            exit_price=exit_price,
            exit_reason=exit_reason,
            transaction_cost=total_transaction_cost,
            exit_time=candle.timestamp,
        )

        self.portfolio_manager.close_position(
            symbol=symbol,
            exit_price=exit_price,
            exit_transaction_cost=exit_transaction_cost,
        )
        if observe_equity_risk:
            self.drawdown_manager.observe_equity(
                self.portfolio_manager.snapshot().equity
            )
        else:
            account_pnl_pct = (
                trade.pnl / self.portfolio_manager.initial_capital
            ) * 100
            self.drawdown_manager.record_trade_pnl(account_pnl_pct)

        self.completed_trades.append(trade)

        self.journal.log_trade(trade)

        self.logger.info(
            f"POSITION CLOSED | "
            f"Reason={exit_reason} | "
            f"Entry={trade.entry_price:.2f} | "
            f"Exit={trade.exit_price:.2f} | "
            f"PnL%={trade.pnl_pct:.2f}"
        )

    def get_runtime_position(
        self,
        symbol: str,
    ) -> Optional[Position]:
        """
        Return current runtime-managed position.
        Used for reconciliation and monitoring.
        """

        return self._get_open_position(symbol)

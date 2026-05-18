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

from core.execution.execution_cost_model import (
    ExecutionCostModel,
)

from core.strategies.base_strategy import (
    BaseStrategy,
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
        risk_per_trade_pct: float = 1.0,
    ):

        self.strategy = strategy
        self.session_id = session_id

        self.logger = get_logger(__name__)

        self.last_execution_event = None

        self.last_execution_price = None

        self.last_execution_quantity = None

        self.risk_manager = RiskManager(
            account_capital=account_capital,
            risk_per_trade_pct=risk_per_trade_pct,
        )

        self.stop_manager = StopLossManager()

        self.portfolio_risk_manager = PortfolioRiskManager()

        self.drawdown_manager = DrawdownRiskManager()

        self.cost_model = ExecutionCostModel()

        self.journal = TradeJournal(session_id=session_id)

        self.open_position: Optional[Position] = None

        self.completed_trades: List[Trade] = []

    # -------------------------------------------------

    def on_signal(
        self,
        signal: Optional[SignalType],
        candle: Candle,
        series,
    ) -> None:

        self.last_execution_event = None

        self.last_execution_price = None

        self.last_execution_quantity = None

        # ---------------- NO POSITION ----------------
        if self.open_position is None:

            if signal != SignalType.BUY:
                return

            if not self.drawdown_manager.can_trade():
                return

            rejection_midpoint = getattr(
                self.strategy,
                "rejection_midpoint",
                None,
            )

            if rejection_midpoint is not None:

                stop_price = self.stop_manager.compute_long_stop(rejection_midpoint)

            else:

                stop_price = candle.close * 0.98

            if stop_price is None:
                return

            raw_entry_price = candle.close

            entry_price = self.cost_model.apply_buy_costs(raw_entry_price)

            qty = self.risk_manager.calculate_position_size(
                entry_price=entry_price,
                stop_price=stop_price,
            )

            if qty is None:
                return

            if not self.portfolio_risk_manager.can_open_new_trade(
                open_trade_risks_pct=[],
                new_trade_risk_pct=(self.risk_manager.risk_per_trade_pct),
            ):
                return

            self.open_position = Position(
                entry_price=entry_price,
                entry_time=candle.timestamp,
                entry_index=len(series) - 1,
                quantity=qty,
                stop_price=stop_price,
                direction="LONG",
            )

            self.last_execution_event = "BUY"

            self.last_execution_price = candle.close

            self.last_execution_quantity = qty

            self.logger.info(
                f"LONG ENTRY | "
                f"Price={entry_price:.2f} | "
                f"Qty={qty} | "
                f"Stop={stop_price:.2f}"
            )

        # ---------------- POSITION OPEN ----------------
        else:

            if candle.low <= self.open_position.stop_price:

                exit_price = self.cost_model.apply_sell_costs(
                    self.open_position.stop_price
                )

                exit_quantity = self.open_position.quantity

                self._close_position(
                    exit_price=exit_price,
                    exit_reason="STOP_LOSS",
                    candle=candle,
                )
                self.last_execution_event = "STOP_EXIT"

                self.last_execution_price = exit_price

                self.last_execution_quantity = exit_quantity

                return

            if signal == SignalType.SELL:

                exit_price = self.cost_model.apply_sell_costs(candle.close)
                exit_quantity = self.open_position.quantity

                self._close_position(
                    exit_price=exit_price,
                    exit_reason="STRATEGY_EXIT",
                    candle=candle,
                )

                self.last_execution_event = "SELL"
                self.last_execution_price = exit_price
                self.last_execution_quantity = exit_quantity

    # -------------------------------------------------

    def _close_position(
        self,
        exit_price: float,
        exit_reason: str,
        candle: Candle,
    ) -> None:

        if self.open_position is None:
            return

        trade = TradeBuilder.build_long_trade(
            position=self.open_position,
            exit_price=exit_price,
            exit_reason=exit_reason,
            exit_time=candle.timestamp,
        )

        self.drawdown_manager.record_trade_pnl(trade.pnl_pct)

        self.completed_trades.append(trade)

        self.journal.log_trade(trade)

        self.logger.info(
            f"POSITION CLOSED | "
            f"Reason={exit_reason} | "
            f"Entry={trade.entry_price:.2f} | "
            f"Exit={trade.exit_price:.2f} | "
            f"PnL%={trade.pnl_pct:.2f}"
        )

        self.open_position = None

    def get_runtime_position(self) -> Optional[Position]:
        """
        Return current runtime-managed position.
        Used for reconciliation and monitoring.
        """

        return self.open_position

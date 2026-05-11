from typing import List, Dict, Optional

from core.risk.risk_manager import RiskManager
from core.risk.stop_loss_manager import StopLossManager
from core.risk.portfolio_risk_manager import PortfolioRiskManager
from core.risk.drawdown_risk_manager import DrawdownRiskManager

from core.entities.candle import Candle
from core.entities.trade import Trade

from core.journal.trade_journal import TradeJournal

from core.entities.position import Position

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
        risk_per_trade_pct: float = 1.0,
    ):

        self.strategy = strategy

        self.risk_manager = RiskManager(
            account_capital=account_capital,
            risk_per_trade_pct=risk_per_trade_pct,
        )

        self.stop_manager = StopLossManager()

        self.portfolio_risk_manager = (
            PortfolioRiskManager()
        )

        self.drawdown_manager = (
            DrawdownRiskManager()
        )

        self.cost_model = ExecutionCostModel()

        self.journal = TradeJournal()

        self.open_position: Optional[position] = None

        self.completed_trades: List[Trade] = []

    # -------------------------------------------------

    def on_signal(
        self,
        signal,
        candle: Candle,
        series,
    ) -> None:

        # ---------------- NO POSITION ----------------
        if self.open_position is None:

            if signal != "BUY":
                return

            if not self.drawdown_manager.can_trade():
                return

            rejection_midpoint = getattr(
                self.strategy,
                "rejection_midpoint",
                None,
            )

            if rejection_midpoint is not None:

                stop_price = (
                    self.stop_manager.compute_long_stop(
                        rejection_midpoint
                    )
                )

            else:

                stop_price = (
                    candle.close * 0.98
                )

            if stop_price is None:
                return

            raw_entry_price = candle.close

            entry_price = (
                self.cost_model.apply_buy_costs(
                    raw_entry_price
                )
            )

            qty = (
                self.risk_manager.calculate_position_size(
                    entry_price=entry_price,
                    stop_price=stop_price,
                )
            )

            if qty is None:
                return

            if not self.portfolio_risk_manager.can_open_new_trade(
                open_trade_risks_pct=[],
                new_trade_risk_pct=(
                    self.risk_manager.risk_per_trade_pct
                ),
            ):
                return

            self.open_position = Position(
                entry_price = entry_price,
                entry_time = candle.timestamp,
                entry_index = len(series) - 1,
                quantity = qty,
                stop_price = stop_price,
                direction = "LONG",
            )

        # ---------------- POSITION OPEN ----------------
        else:

            if candle.low <= self.open_position.stop_price:

                exit_price = (
                    self.cost_model.apply_sell_costs(
                        self.open_position.stop_price
                    )
                )

                self._close_position(
                    exit_price=exit_price,
                    exit_reason="STOP_LOSS",
                    candle=candle,
                )

                return

            if signal == "SELL":

                exit_price = (
                    self.cost_model.apply_sell_costs(
                        candle.close
                    )
                )

                self._close_position(
                    exit_price=exit_price,
                    exit_reason="STRATEGY_EXIT",
                    candle=candle,
                )

    # -------------------------------------------------

    def _close_position(
        self,
        exit_price: float,
        exit_reason: str,
        candle: Candle,
    ) -> None:

        if self.open_position is None:
            return

        entry_price = (
            self.open_position.entry_price
        )

        quantity = (
            self.open_position.quantity
        )

        pnl = (
            exit_price - entry_price
        ) * quantity

        pnl_pct = (
            (exit_price - entry_price)
            / entry_price
        ) * 100

        trade = Trade(
            entry_time=(
                self.open_position.entry_time
            ),
            entry_price=entry_price,
            exit_time=candle.timestamp,
            exit_price=exit_price,
            stop_price=(
                self.open_position.stop_price
            ),
            quantity=quantity,
            direction=(
                self.open_position.direction
            ),
            exit_reason=exit_reason,
            pnl=pnl,
            pnl_pct=pnl_pct,
        )

        self.drawdown_manager.record_trade_pnl(
            pnl_pct
        )

        self.completed_trades.append(
            trade
        )

        self.journal.log_trade(
            trade
        )

        self.open_position = None
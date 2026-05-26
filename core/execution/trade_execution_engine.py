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
    ):

        self.strategy = strategy
        self.session_id = session_id
        self.runtime_context = runtime_context
        self.brokerage_model = BrokerageModel()
        self.slippage_model = SlippageModel(
            slippage_pct=(self.runtime_context.execution_config.slippage_pct)
        )

        self.logger = get_logger(__name__)

        self.last_execution_event = None

        self.last_execution_price = None

        self.last_execution_quantity = None
        self.last_transaction_cost = 0.0

        self.risk_manager = RiskManager(
            account_capital=account_capital,
            risk_per_trade_pct=risk_per_trade_pct,
        )

        self.stop_manager = StopLossManager()

        self.portfolio_risk_manager = PortfolioRiskManager()

        self.drawdown_manager = DrawdownRiskManager()

        self.cost_model = ExecutionCostModel()

        self.journal = TradeJournal(session_id=session_id)

        self.completed_trades: List[Trade] = []
        self.portfolio_manager = PortfolioManager(initial_capital=account_capital)

    # -------------------------------------------------
    def _get_open_position(
        self,
        symbol: str,
    ) -> Optional[Position]:

        return self.portfolio_manager.position_book.get_position(symbol)

    def on_signal(
        self,
        signal: Optional[SignalType],
        candle: Candle,
        series,
        symbol: str,
    ) -> None:

        self.last_execution_event = None

        self.last_execution_price = None

        self.last_execution_quantity = None

        # ---------------- NO POSITION ----------------

        open_position = self._get_open_position(symbol)
        if open_position is None:

            if signal != SignalType.BUY:
                return

            if not self.drawdown_manager.can_trade():
                self.logger.info("TRADE REJECTED | Drawdown limit reached")
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

            if self.runtime_context.execution_config.slippage_enabled:

                slipped_entry_price = self.slippage_model.apply_buy_slippage(
                    raw_entry_price
                )

            else:

                slipped_entry_price = raw_entry_price

            entry_price = self.cost_model.apply_buy_costs(slipped_entry_price)

            qty = self.risk_manager.calculate_position_size(
                entry_price=entry_price,
                stop_price=stop_price,
            )

            if qty is None:

                self.logger.info("TRADE REJECTED | Invalid quantity")

                return

            turnover = entry_price * qty

            costs = self.brokerage_model.calculate(
                turnover=turnover,
            )

            self.last_transaction_cost = costs.total_cost

            entry_transaction_cost = costs.total_cost

            if not self.portfolio_risk_manager.can_open_new_trade(
                open_trade_risks_pct=[],
                new_trade_risk_pct=(self.risk_manager.risk_per_trade_pct),
            ):
                return

            position = Position(
                symbol=symbol,
                entry_price=entry_price,
                entry_transaction_cost=entry_transaction_cost,
                entry_time=candle.timestamp,
                entry_index=len(series) - 1,
                quantity=qty,
                stop_price=stop_price,
                direction="LONG",
            )

            self.portfolio_manager.add_position(
                symbol=symbol,
                position=position,
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
        open_position = self._get_open_position(symbol)

        if open_position is not None:

            if candle.low <= open_position.stop_price:

                if self.runtime_context.execution_config.slippage_enabled:

                    slipped_stop_price = self.slippage_model.apply_sell_slippage(
                        open_position.stop_price
                    )

                else:

                    slipped_stop_price = open_position.stop_price

                exit_price = self.cost_model.apply_sell_costs(slipped_stop_price)

                exit_quantity = open_position.quantity

                self._close_position(
                    symbol=symbol,
                    exit_price=exit_price,
                    exit_reason="STOP_LOSS",
                    candle=candle,
                )
                self.last_execution_event = "STOP_EXIT"

                self.last_execution_price = exit_price

                self.last_execution_quantity = exit_quantity

                return

            if signal == SignalType.SELL:

                if self.runtime_context.execution_config.slippage_enabled:

                    slipped_exit_price = self.slippage_model.apply_sell_slippage(
                        candle.close
                    )

                else:

                    slipped_exit_price = candle.close

                exit_price = self.cost_model.apply_sell_costs(slipped_exit_price)
                exit_quantity = open_position.quantity

                self._close_position(
                    symbol=symbol,
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
        symbol: str,
        exit_price: float,
        exit_reason: str,
        candle: Candle,
    ) -> None:

        open_position = self._get_open_position(symbol)

        if open_position is None:
            return

        turnover = exit_price * open_position.quantity

        exit_costs = self.brokerage_model.calculate(
            turnover=turnover,
        )

        total_transaction_cost = (
            open_position.entry_transaction_cost + exit_costs.total_cost
        )

        trade = TradeBuilder.build_long_trade(
            position=open_position,
            exit_price=exit_price,
            exit_reason=exit_reason,
            transaction_cost=total_transaction_cost,
            exit_time=candle.timestamp,
        )

        self.drawdown_manager.record_trade_pnl(trade.pnl_pct)

        self.completed_trades.append(trade)
        self.portfolio_manager.remove_position(symbol)
        self.portfolio_manager.record_realized_pnl(trade.pnl)

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

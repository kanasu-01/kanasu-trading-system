from typing import Optional, Dict

from core.broker.base_broker import BaseBroker
from core.execution.order import Order, OrderSide, OrderType
from core.execution.order_response import OrderStatus
from core.entities.candle import Candle
from core.entities.position import Position
from core.entities.trade import Trade
from core.risk.risk_manager import RiskManager
from core.risk.stop_loss_manager import StopLossManager
from core.risk.portfolio_risk_manager import PortfolioRiskManager
from core.risk.drawdown_risk_manager import DrawdownRiskManager
from core.execution.execution_cost_model import ExecutionCostModel
from core.execution.trade_builder import TradeBuilder
from core.journal.trade_journal import TradeJournal
from core.risk.live_risk_guard import LiveRiskGuard
from core.risk.kill_switch import KillSwitch
from core.strategies.signal import SignalType


class BrokerExecutionEngine:
    """
    Broker-backed execution engine with full live safety stack.
    """

    def __init__(
        self,
        strategy,
        broker: BaseBroker,
        account_capital: float,
        risk_per_trade_pct: float = 1.0,
        enable_live_trading: bool = False,
    ):
        self.strategy = strategy
        self.broker = broker
        self.enable_live_trading = enable_live_trading

        self.risk_manager = RiskManager(
            account_capital=account_capital,
            risk_per_trade_pct=risk_per_trade_pct,
        )

        self.stop_manager = StopLossManager()
        self.portfolio_risk_manager = PortfolioRiskManager()
        self.drawdown_manager = DrawdownRiskManager()
        self.cost_model = ExecutionCostModel()
        self.journal = TradeJournal()

        self.live_guard = LiveRiskGuard(min_required_balance=account_capital * 0.9)
        self.kill_switch = KillSwitch()

        self.open_position: Optional[Position] = None

    def on_new_candle(self, candle: Candle, series) -> None:
        if self.kill_switch.is_active():
            if self.open_position:
                self._force_exit(candle, "KILL_SWITCH")
            return

        signal = self.strategy.on_new_candle(series)
        signal: Optional[SignalType]

        if self.open_position is None:
            if signal != SignalType.BUY:
                return
            if not self.enable_live_trading:
                return
            if not self.live_guard.validate(self.broker):
                self.kill_switch.activate("LIVE_RISK_FAILED")
                return
            if not self.drawdown_manager.can_trade():
                return

            stop_price = self.stop_manager.compute_long_stop(
                self.strategy.rejection_midpoint
            )
            if stop_price is None:
                return

            entry_price = self.cost_model.apply_buy_costs(candle.close)
            qty = self.risk_manager.calculate_position_size(
                entry_price=entry_price,
                stop_price=stop_price,
            )
            if qty is None:
                return

            order = Order(
                symbol=candle.symbol,
                side=OrderSide.BUY,
                quantity=qty,
                order_type=OrderType.MARKET,
            )

            response = self.broker.place_order(order)
            if response.status != OrderStatus.FILLED:
                return

            self.open_position = Position(
                entry_time=candle.timestamp,
                entry_price=(response.filled_price or entry_price),
                entry_index=len(series) - 1,
                quantity=qty,
                stop_price=stop_price,
                direction="LONG",
            )

        else:
            if candle.low <= self.open_position.stop_price:
                self._exit_position(candle, "STOP_LOSS")
            elif signal == SignalType.SELL:
                self._exit_position(candle, "STRATEGY_EXIT")

    def _exit_position(self, candle: Candle, reason: str) -> None:
        exit_price = self.cost_model.apply_sell_costs(candle.close)

        order = Order(
            symbol=candle.symbol,
            side=OrderSide.SELL,
            quantity=self.open_position.quantity,
            order_type=OrderType.MARKET,
        )

        response = self.broker.place_order(order)
        if response.status != OrderStatus.FILLED:
            return

        self._record_trade(exit_price, reason)
        self.open_position = None

    def _force_exit(self, candle: Candle, reason: str) -> None:
        try:
            self._exit_position(candle, reason)
        except Exception:
            pass

    def _record_trade(self, exit_price: float, reason: str) -> None:
        if self.open_position is None:
            return

        trade = TradeBuilder.build_long_trade(
            position=self.open_position,
            exit_price=exit_price,
            exit_reason=reason,
            exit_time=None,
        )

        self.drawdown_manager.record_trade_pnl(trade.pnl_pct)

        self.journal.log_trade(trade)

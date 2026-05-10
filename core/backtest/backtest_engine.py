from typing import List, Dict, Optional

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.strategies.strategy_runner import StrategyRunner
from core.strategies.base_strategy import BaseStrategy
from core.backtest.bar_record import BarRecorder
from core.portfolio.portfolio_manager import PortfolioManager
from core.execution.trade_execution_engine import TradeExecutionEngine


class BacktestEngine:
    """
    Runs a candle-by-candle backtest and records bar-level strategy decisions.
    Strategy-agnostic by design.
    """

    def __init__(self, strategy: BaseStrategy):
        self.strategy = strategy
        self.runner = StrategyRunner(strategy)

        self.trades: List[Dict] = []
        self.bar_recorder = BarRecorder()

        self.execution_engine = TradeExecutionEngine(
            strategy=strategy,
            account_capital=100000,
        )

    # -------------------------------------------------
    # Internal engine (used by both batch & stream)
    # -------------------------------------------------

    def _run_internal(self, candles) -> List[Dict]:
        series = CandleSeries([])
        self.runner.start(series)

        current_trade: Optional[Dict] = None

        # Portfolio manager
        portfolio = PortfolioManager(initial_capital=100000)

        for candle in candles:

            signal = self.runner.on_new_candle(candle)

            self.execution_engine.on_signal(
                signal=signal,
                candle=candle,
                series=series,
            )

            print(self.execution_engine.completed_trades)

            # -----------------------------------------
            # TRADE ENTRY
            # -----------------------------------------

            if signal == "BUY" and current_trade is None:

                current_trade = {
                    "entry_time": candle.timestamp,
                    "entry_price": candle.close,
                }

                portfolio.buy(candle.close)

            # -----------------------------------------
            # TRADE EXIT
            # -----------------------------------------

            elif signal == "SELL" and current_trade is not None:

                portfolio.sell(candle.close)

                exit_price = candle.close
                entry_price = current_trade["entry_price"]

                pnl = exit_price - entry_price
                pnl_pct = (pnl / entry_price) * 100

                current_trade.update(
                    {
                        "exit_time": candle.timestamp,
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct,
                        "holding_period": (
                            candle.timestamp - current_trade["entry_time"]
                        ),
                    }
                )

                self.trades.append(current_trade)
                current_trade = None

            # -----------------------------------------
            # PORTFOLIO UPDATE
            # -----------------------------------------

            portfolio.update_equity(candle.close)

            state = portfolio.snapshot()

            # -----------------------------------------
            # BAR RECORDING
            # -----------------------------------------

            self.bar_recorder.record(
                candle=candle,
                strategy=self.strategy,
                signal=signal,
                equity=state.equity,
                cash=state.cash,
                position_size=state.position_size,
                drawdown=state.drawdown,
            )

        return self.trades

    # -------------------------------------------------
    # Public APIs
    # -------------------------------------------------

    def run(self, candles: List[Candle]) -> List[Dict]:
        """
        Backward-compatible bulk backtest method.
        """
        return self._run_internal(candles)

    def run_stream(self, candle_stream) -> List[Dict]:
        """
        Stream-based backtest method.
        """
        return self._run_internal(candle_stream)

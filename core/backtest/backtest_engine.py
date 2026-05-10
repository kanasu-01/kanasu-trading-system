from typing import List, Dict, Optional

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.strategies.strategy_runner import StrategyRunner
from core.strategies.base_strategy import BaseStrategy
from core.backtest.bar_record import BarRecorder
from core.portfolio.portfolio_manager import PortfolioManager
from core.execution.trade_execution_engine import TradeExecutionEngine
from core.entities.trade import Trade


class BacktestEngine:
    """
    Runs a candle-by-candle backtest and records bar-level strategy decisions.
    Strategy-agnostic by design.
    """

    def __init__(self, strategy: BaseStrategy, initial_capital: float,):
        self.strategy = strategy
        self.initial_capital = initial_capital
        self.runner = StrategyRunner(strategy)

        self.bar_recorder = BarRecorder()

        self.execution_engine = TradeExecutionEngine(
            strategy=strategy,
            account_capital=initial_capital,
        )

    # -------------------------------------------------
    # Internal engine (used by both batch & stream)
    # -------------------------------------------------

    def _run_internal(self, candles) -> List[Trade]:
        series = CandleSeries([])
        self.runner.start(series)

        #current_trade: Optional[Dict] = None

        # Portfolio manager
        portfolio = PortfolioManager(initial_capital=self.initial_capital)

        for candle in candles:

            signal = self.runner.on_new_candle(candle)

            self.execution_engine.on_signal(
                signal=signal,
                candle=candle,
                series=series,
            )

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

        return self.execution_engine.completed_trades

    # -------------------------------------------------
    # Public APIs
    # -------------------------------------------------

    def run(self, candles: List[Candle]) -> List[Trade]:
        """
        Backward-compatible bulk backtest method.
        """
        return self._run_internal(candles)

    def run_stream(self, candle_stream) -> List[Trade]:
        """
        Stream-based backtest method.
        """
        return self._run_internal(candle_stream)

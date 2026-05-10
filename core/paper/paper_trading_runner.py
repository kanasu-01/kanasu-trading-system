from typing import List, Dict

from core.execution.trade_execution_engine import TradeExecutionEngine
from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries

from core.strategies.base_strategy import BaseStrategy
from core.entities.trade import Trade
from core.strategies.strategy_runner import (
    StrategyRunner,
)

class PaperTradingRunner:
    """
    Paper trading runner using historical data.
    """

    def __init__(
        self,
        candles: List[Candle],
        strategy: BaseStrategy,
        initial_capital: float = 1_000_000,
    ):
        self.series = CandleSeries()
        self.candles = candles

        self.strategy = strategy
        self.runner = StrategyRunner(self.strategy)
        self.execution_engine = TradeExecutionEngine(
            strategy=self.strategy,
            account_capital=initial_capital,
        )

    def run(self) -> List[Trade]:
        self.runner.start(self.series)

        for candle in self.candles:

            signal = self.runner.on_new_candle(
            candle
            )

            self.execution_engine.on_signal(
                signal=signal,
                candle=candle,
                series=self.series,
            )

        return self.execution_engine.completed_trades

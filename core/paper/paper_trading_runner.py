from typing import List
import uuid

from core.logging.logger import get_logger
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
        self.logger = get_logger(__name__)
        self.session_id = str(uuid.uuid4())[:8]
        self.runner = StrategyRunner(self.strategy)
        self.execution_engine = TradeExecutionEngine(
            strategy=self.strategy,
            account_capital=initial_capital,
            session_id=self.session_id,
        )

    def run(self) -> List[Trade]:
        self.logger.info(
            f"PAPER TRADING STARTED | "
            f"Session={self.session_id} | "
            f"Strategy={self.strategy.name}"
        )
        self.runner.start(self.series)

        for candle in self.candles:

            signal = self.runner.on_new_candle(candle)

            self.execution_engine.on_signal(
                signal=signal,
                candle=candle,
                series=self.series,
            )

        self.logger.info(
            f"PAPER TRADING COMPLETED | "
            f"Session={self.session_id} | "
            f"Trades={len(self.execution_engine.completed_trades)}"
        )
        
        return self.execution_engine.completed_trades

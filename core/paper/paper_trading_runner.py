from typing import List

from core.execution.trade_execution_engine import TradeExecutionEngine
from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.strategies.pivotboss_swing_strategy import PivotBossSwingStrategy
from core.risk.risk_metrics import RiskMetrics


class PaperTradingRunner:
    """
    Paper trading runner using historical data.
    """

    def __init__(
        self,
        candles: List[Candle],
        initial_capital: float = 1_000_000,
    ):
        self.series = CandleSeries()
        self.candles = candles

        self.strategy = PivotBossSwingStrategy()
        self.execution_engine = TradeExecutionEngine(
            strategy=self.strategy,
            account_capital=initial_capital,
        )

    def run(self) -> None:
        for candle in self.candles:
            self.series.add(candle)
            self.execution_engine.on_new_candle(candle, self.series)

        self._print_summary()

    def _print_summary(self) -> None:
        trades = self.execution_engine.completed_trades
        stats = RiskMetrics.summarize(trades)

        print("\nPAPER TRADING SUMMARY")
        for k, v in stats.items():
            print(f"{k}: {v}")

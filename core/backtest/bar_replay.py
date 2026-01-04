from typing import List

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.strategies.strategy_runner import StrategyRunner
from core.strategies.pivotboss_swing_strategy import PivotBossSwingStrategy


class BarByBarReplay:
    """
    Text-based bar-by-bar replay for strategy validation.
    """

    def __init__(self, strategy: PivotBossSwingStrategy):
        self.strategy = strategy
        self.runner = StrategyRunner(strategy)

    def run(self, candles: List[Candle]) -> None:
        series = CandleSeries([])
        self.runner.start(series)

        print("\n--- BAR BY BAR REPLAY START ---\n")

        for idx, candle in enumerate(candles, start=1):
            signal = self.runner.on_new_candle(candle)

            state = self.strategy.state.value

            print(
                f"{idx:04d} | "
                f"{candle.timestamp} | "
                f"Close: {candle.close:.2f} | "
                f"State: {state} | "
                f"Signal: {signal}"
            )

        print("\n--- BAR BY BAR REPLAY END ---\n")

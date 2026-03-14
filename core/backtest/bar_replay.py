from typing import List

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.strategies.strategy_runner import StrategyRunner
from core.strategies.pivotboss_swing_strategy import PivotBossSwingStrategy
from core.strategies.base_strategy import BaseStrategy


class BarByBarReplay:
    """
    Text-based bar-by-bar replay for strategy validation.
    """

    def __init__(self, strategy: BaseStrategy):
        self.strategy = strategy
        self.runner = StrategyRunner(strategy)

    def _run_internal(self, candles) -> None:
        series = CandleSeries([])
        self.runner.start(series)
        """
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
        """
        
    def run(self, candles:List[Candle]) -> None:
        """
               Replay using a list of candles (backward compatible).
        """
        self._run_internal(candles)
        
    def run_stream(self, candle_stream) -> None:
        """
        Replay using a candle stream (generator).
        """
        self._run_internal(candle_stream)
        
    def run_from_records(self, records) -> None:
        """
        Replay using recorded bar data (No API calls).
        """
        print("\n--- BAR BY BAR REPLAY START ---\n")

        for idx, r in enumerate(records, start=1):

            print(
                f"{idx:04d} | "
                f"{r.timestamp} | "
                f"Close: {r.close:.2f} | "
                f"State: {r.state} | "
                f"Signal: {r.signal}"
            )
            
            if r.decision_snapshot:
                for k, v in r.decision_snapshot.items():
                    print(f"    {k}: {v}")
            
        print("\n--- BAR BY BAR REPLAY END ---\n")

        
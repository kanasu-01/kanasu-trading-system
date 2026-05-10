from typing import Optional

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.strategies.base_strategy import BaseStrategy


class StrategyRunner:
    """
    Manages the lifecycle of a strategy.
    Feeds candles and collects signals safely.
    """

    def __init__(self, strategy: BaseStrategy):
        self.strategy = strategy
        self.series: CandleSeries | None = None

    def start(self, series: CandleSeries) -> None:
        """
        Starts the strategy with initial candle data.
        """
        self.series = series
        self.strategy.reset()

    def on_new_candle(self,
        candle: Candle
    ) -> Optional[str]:
        """
        Called whenever a new candle arrives.
        """
        if self.series is None:
            raise RuntimeError("StrategyRunner not started")

        self.series.append(candle)
        
        warmup_required = (
            self.strategy.warmup_bars()
            )
        
        if len(self.series) < warmup_required:
            return None  # Not enough data to generate signals yet
        
        return self.strategy.on_new_candle(self.series)

    def stop(self) -> None:
        """
        Stops the strategy.
        """
        self.strategy.reset()

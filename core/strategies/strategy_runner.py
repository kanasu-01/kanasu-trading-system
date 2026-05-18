from typing import Optional

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import SignalType
from core.logging.logger import get_logger


class StrategyRunner:
    """
    Manages the lifecycle of a strategy.
    Feeds candles and collects signals safely.
    """

    def __init__(self, strategy: BaseStrategy):
        self.strategy = strategy
        self.logger = get_logger(__name__)
        self.series: CandleSeries | None = None

    def start(self, series: CandleSeries) -> None:
        """
        Starts the strategy with initial candle data.
        """
        self.series = series
        self.strategy.reset()

    def on_new_candle(self, candle: Candle) -> Optional[SignalType]:
        """
        Called whenever a new candle arrives.
        """
        if self.series is None:
            raise RuntimeError("StrategyRunner not started")

        self.series.append(candle)

        warmup_required = self.strategy.warmup_bars()

        if len(self.series) < warmup_required:
            return None  # Not enough data to generate signals yet

        signal = self.strategy.on_new_candle(self.series)

        if signal is not None:

            self.logger.info(
                f"STRATEGY SIGNAL | "
                f"Strategy={self.strategy.name} | "
                f"Signal={signal.value} | "
                f"Time={candle.timestamp}"
            )

        return signal

    def stop(self) -> None:
        """
        Stops the strategy.
        """
        self.strategy.reset()

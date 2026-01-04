from typing import List

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.metrics.range_metrics import RangeMetrics


class EffortResultMetrics:
    """
    Measures the relationship between trading effort (volume)
    and price result (range).
    """

    @staticmethod
    def effort_result_ratio(candle: Candle) -> float:
        price_range = RangeMetrics.range(candle)

        if price_range == 0:
            return 0.0

        return candle.volume / price_range

    @staticmethod
    def average_effort_result(
        series: CandleSeries,
        window: int
    ) -> float:
        if window <= 0:
            raise ValueError("Window must be positive")

        if len(series) < window:
            raise ValueError("Not enough candles")

        ratios: List[float] = [
            EffortResultMetrics.effort_result_ratio(candle)
            for candle in series
        ]

        recent = ratios[-window:]
        return sum(recent) / window

from typing import List
from core.entities.candle_series import CandleSeries
from core.metrics.range_metrics import RangeMetrics

class VolatilityMetrics:
    """
    Measures whether price volatility is contracting or expanding.
    """
    @staticmethod
    def average_range(
        series: CandleSeries,
        window: int
    ) -> float:
        if window <= 0:
            raise ValueError("window must be positive.")
        
        if len(series) < window:
            raise ValueError("Not enough data to compute average range.")
        
        ranges: List[float] = [
            RangeMetrics.range(candle)
                for candle in series
                ]
        recent_ranges = ranges[-window:]
        return sum(recent_ranges) / window
    
    @staticmethod
    def is_volatility_contracting(
        series: CandleSeries,
        short_window: int,
        long_window: int
    ) -> bool:
        if short_window >= long_window:
            raise ValueError("short_window must be less than long_window.")
        short_avg = VolatilityMetrics.average_range(series, short_window)
        long_avg = VolatilityMetrics.average_range(series, long_window)

        return short_avg < long_avg
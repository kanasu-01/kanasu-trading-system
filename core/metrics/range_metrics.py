from typing import List, Optional

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries

class RangeMetrics:
    """
    Computes price range related metrics required for
    volatility and Wyckoff-style analysis.
    """
    @staticmethod
    def true_range(
        current: Candle,
        previous: Optional[Candle]
    ) -> float:
        if previous is None: # First candle case
            return current.high - current.low
        return max(
            current.high - current.low,
            abs(current.high - previous.close),
            abs(current.low - previous.close)
        )
        
    @staticmethod
    def range(
        candle: Candle
    ) -> float:
        return candle.high - candle.low
    
    @staticmethod
    def true_range_series(
        series: CandleSeries
    ) -> List[float]:
        true_ranges: List[float] = []
        previous: Optional[Candle] = None
        for candle in series:
            tr = RangeMetrics.true_range(candle, previous)
            true_ranges.append(tr)
            previous = candle
        return true_ranges
    
    @staticmethod
    def average_true_range(
        series: CandleSeries,
        window: int
    ) -> float:
        if window <= 0:
            raise ValueError("Period must be positive.")
        
        if len(series) < window:
            raise ValueError("Not enough data to compute ATR.")
        
        true_ranges = RangeMetrics.true_range_series(series)
        recent_tr = true_ranges[-window:]
        return sum(recent_tr) / window
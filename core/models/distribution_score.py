from core.entities.candle_series import CandleSeries
from core.metrics.volatility_metrics import VolatilityMetrics
from core.metrics.effort_result_metrics import EffortResultMetrics


class DistributionScorer:
    """
    Computes a distribution probability score (0–100)
    using Wyckoff principles.
    """

    def __init__(
        self,
        volatility_weight: float = 0.4,
        effort_result_weight: float = 0.6
    ):
        self.volatility_weight = volatility_weight
        self.effort_result_weight = effort_result_weight

    def score(
        self,
        series: CandleSeries,
        short_window: int = 5,
        long_window: int = 20,
        effort_window: int = 10
    ) -> float:
        score = 0.0

        # 1. Volatility contraction (price stuck)
        if VolatilityMetrics.is_volatility_contracting(
            series,
            short_window,
            long_window
        ):
            score += 100 * self.volatility_weight

        # 2. Effort vs Result (selling absorption)
        avg_effort = EffortResultMetrics.average_effort_result(
            series,
            effort_window
        )

        if avg_effort > 0:
            score += 100 * self.effort_result_weight

        return round(score, 2)

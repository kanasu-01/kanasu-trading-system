from typing import List, Dict, Any

from core.backtest.performance_metrics import PerformanceMetrics


# ==========================================================
# WALK-FORWARD METRICS
# ==========================================================

class WalkForwardMetrics:
    """
    Computes walk-forward level metrics and stability scores.
    """

    # ------------------------------------------------------
    # Per-window metrics
    # ------------------------------------------------------

    def compute(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute metrics for a single out-of-sample window.
        """
        if not trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "expectancy_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "profitable": False,
            }

        summary = PerformanceMetrics.summarize(trades)

        expectancy = summary.get("expectancy_pct", 0.0)

        return {
            **summary,
            "profitable": expectancy > 0,
        }

    # ------------------------------------------------------
    # Cross-window aggregation
    # ------------------------------------------------------

    @staticmethod
    def aggregate(
        window_metrics: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Aggregate metrics across all walk-forward windows.
        """
        if not window_metrics:
            raise ValueError("No window metrics to aggregate")

        total_windows = len(window_metrics)

        profitable_windows = [
            m for m in window_metrics if m.get("profitable")
        ]

        expectancy_values = [
            m.get("expectancy_pct", 0.0) for m in window_metrics
        ]

        drawdowns = [
            m.get("max_drawdown_pct", 0.0) for m in window_metrics
        ]

        consistency_ratio = len(profitable_windows) / total_windows

        avg_expectancy = (
            sum(expectancy_values) / total_windows
            if total_windows > 0 else 0.0
        )

        worst_drawdown = max(drawdowns) if drawdowns else 0.0

        stability_score = WalkForwardMetrics._stability_score(
            expectancy_values
        )

        return {
            "total_windows": total_windows,
            "profitable_windows": len(profitable_windows),
            "consistency_ratio": round(consistency_ratio, 2),
            "avg_expectancy_pct": round(avg_expectancy, 2),
            "worst_drawdown_pct": round(worst_drawdown, 2),
            "stability_score": round(stability_score, 2),
        }

    # ------------------------------------------------------
    # Stability logic
    # ------------------------------------------------------

    @staticmethod
    def _stability_score(values: List[float]) -> float:
        """
        Penalize large variance in expectancy across windows.
        Higher is better.
        """
        if not values:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)

        # Add 1 to avoid division by zero
        stability = 1 / (1 + variance)

        return stability

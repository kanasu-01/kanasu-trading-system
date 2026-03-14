from dataclasses import dataclass
from typing import List, Dict, Any, Literal

from core.walk_forward.metrics import WalkForwardMetrics


# ==========================================================
# PER-WINDOW RESULT
# ==========================================================

@dataclass(frozen=True)
class WalkWindowResult:
    """
    Result of a single walk-forward window.
    """
    window_index: int
    best_params: Dict[str, Any]
    test_metrics: Dict[str, Any]
    trade_count: int


# ==========================================================
# WALK-FORWARD FINAL RESULT
# ==========================================================

@dataclass(frozen=True)
class WalkForwardResult:
    """
    Immutable result of full walk-forward analysis.
    """
    windows: List[WalkWindowResult]
    aggregated_metrics: Dict[str, Any]
    verdict: Literal["PASS", "FAIL"]

    # ------------------------------------------------------
    # Factory method
    # ------------------------------------------------------

    @classmethod
    def from_windows(
        cls,
        windows: List[WalkWindowResult],
        *,
        min_consistency: float = 0.60,
        max_drawdown_pct: float = 20.0,
        min_stability_score: float = 0.20,
    ) -> "WalkForwardResult":

        if not windows:
            raise ValueError("WalkForwardResult requires window results")

        metrics = WalkForwardMetrics.aggregate(
            [w.test_metrics for w in windows]
        )

        verdict = cls._evaluate_verdict(
            metrics=metrics,
            min_consistency=min_consistency,
            max_drawdown_pct=max_drawdown_pct,
            min_stability_score=min_stability_score,
        )

        return cls(
            windows=windows,
            aggregated_metrics=metrics,
            verdict=verdict,
        )

    # ------------------------------------------------------
    # Verdict logic
    # ------------------------------------------------------

    @staticmethod
    def _evaluate_verdict(
        metrics: Dict[str, Any],
        *,
        min_consistency: float,
        max_drawdown_pct: float,
        min_stability_score: float,
    ) -> Literal["PASS", "FAIL"]:

        if metrics["consistency_ratio"] < min_consistency:
            return "FAIL"

        if metrics["avg_expectancy_pct"] <= 0:
            return "FAIL"

        if metrics["worst_drawdown_pct"] > max_drawdown_pct:
            return "FAIL"

        if metrics["stability_score"] < min_stability_score:
            return "FAIL"

        return "PASS"

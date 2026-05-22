from dataclasses import dataclass
from typing import List, Dict, Any, Literal

from core.walk_forward.metrics import WalkForwardMetrics
from core.backtest.backtest_result import BacktestResult
from core.walk_forward.equity_stitcher import EquityStitcher
from core.walk_forward.optimization_result import OptimizationResult

# ==========================================================
# PER-WINDOW RESULT
# ==========================================================


@dataclass(frozen=True)
class WalkWindowResult:
    """
    Result of a single walk-forward window.
    """

    window_index: int

    optimization_stability_score: float

    # Canonical optimization lineage
    optimization_result: OptimizationResult

    # Selected parameter set from IS optimization
    best_params: Dict[str, Any]

    # Canonical OOS execution result
    backtest_result: BacktestResult

    # Legacy summary fields (temporary migration layer)
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

    # Legacy summary metrics
    aggregated_metrics: Dict[str, Any]

    # Canonical stitched OOS equity
    stitched_equity_curve: List

    # Metrics derived from stitched equity
    stitched_equity_metrics: Dict[str, Any]

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

        metrics = WalkForwardMetrics.aggregate([w.test_metrics for w in windows])

        stitched_equity_curve = EquityStitcher.stitch(windows)
        stitched_equity_metrics = WalkForwardMetrics.compute_stitched_equity_metrics(
            stitched_equity_curve
        )

        optimization_stability_scores = [
            w.optimization_stability_score for w in windows
        ]

        avg_optimization_stability = round(
            sum(optimization_stability_scores) / len(optimization_stability_scores),
            4,
        )

        verdict = cls._evaluate_verdict(
            metrics=metrics,
            stitched_metrics=stitched_equity_metrics,
            min_consistency=min_consistency,
            max_drawdown_pct=max_drawdown_pct,
            min_stability_score=min_stability_score,
        )

        return cls(
            windows=windows,
            aggregated_metrics={
                **metrics,
                "avg_optimization_stability": avg_optimization_stability,
            },
            verdict=verdict,
            stitched_equity_curve=stitched_equity_curve,
            stitched_equity_metrics=stitched_equity_metrics,
        )

    # ------------------------------------------------------
    # Verdict logic
    # ------------------------------------------------------

    @staticmethod
    def _evaluate_verdict(
        metrics: Dict[str, Any],
        stitched_metrics: Dict[str, Any],
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

        if stitched_metrics["stitched_max_drawdown_pct"] > max_drawdown_pct:
            return "FAIL"

        if metrics["stability_score"] < min_stability_score:
            return "FAIL"

        return "PASS"

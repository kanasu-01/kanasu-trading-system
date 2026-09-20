from dataclasses import dataclass
from math import inf, isfinite, nextafter
from numbers import Real
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

    # Authoritative OOS account metrics
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

    # Authoritative cross-window account metrics
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

        min_consistency = cls._validated_threshold(
            name="min_consistency",
            value=min_consistency,
            minimum=0.0,
            maximum=1.0,
        )
        max_drawdown_pct = cls._validated_threshold(
            name="max_drawdown_pct",
            value=max_drawdown_pct,
            minimum=0.0,
        )
        min_stability_score = cls._validated_threshold(
            name="min_stability_score",
            value=min_stability_score,
            minimum=0.0,
            maximum=1.0,
        )

        metrics = WalkForwardMetrics.aggregate([w.test_metrics for w in windows])

        stitched_equity_curve = EquityStitcher.stitch(windows)
        stitched_equity_metrics = WalkForwardMetrics.compute_stitched_equity_metrics(
            stitched_equity_curve
        )

        optimization_stability_scores = []

        for index, window in enumerate(windows):
            try:
                score = float(
                    window.optimization_stability_score
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"WFA window {index} optimization stability "
                    f"must be finite"
                ) from exc

            if not isfinite(score):
                raise ValueError(
                    f"WFA window {index} optimization stability "
                    f"must be finite"
                )

            optimization_stability_scores.append(score)

        avg_optimization_stability = round(
            sum(optimization_stability_scores)
            / len(optimization_stability_scores),
            4,
        )

        if not isfinite(avg_optimization_stability):
            raise ValueError(
                "average optimization stability must be finite"
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

    @staticmethod
    def _validated_threshold(
        *,
        name: str,
        value,
        minimum: float,
        maximum: float | None = None,
    ) -> float:
        if (
            isinstance(value, bool)
            or not isinstance(value, Real)
        ):
            raise ValueError(
                f"{name} must be a finite number"
            )

        numeric_value = float(value)

        if not isfinite(numeric_value):
            raise ValueError(
                f"{name} must be a finite number"
            )

        if numeric_value < minimum:
            raise ValueError(
                f"{name} must be >= {minimum}"
            )

        if (
            maximum is not None
            and numeric_value > maximum
        ):
            raise ValueError(
                f"{name} must be <= {maximum}"
            )

        return numeric_value

    @staticmethod
    def _boundary_with_ulp_tolerance(
        boundary: float,
        direction: float,
    ) -> float:
        """
        Move four representable floats from an inclusive
        threshold to absorb arithmetic reconstruction noise.
        """

        adjusted = boundary

        for _ in range(4):
            adjusted = nextafter(
                adjusted,
                direction,
            )

        return adjusted

    @staticmethod
    def _below_minimum(
        value: float,
        minimum: float,
    ) -> bool:
        tolerated_minimum = (
            WalkForwardResult._boundary_with_ulp_tolerance(
                minimum,
                -inf,
            )
        )

        return value < tolerated_minimum

    @staticmethod
    def _above_maximum(
        value: float,
        maximum: float,
    ) -> bool:
        tolerated_maximum = (
            WalkForwardResult._boundary_with_ulp_tolerance(
                maximum,
                inf,
            )
        )

        return value > tolerated_maximum

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

        min_consistency = WalkForwardResult._validated_threshold(
            name="min_consistency",
            value=min_consistency,
            minimum=0.0,
            maximum=1.0,
        )
        max_drawdown_pct = WalkForwardResult._validated_threshold(
            name="max_drawdown_pct",
            value=max_drawdown_pct,
            minimum=0.0,
        )
        min_stability_score = WalkForwardResult._validated_threshold(
            name="min_stability_score",
            value=min_stability_score,
            minimum=0.0,
            maximum=1.0,
        )

        if WalkForwardResult._below_minimum(
            metrics["consistency_ratio"],
            min_consistency,
        ):
            return "FAIL"

        if metrics["avg_account_return_pct"] <= 0:
            return "FAIL"

        if WalkForwardResult._above_maximum(
            metrics["worst_equity_drawdown_pct"],
            max_drawdown_pct,
        ):
            return "FAIL"

        if stitched_metrics["stitched_total_return_pct"] <= 0:
            return "FAIL"

        if WalkForwardResult._above_maximum(
            stitched_metrics["stitched_max_drawdown_pct"],
            max_drawdown_pct,
        ):
            return "FAIL"

        if WalkForwardResult._below_minimum(
            metrics["account_return_stability_score"],
            min_stability_score,
        ):
            return "FAIL"

        return "PASS"

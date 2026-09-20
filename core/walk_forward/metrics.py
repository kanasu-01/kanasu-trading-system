from fractions import Fraction
from math import inf, isfinite, nextafter
from typing import List, Dict, Any

from core.backtest.backtest_result import BacktestResult
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

    def compute(
        self,
        result: BacktestResult,
    ) -> Dict[str, Any]:
        """
        Compute authoritative metrics for one out-of-sample window.
        """
        summary = PerformanceMetrics.summarize_backtest(result)

        return {
            **summary,
            "profitable": summary["account_return_pct"] > 0,
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

        account_returns = []
        equity_drawdowns = []

        for index, metrics in enumerate(window_metrics):
            try:
                account_return = float(
                    metrics["account_return_pct"]
                )
                equity_drawdown = float(
                    metrics["max_equity_drawdown_pct"]
                )
            except KeyError as exc:
                raise ValueError(
                    f"WFA window {index} missing metric "
                    f"{exc.args[0]}"
                ) from exc
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"WFA window {index} account metrics "
                    f"must be finite numbers"
                ) from exc

            if not isfinite(account_return) or not isfinite(
                equity_drawdown
            ):
                raise ValueError(
                    f"WFA window {index} account metrics "
                    f"must be finite numbers"
                )

            if equity_drawdown < 0:
                raise ValueError(
                    f"WFA window {index} equity drawdown "
                    f"must be non-negative"
                )

            account_returns.append(account_return)
            equity_drawdowns.append(equity_drawdown)

        profitable_windows = sum(
            account_return > 0
            for account_return in account_returns
        )

        consistency_ratio = profitable_windows / total_windows
        avg_account_return = (
            sum(account_returns) / total_windows
        )
        worst_equity_drawdown = max(equity_drawdowns)

        primary_derived_values = (
            consistency_ratio,
            avg_account_return,
            worst_equity_drawdown,
        )

        if any(
            not isfinite(value)
            for value in primary_derived_values
        ):
            raise ValueError(
                "WFA aggregate derived metrics must be finite"
            )

        account_return_stability = WalkForwardMetrics._stability_score(
            account_returns
        )

        if not isfinite(account_return_stability):
            raise ValueError(
                "WFA aggregate derived metrics must be finite"
            )

        return {
            "total_windows": total_windows,
            "profitable_windows": profitable_windows,
            "consistency_ratio": consistency_ratio,
            "avg_account_return_pct": avg_account_return,
            "worst_equity_drawdown_pct": worst_equity_drawdown,
            "account_return_stability_score": (
                account_return_stability
            ),
        }

    @staticmethod
    def _exact_equity_value(value) -> Fraction:
        if isinstance(value, Fraction):
            return value

        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "stitched WFA equity must be finite"
            ) from exc

        if not isfinite(numeric_value):
            raise ValueError(
                "stitched WFA equity must be finite"
            )

        return Fraction.from_float(numeric_value)

    @staticmethod
    def _finite_fraction_metric(
        value: Fraction,
    ) -> float:
        try:
            numeric_value = float(value)
        except OverflowError as exc:
            raise ValueError(
                "stitched WFA derived metrics must be finite"
            ) from exc

        if not isfinite(numeric_value):
            raise ValueError(
                "stitched WFA derived metrics must be finite"
            )

        # If an exact non-zero rational is smaller than the
        # smallest representable float, preserve its sign
        # instead of silently converting it into zero.
        if numeric_value == 0.0 and value != 0:
            numeric_value = nextafter(
                0.0,
                inf if value > 0 else -inf,
            )

        return numeric_value

    @staticmethod
    def compute_stitched_equity_metrics(
        stitched_equity_curve,
    ) -> Dict[str, Any]:
        """
        Compute metrics from continuous stitched OOS equity.

        Fraction inputs retain exact compounded relationships,
        preventing reconstruction noise from changing zero-boundary
        return or drawdown verdicts.
        """

        if not stitched_equity_curve:
            return {
                "stitched_total_return_pct": 0.0,
                "stitched_max_drawdown_pct": 0.0,
            }

        equity_values = [
            WalkForwardMetrics._exact_equity_value(equity)
            for _, equity in stitched_equity_curve
        ]

        if equity_values[0] <= 0:
            raise ValueError(
                "stitched WFA starting equity must be strictly positive"
            )

        start_equity = equity_values[0]
        end_equity = equity_values[-1]
        hundred = Fraction(100, 1)

        total_return_exact = (
            (end_equity - start_equity)
            / start_equity
            * hundred
        )

        peak = equity_values[0]
        max_drawdown_exact = Fraction(0, 1)

        for equity in equity_values:
            if equity > peak:
                peak = equity

            drawdown_exact = (
                (peak - equity)
                / peak
                * hundred
            )

            if drawdown_exact > max_drawdown_exact:
                max_drawdown_exact = drawdown_exact

        return {
            "stitched_total_return_pct": (
                WalkForwardMetrics._finite_fraction_metric(
                    total_return_exact
                )
            ),
            "stitched_max_drawdown_pct": (
                WalkForwardMetrics._finite_fraction_metric(
                    max_drawdown_exact
                )
            ),
        }

    # ------------------------------------------------------
    # Stability logic
    # ------------------------------------------------------

    @staticmethod
    def _stability_score(values: List[float]) -> float:
        """
        Penalize large variance across observed values.
        Higher is better.
        """
        if not values:
            return 0.0

        normalized_values = []

        for value in values:
            try:
                numeric_value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    "stability values must be finite numbers"
                ) from exc

            if not isfinite(numeric_value):
                raise ValueError(
                    "stability values must be finite numbers"
                )

            normalized_values.append(numeric_value)

        try:
            mean = (
                sum(normalized_values)
                / len(normalized_values)
            )

            if not isfinite(mean):
                raise ValueError(
                    "stability calculation must remain finite"
                )

            variance = (
                sum(
                    (value - mean) ** 2
                    for value in normalized_values
                )
                / len(normalized_values)
            )

            if not isfinite(variance):
                raise ValueError(
                    "stability calculation must remain finite"
                )

            stability = 1 / (1 + variance)

        except OverflowError as exc:
            raise ValueError(
                "stability calculation must remain finite"
            ) from exc

        if not isfinite(stability):
            raise ValueError(
                "stability calculation must remain finite"
            )

        return stability

    @staticmethod
    def optimization_stability_score(
        evaluation_scores: List[float],
    ) -> float:
        """
        Measures optimization stability from
        parameter evaluation scores.
        """

        return round(
            WalkForwardMetrics._stability_score(evaluation_scores),
            4,
        )

from math import isfinite
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
        account_return_stability = WalkForwardMetrics._stability_score(
            account_returns
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
    def compute_stitched_equity_metrics(
        stitched_equity_curve,
    ) -> Dict[str, Any]:
        """
        Compute metrics from continuous stitched OOS equity.
        """

        if not stitched_equity_curve:
            return {
                "stitched_total_return_pct": 0.0,
                "stitched_max_drawdown_pct": 0.0,
            }

        try:
            equity_values = [
                float(equity)
                for _, equity in stitched_equity_curve
            ]
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "stitched WFA equity must be finite"
            ) from exc

        if any(not isfinite(equity) for equity in equity_values):
            raise ValueError("stitched WFA equity must be finite")

        if equity_values[0] <= 0:
            raise ValueError(
                "stitched WFA starting equity must be strictly positive"
            )

        start_equity = equity_values[0]
        end_equity = equity_values[-1]

        # -----------------------------------------
        # Total return
        # -----------------------------------------
        total_return_pct = (
            ((end_equity - start_equity) / start_equity) * 100
            if start_equity != 0
            else 0.0
        )

        # -----------------------------------------
        # Max drawdown
        # -----------------------------------------
        peak = equity_values[0]
        max_drawdown = 0.0

        for equity in equity_values:

            if equity > peak:
                peak = equity

            drawdown = ((peak - equity) / peak) * 100 if peak != 0 else 0.0

            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return {
            "stitched_total_return_pct": total_return_pct,
            "stitched_max_drawdown_pct": max_drawdown,
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

        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)

        # Add 1 to avoid division by zero
        stability = 1 / (1 + variance)

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

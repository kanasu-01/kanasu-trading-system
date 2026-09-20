from typing import Dict, List, Type, Any

from core.backtest.backtest_engine import BacktestEngine
from core.runtime.runtime_context import (
    RuntimeContext,
)
from core.runtime.dataset_context import (
    DatasetContext,
)
from core.backtest.performance_metrics import PerformanceMetrics
from core.strategies.base_strategy import BaseStrategy
from core.entities.candle import Candle

from core.walk_forward.optimization_result import (
    OptimizationResult,
    OptimizationEvaluation,
)

# ==========================================================
# GRID SEARCH OPTIMIZER
# ==========================================================


class GridSearchOptimizer:
    """
    Simple grid-search optimizer for walk-forward analysis.

    Strategy-agnostic.
    Deterministic.
    """

    def optimize(
        self,
        strategy_cls: Type,
        param_space: List[Dict[str, Any]],
        train_bars: List[Candle],
        dataset_context: DatasetContext,
        initial_capital: float,
        runtime_context: RuntimeContext,
        history_bars: List[Candle] | None = None,
    ) -> OptimizationResult:
        """
        Returns the best parameter set based on in-sample performance.
        """

        if not param_space:
            raise ValueError("param_space cannot be empty")

        best_params: Dict[str, Any] | None = None
        best_score: float = float("-inf")
        evaluations: List[OptimizationEvaluation] = []

        for params in param_space:
            # --------------------------------------------------
            # Instantiate fresh strategy & engine (MANDATORY)
            # --------------------------------------------------
            strategy = strategy_cls(params=params)
            engine = BacktestEngine(
                strategy=strategy,
                initial_capital=initial_capital,
                runtime_context=runtime_context,
                dataset_context=dataset_context,
            )

            backtest_result = engine.run(
                train_bars,
                history_bars=history_bars,
            )

            metrics = PerformanceMetrics.summarize_backtest(
                backtest_result
            )

            score = self._score(metrics)
            evaluations.append(
                OptimizationEvaluation(
                    params=params,
                    score=score,
                    metrics=metrics,
                )
            )

            if score > best_score:
                best_score = score
                best_params = params

        if best_params is None:
            raise RuntimeError("Optimizer failed to find valid parameters")

        return OptimizationResult(
            best_params=best_params,
            best_score=best_score,
            evaluations=evaluations,
        )

    # ------------------------------------------------------
    # Scoring logic (simple & transparent)
    # ------------------------------------------------------

    @staticmethod
    def _score(metrics: Dict[str, Any]) -> float:
        """
        Prefer higher account return with lower equity drawdown.
        """

        account_return = metrics["account_return_pct"]
        max_drawdown = metrics["max_equity_drawdown_pct"]

        return account_return - (0.5 * max_drawdown)

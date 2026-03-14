from typing import Type, List, Dict, Any

from core.entities.candle import Candle
from core.strategies.base_strategy import BaseStrategy
from core.backtest.backtest_engine import BacktestEngine

from core.walk_forward.window_generator import (
    WalkForwardWindowGenerator,
    WalkForwardWindow,
)
from core.walk_forward.optimizer import GridSearchOptimizer
from core.walk_forward.metrics import WalkForwardMetrics
from core.walk_forward.result import (
    WalkWindowResult,
    WalkForwardResult,
)


# ==========================================================
# WALK-FORWARD RUNNER
# ==========================================================

class WalkForwardRunner:
    """
    Orchestrates full walk-forward analysis.

    Coordinates:
    - window generation
    - parameter optimization
    - out-sample evaluation
    """

    def __init__(
        self,
        window_generator: WalkForwardWindowGenerator,
        optimizer: GridSearchOptimizer,
        metrics: WalkForwardMetrics,
    ):
        self.window_generator = window_generator
        self.optimizer = optimizer
        self.metrics = metrics

    # ------------------------------------------------------
    # Public API
    # ------------------------------------------------------

    def run(
        self,
        strategy_cls: Type[BaseStrategy],
        param_space: List[Dict[str, Any]],
        candles: List[Candle],
    ) -> WalkForwardResult:

        window_results: List[WalkWindowResult] = []

        for window in self.window_generator.generate(candles):
            window_result = self._run_single_window(
                strategy_cls=strategy_cls,
                param_space=param_space,
                window=window,
            )
            window_results.append(window_result)

        return WalkForwardResult.from_windows(window_results)

    # ------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------

    def _run_single_window(
        self,
        strategy_cls: Type[BaseStrategy],
        param_space: List[Dict[str, Any]],
        window: WalkForwardWindow,
    ) -> WalkWindowResult:

        # -----------------------------
        # 1. IN-SAMPLE OPTIMIZATION
        # -----------------------------
        best_params = self.optimizer.optimize(
            strategy_cls=strategy_cls,
            param_space=param_space,
            train_bars=window.train_bars,
        )

        # -----------------------------
        # 2. OUT-SAMPLE EVALUATION
        # -----------------------------
        strategy = strategy_cls(params=best_params)
        engine = BacktestEngine(strategy)

        trades = engine.run(window.test_bars)

        test_metrics = self.metrics.compute(trades)

        return WalkWindowResult(
            window_index=window.window_index,
            best_params=best_params,
            test_metrics=test_metrics,
            trade_count=len(trades),
        )

from datetime import datetime, timedelta
from types import SimpleNamespace

from core.entities.candle import Candle
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext

import core.walk_forward.runner as runner_module

from core.walk_forward.window_generator import (
    WalkForwardWindowGenerator,
)

from core.walk_forward.optimizer import (
    GridSearchOptimizer,
)
from core.walk_forward.optimization_result import (
    OptimizationEvaluation,
    OptimizationResult,
)

from core.walk_forward.metrics import (
    WalkForwardMetrics,
)

from core.walk_forward.runner import (
    WalkForwardRunner,
)

from core.strategies.sma_crossover_strategy import (
    SMACrossOverStrategy,
)


def build_dummy_candles(count: int):

    candles = []

    base_time = datetime(2020, 1, 1)

    price = 100

    for i in range(count):

        if i % 20 < 10:
            price += 2
        else:
            price -= 2

        candles.append(
            Candle(
                timestamp=(base_time + timedelta(minutes=i)),
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=1000,
            )
        )

    return candles


def test_walk_forward_runner_executes():

    candles = build_dummy_candles(1000)

    window_generator = WalkForwardWindowGenerator(
        in_sample_bars=300,
        out_sample_bars=100,
        step_bars=100,
        mode="rolling",
    )

    optimizer = GridSearchOptimizer()

    metrics = WalkForwardMetrics()

    runner = WalkForwardRunner(
        window_generator=window_generator,
        optimizer=optimizer,
        metrics=metrics,
    )

    param_space = [
        {
            "fast_period": 10,
            "slow_period": 30,
        },
        {
            "fast_period": 20,
            "slow_period": 50,
        },
    ]

    result = runner.run(
        strategy_cls=SMACrossOverStrategy,
        param_space=param_space,
        candles=candles,
        dataset_context=DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
        ),
        initial_capital=100_000.0,
        runtime_context=RuntimeContext(),
    )

    assert result is not None

    assert result.windows is not None

    assert len(result.windows) > 0


def test_walk_forward_runner_propagates_effective_settings(monkeypatch):
    dataset_context = DatasetContext(
        symbol="RELIANCE",
        timeframe="15m",
    )
    runtime_context = RuntimeContext(
        risk_per_trade_pct=2.5,
    )
    initial_capital = 250_000.0
    candles = build_dummy_candles(2)

    optimizer_calls = []
    out_of_sample_calls = []

    class SingleWindowGenerator:
        def generate(self, source_candles):
            yield runner_module.WalkForwardWindow(
                train_bars=source_candles[:1],
                test_bars=source_candles[1:],
                window_index=0,
            )

    class SpyOptimizer:
        def optimize(
            self,
            *,
            strategy_cls,
            param_space,
            train_bars,
            dataset_context,
            initial_capital,
            runtime_context,
        ):
            optimizer_calls.append(
                (
                    dataset_context,
                    initial_capital,
                    runtime_context,
                )
            )
            evaluation = OptimizationEvaluation(
                params=param_space[0],
                score=1.0,
                metrics={},
            )
            return OptimizationResult(
                best_params=param_space[0],
                best_score=1.0,
                evaluations=[evaluation],
            )

    class StubMetrics:
        def compute(self, trades):
            return {}

    class SpyBacktestEngine:
        def __init__(
            self,
            *,
            strategy,
            initial_capital,
            runtime_context,
            dataset_context,
        ):
            out_of_sample_calls.append(
                (
                    dataset_context,
                    initial_capital,
                    runtime_context,
                )
            )

        def run(self, source_candles):
            return SimpleNamespace(trades=[])

    monkeypatch.setattr(
        runner_module,
        "BacktestEngine",
        SpyBacktestEngine,
    )
    monkeypatch.setattr(
        runner_module.WalkForwardResult,
        "from_windows",
        classmethod(
            lambda cls, windows: SimpleNamespace(
                windows=windows
            )
        ),
    )

    runner = WalkForwardRunner(
        window_generator=SingleWindowGenerator(),
        optimizer=SpyOptimizer(),
        metrics=StubMetrics(),
    )
    runner.run(
        strategy_cls=SMACrossOverStrategy,
        param_space=[
            {
                "fast_period": 10,
                "slow_period": 30,
            }
        ],
        candles=candles,
        dataset_context=dataset_context,
        initial_capital=initial_capital,
        runtime_context=runtime_context,
    )

    expected = [
        (
            dataset_context,
            initial_capital,
            runtime_context,
        )
    ]
    assert optimizer_calls == expected
    assert out_of_sample_calls == expected

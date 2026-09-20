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
    out_of_sample_results = []
    metric_inputs = []

    class SingleWindowGenerator:
        def generate(
            self,
            source_candles,
            *,
            prehistory_bars=0,
        ):
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
            history_bars=None,
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
        def compute(self, result):
            metric_inputs.append(result)
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

        def run(
            self,
            source_candles,
            *,
            history_bars=None,
        ):
            result = SimpleNamespace(trades=[])
            out_of_sample_results.append(result)
            return result

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
    assert metric_inputs == out_of_sample_results


def test_runner_uses_common_candidate_warmup_before_scored_windows(
    monkeypatch,
):
    candles = build_dummy_candles(20)
    optimizer_calls = []
    oos_calls = []

    class WarmupStrategy:
        def __init__(self, params):
            self.params = params

        def warmup_bars(self):
            return self.params["warmup"]

    class RecordingOptimizer:
        def optimize(
            self,
            *,
            strategy_cls,
            param_space,
            train_bars,
            dataset_context,
            initial_capital,
            runtime_context,
            history_bars=None,
        ):
            optimizer_calls.append(
                {
                    "train_bars": list(train_bars),
                    "history_bars": list(
                        history_bars or []
                    ),
                }
            )
            return OptimizationResult(
                best_params=param_space[0],
                best_score=1.0,
                evaluations=[
                    OptimizationEvaluation(
                        params=param_space[0],
                        score=1.0,
                        metrics={},
                    )
                ],
            )

    class RecordingBacktestEngine:
        def __init__(self, **kwargs):
            pass

        def run(
            self,
            scored_bars,
            *,
            history_bars=None,
        ):
            oos_calls.append(
                {
                    "scored_bars": list(scored_bars),
                    "history_bars": list(
                        history_bars or []
                    ),
                }
            )
            return SimpleNamespace(
                trades=[],
                bar_records=[],
            )

    monkeypatch.setattr(
        runner_module,
        "BacktestEngine",
        RecordingBacktestEngine,
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

    class StubMetrics:
        def compute(self, result):
            return {}

    runner = WalkForwardRunner(
        window_generator=WalkForwardWindowGenerator(
            in_sample_bars=5,
            out_sample_bars=3,
            step_bars=3,
            mode="rolling",
        ),
        optimizer=RecordingOptimizer(),
        metrics=StubMetrics(),
    )

    runner.run(
        strategy_cls=WarmupStrategy,
        param_space=[
            {"warmup": 2},
            {"warmup": 4},
        ],
        candles=candles,
        dataset_context=DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
        ),
        initial_capital=100_000.0,
        runtime_context=RuntimeContext(),
    )

    first_is = optimizer_calls[0]
    first_oos = oos_calls[0]

    assert first_is["history_bars"] == candles[0:3]
    assert first_is["train_bars"] == candles[3:8]

    assert first_oos["history_bars"] == candles[5:8]
    assert first_oos["scored_bars"] == candles[8:11]


def test_runner_accepts_exact_minimum_strategy_prehistory():
    runner = WalkForwardRunner(
        window_generator=WalkForwardWindowGenerator(
            in_sample_bars=5,
            out_sample_bars=3,
            step_bars=3,
            mode="rolling",
        ),
        optimizer=GridSearchOptimizer(),
        metrics=WalkForwardMetrics(),
    )

    result = runner.run(
        strategy_cls=SMACrossOverStrategy,
        param_space=[
            {
                "fast_period": 10,
                "slow_period": 30,
            }
        ],
        candles=build_dummy_candles(37),
        dataset_context=DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
        ),
        initial_capital=100_000.0,
        runtime_context=RuntimeContext(),
    )

    assert len(result.windows) == 1


def test_runner_rejects_insufficient_strategy_prehistory():
    runner = WalkForwardRunner(
        window_generator=WalkForwardWindowGenerator(
            in_sample_bars=5,
            out_sample_bars=3,
            step_bars=3,
            mode="rolling",
        ),
        optimizer=GridSearchOptimizer(),
        metrics=WalkForwardMetrics(),
    )

    try:
        runner.run(
            strategy_cls=SMACrossOverStrategy,
            param_space=[
                {
                    "fast_period": 10,
                    "slow_period": 30,
                }
            ],
            candles=build_dummy_candles(36),
            dataset_context=DatasetContext(
                symbol="RELIANCE",
                timeframe="15m",
            ),
            initial_capital=100_000.0,
            runtime_context=RuntimeContext(),
        )
    except ValueError as exc:
        assert "prehistory" in str(exc)
    else:
        raise AssertionError(
            "insufficient WFA prehistory was accepted"
        )

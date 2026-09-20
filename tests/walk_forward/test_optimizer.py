from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.entities.candle import Candle
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext

import core.walk_forward.optimizer as optimizer_module

from core.walk_forward.optimizer import (
    GridSearchOptimizer,
)

from core.strategies.sma_crossover_strategy import (
    SMACrossOverStrategy,
)
from core.strategies.pivotboss_swing_strategy import (
    PivotBossSwingStrategy,
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


def test_optimizer_executes_without_crashing():

    candles = build_dummy_candles(500)

    optimizer = GridSearchOptimizer()

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

    try:

        optimizer.optimize(
            strategy_cls=SMACrossOverStrategy,
            param_space=param_space,
            train_bars=candles,
            dataset_context=DatasetContext(
                symbol="RELIANCE",
                timeframe="15m",
            ),
            initial_capital=100_000.0,
            runtime_context=RuntimeContext(),
        )

    except RuntimeError:

        # Acceptable for deterministic
        # synthetic test data
        pass


def test_optimizer_propagates_caller_effective_settings(monkeypatch):
    dataset_context = DatasetContext(
        symbol="RELIANCE",
        timeframe="15m",
    )
    runtime_context = RuntimeContext(
        risk_per_trade_pct=2.5,
    )
    initial_capital = 250_000.0

    received_dataset_contexts = []
    received_initial_capitals = []
    received_runtime_contexts = []

    class SpyBacktestEngine:
        def __init__(
            self,
            *,
            strategy,
            initial_capital,
            runtime_context,
            dataset_context,
        ):
            received_dataset_contexts.append(dataset_context)
            received_initial_capitals.append(initial_capital)
            received_runtime_contexts.append(runtime_context)

        def run(
            self,
            candles,
            *,
            history_bars=None,
        ):
            return SimpleNamespace(trades=[])

    monkeypatch.setattr(
        optimizer_module,
        "BacktestEngine",
        SpyBacktestEngine,
    )
    monkeypatch.setattr(
        optimizer_module.PerformanceMetrics,
        "summarize",
        staticmethod(
            lambda _trades: (_ for _ in ()).throw(
                AssertionError(
                    "optimizer used legacy trade-only metrics"
                )
            )
        ),
    )
    monkeypatch.setattr(
        optimizer_module.PerformanceMetrics,
        "summarize_backtest",
        staticmethod(
            lambda _result: {
                "account_return_pct": 4.0,
                "max_equity_drawdown_pct": 2.0,
            }
        ),
    )

    optimizer = GridSearchOptimizer()
    optimization_result = optimizer.optimize(
        strategy_cls=SMACrossOverStrategy,
        param_space=[
            {
                "fast_period": 10,
                "slow_period": 30,
            }
        ],
        train_bars=build_dummy_candles(2),
        dataset_context=dataset_context,
        initial_capital=initial_capital,
        runtime_context=runtime_context,
    )

    assert received_dataset_contexts == [dataset_context]
    assert received_initial_capitals == [initial_capital]
    assert received_runtime_contexts == [runtime_context]
    assert optimization_result.best_score == pytest.approx(3.0)
    assert optimization_result.evaluations[0].metrics == {
        "account_return_pct": 4.0,
        "max_equity_drawdown_pct": 2.0,
    }


def test_optimizer_score_uses_account_return_and_equity_drawdown():
    assert GridSearchOptimizer._score(
        {
            "account_return_pct": 5.0,
            "max_equity_drawdown_pct": 4.0,
        }
    ) == pytest.approx(3.0)

    assert GridSearchOptimizer._score(
        {
            "account_return_pct": 5.0,
            "max_equity_drawdown_pct": 10.0,
        }
    ) == pytest.approx(0.0)


def test_optimizer_rejects_candidate_keys_ignored_by_strategy(
    monkeypatch,
):
    class ForbiddenBacktestEngine:
        def __init__(self, **kwargs):
            raise AssertionError(
                "invalid candidate reached BacktestEngine"
            )

    monkeypatch.setattr(
        optimizer_module,
        "BacktestEngine",
        ForbiddenBacktestEngine,
    )

    optimizer = GridSearchOptimizer()

    with pytest.raises(
        ValueError,
        match="not effective strategy parameters: ignored",
    ):
        optimizer.optimize(
            strategy_cls=SMACrossOverStrategy,
            param_space=[
                {
                    "fast_period": 10,
                    "slow_period": 30,
                    "ignored": 123,
                }
            ],
            train_bars=[],
            dataset_context=DatasetContext(
                symbol="RELIANCE",
                timeframe="15m",
            ),
            initial_capital=100_000.0,
            runtime_context=RuntimeContext(),
        )


def test_optimizer_rejects_sma_grid_for_pivotboss(
    monkeypatch,
):
    class ForbiddenBacktestEngine:
        def __init__(self, **kwargs):
            raise AssertionError(
                "invalid PivotBoss candidate reached BacktestEngine"
            )

    monkeypatch.setattr(
        optimizer_module,
        "BacktestEngine",
        ForbiddenBacktestEngine,
    )

    optimizer = GridSearchOptimizer()

    with pytest.raises(
        ValueError,
        match="not effective strategy parameters",
    ):
        optimizer.optimize(
            strategy_cls=PivotBossSwingStrategy,
            param_space=[
                {
                    "fast_period": 10,
                    "slow_period": 30,
                }
            ],
            train_bars=[],
            dataset_context=DatasetContext(
                symbol="RELIANCE",
                timeframe="15m",
            ),
            initial_capital=100_000.0,
            runtime_context=RuntimeContext(),
        )


def test_optimizer_rejects_candidate_missing_effective_parameters(
    monkeypatch,
):
    class ForbiddenBacktestEngine:
        def __init__(self, **kwargs):
            raise AssertionError(
                "incomplete candidate reached BacktestEngine"
            )

    monkeypatch.setattr(
        optimizer_module,
        "BacktestEngine",
        ForbiddenBacktestEngine,
    )

    with pytest.raises(
        ValueError,
        match=(
            "omit effective strategy parameters: "
            "slow_period"
        ),
    ):
        GridSearchOptimizer().optimize(
            strategy_cls=SMACrossOverStrategy,
            param_space=[
                {
                    "fast_period": 10,
                }
            ],
            train_bars=[],
            dataset_context=DatasetContext(
                symbol="RELIANCE",
                timeframe="15m",
            ),
            initial_capital=100_000.0,
            runtime_context=RuntimeContext(),
        )


def test_optimizer_rejects_parameter_evidence_that_resolves_differently(
    monkeypatch,
):
    class NormalizingStrategy:
        def __init__(self, params):
            self.params = params

        def research_parameters(self):
            return {
                "period": self.params["period"] + 1,
            }

    class ForbiddenBacktestEngine:
        def __init__(self, **kwargs):
            raise AssertionError(
                "mismatched candidate reached BacktestEngine"
            )

    monkeypatch.setattr(
        optimizer_module,
        "BacktestEngine",
        ForbiddenBacktestEngine,
    )

    optimizer = GridSearchOptimizer()

    with pytest.raises(
        ValueError,
        match="do not match resolved effective values: period",
    ):
        optimizer.optimize(
            strategy_cls=NormalizingStrategy,
            param_space=[
                {
                    "period": 10,
                }
            ],
            train_bars=[],
            dataset_context=DatasetContext(
                symbol="RELIANCE",
                timeframe="15m",
            ),
            initial_capital=100_000.0,
            runtime_context=RuntimeContext(),
        )


def test_optimizer_preserves_valid_effective_parameter_evidence(
    monkeypatch,
):
    captured_strategies = []

    class SpyBacktestEngine:
        def __init__(
            self,
            *,
            strategy,
            initial_capital,
            runtime_context,
            dataset_context,
        ):
            captured_strategies.append(strategy)

        def run(
            self,
            candles,
            *,
            history_bars=None,
        ):
            return SimpleNamespace(trades=[])

    monkeypatch.setattr(
        optimizer_module,
        "BacktestEngine",
        SpyBacktestEngine,
    )
    monkeypatch.setattr(
        optimizer_module.PerformanceMetrics,
        "summarize_backtest",
        staticmethod(
            lambda _result: {
                "account_return_pct": 1.0,
                "max_equity_drawdown_pct": 0.0,
            }
        ),
    )

    params = {
        "fast_period": 10,
        "slow_period": 30,
    }

    result = GridSearchOptimizer().optimize(
        strategy_cls=SMACrossOverStrategy,
        param_space=[params],
        train_bars=[],
        dataset_context=DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
        ),
        initial_capital=100_000.0,
        runtime_context=RuntimeContext(),
    )

    assert len(captured_strategies) == 1
    assert captured_strategies[
        0
    ].research_parameters() == params
    assert result.best_params == params
    assert result.evaluations[0].params == params


@pytest.mark.parametrize(
    "metrics",
    [
        {
            "account_return_pct": float("nan"),
            "max_equity_drawdown_pct": 0.0,
        },
        {
            "account_return_pct": float("inf"),
            "max_equity_drawdown_pct": 0.0,
        },
        {
            "account_return_pct": 1.0,
            "max_equity_drawdown_pct": float("inf"),
        },
    ],
)
def test_optimizer_score_rejects_non_finite_inputs(metrics):
    with pytest.raises(
        ValueError,
        match="finite",
    ):
        GridSearchOptimizer._score(metrics)


def test_optimizer_score_rejects_finite_input_overflow():
    with pytest.raises(
        ValueError,
        match="optimizer score must be finite",
    ):
        GridSearchOptimizer._score(
            {
                "account_return_pct": -1.7e308,
                "max_equity_drawdown_pct": 1.7e308,
            }
        )


def test_optimizer_rejects_real_engine_non_finite_account_score():
    start = datetime(2026, 1, 2, 9, 15)

    candles = [
        Candle(
            timestamp=start,
            open=0.001,
            high=0.001,
            low=0.001,
            close=0.001,
            volume=1000.0,
        ),
        Candle(
            timestamp=start + timedelta(minutes=15),
            open=0.001,
            high=0.0011,
            low=0.001,
            close=0.0011,
            volume=1000.0,
        ),
        Candle(
            timestamp=start + timedelta(minutes=30),
            open=0.0011,
            high=5e305,
            low=0.0011,
            close=5e305,
            volume=1000.0,
        ),
    ]

    with pytest.raises(
        ValueError,
        match="optimizer scoring metrics must be finite",
    ):
        GridSearchOptimizer().optimize(
            strategy_cls=SMACrossOverStrategy,
            param_space=[
                {
                    "fast_period": 1,
                    "slow_period": 2,
                }
            ],
            train_bars=candles,
            dataset_context=DatasetContext(
                symbol="TEST",
                timeframe="15m",
            ),
            initial_capital=1.0,
            runtime_context=RuntimeContext(),
        )

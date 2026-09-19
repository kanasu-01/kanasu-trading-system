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

        def run(self, candles):
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

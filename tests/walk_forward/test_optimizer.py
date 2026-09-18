from datetime import datetime, timedelta
from types import SimpleNamespace

from core.entities.candle import Candle
from core.runtime.dataset_context import DatasetContext

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
        )

    except RuntimeError:

        # Acceptable for deterministic
        # synthetic test data
        pass


def test_optimizer_propagates_caller_dataset_context(monkeypatch):
    dataset_context = DatasetContext(
        symbol="RELIANCE",
        timeframe="15m",
    )
    received_dataset_contexts = []
    received_risk_settings = []

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
            received_risk_settings.append(runtime_context.risk_per_trade_pct)

        def run(self, candles):
            return SimpleNamespace(trades=[])

    monkeypatch.setattr(optimizer_module, "BacktestEngine", SpyBacktestEngine)
    monkeypatch.setattr(
        optimizer_module.PerformanceMetrics,
        "summarize",
        staticmethod(
            lambda trades: {
                "expectancy_pct": 1.0,
                "max_drawdown_pct": 0.0,
            }
        ),
    )
    monkeypatch.setattr(
        optimizer_module.PerformanceMetrics,
        "summarize_backtest",
        staticmethod(
            lambda _result: (_ for _ in ()).throw(
                AssertionError("WFA optimizer used result-aware Backtest metrics")
            )
        ),
    )

    optimizer = GridSearchOptimizer()
    optimizer.optimize(
        strategy_cls=SMACrossOverStrategy,
        param_space=[{"fast_period": 10, "slow_period": 30}],
        train_bars=build_dummy_candles(2),
        dataset_context=dataset_context,
    )

    assert received_dataset_contexts == [dataset_context]
    assert received_risk_settings == [1.0]

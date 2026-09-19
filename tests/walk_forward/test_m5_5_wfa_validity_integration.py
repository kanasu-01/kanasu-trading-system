from datetime import datetime, timedelta

import pytest

import core.walk_forward.runner as runner_module
from core.backtest.backtest_result import BacktestResult
from core.backtest.bar_record import BarRecord
from core.entities.candle import Candle
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.walk_forward.metrics import WalkForwardMetrics
from core.walk_forward.optimization_result import (
    OptimizationEvaluation,
    OptimizationResult,
)
from core.walk_forward.runner import WalkForwardRunner
from core.walk_forward.window_generator import WalkForwardWindow


START = datetime(2026, 1, 2, 9, 15)


def candle(timestamp: datetime) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1_000.0,
    )


def bar(timestamp: datetime, equity: float) -> BarRecord:
    return BarRecord(
        timestamp=timestamp,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1_000.0,
        strategy="M5.5",
        state=None,
        signal=None,
        execution_event=None,
        execution_price=None,
        execution_quantity=None,
        decision_snapshot={},
        equity=equity,
        cash=equity,
        position_size=0,
        drawdown=0.0,
    )


def backtest_result(
    start: datetime,
    starting_equity: float,
    ending_equity: float,
    session_id: str,
) -> BacktestResult:
    return BacktestResult(
        trades=[],
        bar_records=[
            bar(start, starting_equity),
            bar(
                start + timedelta(minutes=15),
                ending_equity,
            ),
        ],
        session_id=session_id,
    )


class DummyStrategy:
    def __init__(self, params):
        self.params = params


class StaticWindowGenerator:
    def __init__(self, count: int):
        self.count = count

    def generate(self, source_candles):
        for index in range(self.count):
            base = START + timedelta(hours=index)
            yield WalkForwardWindow(
                train_bars=[candle(base)],
                test_bars=[
                    candle(base + timedelta(minutes=15))
                ],
                window_index=index,
            )


class RecordingOptimizer:
    def __init__(self):
        self.calls = []
        self.results = []

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
        index = len(self.calls)
        best_params = param_space[index % len(param_space)]

        self.calls.append(
            {
                "strategy_cls": strategy_cls,
                "param_space": param_space,
                "train_bars": train_bars,
                "dataset_context": dataset_context,
                "initial_capital": initial_capital,
                "runtime_context": runtime_context,
            }
        )

        evaluations = [
            OptimizationEvaluation(
                params=params,
                score=1.0,
                metrics={
                    "account_return_pct": 1.0,
                    "max_equity_drawdown_pct": 0.0,
                },
            )
            for params in param_space
        ]

        result = OptimizationResult(
            best_params=best_params,
            best_score=1.0,
            evaluations=evaluations,
        )
        self.results.append(result)
        return result


def build_runner(monkeypatch, results):
    queue = list(results)
    engine_calls = []

    class RecordingBacktestEngine:
        def __init__(
            self,
            *,
            strategy,
            initial_capital,
            runtime_context,
            dataset_context,
        ):
            self.strategy = strategy
            engine_calls.append(
                {
                    "strategy": strategy,
                    "initial_capital": initial_capital,
                    "runtime_context": runtime_context,
                    "dataset_context": dataset_context,
                }
            )

        def run(self, source_candles):
            if not queue:
                raise AssertionError(
                    "unexpected extra OOS backtest"
                )
            return queue.pop(0)

    monkeypatch.setattr(
        runner_module,
        "BacktestEngine",
        RecordingBacktestEngine,
    )

    optimizer = RecordingOptimizer()
    runner = WalkForwardRunner(
        window_generator=StaticWindowGenerator(
            len(results)
        ),
        optimizer=optimizer,
        metrics=WalkForwardMetrics(),
    )

    return runner, optimizer, engine_calls, queue


def test_m5_5_end_to_end_wfa_validity_chain(monkeypatch):
    initial_capital = 250_000.0
    dataset_context = DatasetContext(
        symbol="RELIANCE",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )
    runtime_context = RuntimeContext(
        risk_per_trade_pct=2.5,
    )
    param_space = [
        {"fast_period": 10, "slow_period": 30},
        {"fast_period": 20, "slow_period": 50},
        {"fast_period": 30, "slow_period": 100},
    ]

    oos_results = [
        backtest_result(
            START,
            initial_capital,
            255_000.0,
            "m5.5-window-0",
        ),
        backtest_result(
            START + timedelta(minutes=30),
            initial_capital,
            252_500.0,
            "m5.5-window-1",
        ),
        backtest_result(
            START + timedelta(minutes=60),
            initial_capital,
            251_250.0,
            "m5.5-window-2",
        ),
    ]

    runner, optimizer, engine_calls, queue = build_runner(
        monkeypatch,
        oos_results,
    )

    result = runner.run(
        strategy_cls=DummyStrategy,
        param_space=param_space,
        candles=[],
        dataset_context=dataset_context,
        initial_capital=initial_capital,
        runtime_context=runtime_context,
    )

    assert queue == []
    assert len(result.windows) == 3
    assert len(optimizer.calls) == 3
    assert len(engine_calls) == 3

    for index, call in enumerate(optimizer.calls):
        assert call["strategy_cls"] is DummyStrategy
        assert call["param_space"] is param_space
        assert call["dataset_context"] is dataset_context
        assert call["initial_capital"] == initial_capital
        assert call["runtime_context"] is runtime_context

        engine_call = engine_calls[index]

        assert engine_call["dataset_context"] is dataset_context
        assert engine_call["runtime_context"] is runtime_context
        assert engine_call["initial_capital"] == initial_capital
        assert engine_call["strategy"].params == param_space[index]

        window = result.windows[index]

        assert window.optimization_result is optimizer.results[index]
        assert window.best_params == param_space[index]
        assert window.backtest_result is oos_results[index]
        assert window.trade_count == 0
        assert window.test_metrics["completed_trade_count"] == 0
        assert "expectancy_pct" not in window.test_metrics
        assert "max_drawdown_pct" not in window.test_metrics
        assert window.optimization_stability_score == 1.0

    assert [
        window.test_metrics["account_return_pct"]
        for window in result.windows
    ] == pytest.approx([2.0, 1.0, 0.5])

    assert result.aggregated_metrics == {
        "total_windows": 3,
        "profitable_windows": 3,
        "consistency_ratio": 1.0,
        "avg_account_return_pct": 1.17,
        "worst_equity_drawdown_pct": 0.0,
        "account_return_stability_score": 0.72,
        "avg_optimization_stability": 1.0,
    }

    assert [
        equity
        for _, equity in result.stitched_equity_curve
    ] == pytest.approx(
        [
            250_000.0,
            255_000.0,
            255_000.0,
            257_550.0,
            257_550.0,
            258_837.75,
        ]
    )

    assert result.stitched_equity_metrics == {
        "stitched_total_return_pct": 3.54,
        "stitched_max_drawdown_pct": 0.0,
    }

    assert result.verdict == "PASS"


def test_m5_5_end_to_end_rejects_overlapping_oos_evidence(
    monkeypatch,
):
    initial_capital = 250_000.0

    oos_results = [
        backtest_result(
            START,
            initial_capital,
            255_000.0,
            "m5.5-overlap-0",
        ),
        backtest_result(
            START + timedelta(minutes=15),
            initial_capital,
            252_500.0,
            "m5.5-overlap-1",
        ),
    ]

    runner, _, _, _ = build_runner(
        monkeypatch,
        oos_results,
    )

    with pytest.raises(
        ValueError,
        match="strictly increasing and non-overlapping",
    ):
        runner.run(
            strategy_cls=DummyStrategy,
            param_space=[
                {"fast_period": 10, "slow_period": 30},
                {"fast_period": 20, "slow_period": 50},
            ],
            candles=[],
            dataset_context=DatasetContext(
                symbol="RELIANCE",
                timeframe="15m",
            ),
            initial_capital=initial_capital,
            runtime_context=RuntimeContext(),
        )
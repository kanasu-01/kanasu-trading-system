from datetime import datetime, timedelta, timezone

import pytest

from core.backtest.backtest_engine import BacktestEngine
from core.backtest.performance_metrics import PerformanceMetrics
from core.config.execution_config import ExecutionConfig
from core.entities.candle import Candle
from core.execution.execution_feedback import (
    ExecutionFeedbackType,
    ExecutionRejectionReason,
)
from core.market_data.historical_coverage import TimeRange
from core.research.reproducibility import (
    backtest_configuration_fingerprint_v2,
    build_backtest_run_manifest,
    dataset_fingerprint,
    stable_backtest_result_fingerprint,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import SignalType


INDIA = timezone(
    timedelta(hours=5, minutes=30),
    name="Asia/Kolkata",
)
START = datetime(2026, 1, 5, 9, 15, tzinfo=INDIA)
CONTEXT = DatasetContext(
    "TEST",
    "15m",
    "Asia/Kolkata",
)
REQUEST = TimeRange(
    START,
    START + timedelta(hours=1),
)


def candle(
    index: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    return Candle(
        timestamp=START + timedelta(minutes=15 * index),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1_000.0 + index,
    )


def reference_candles() -> list[Candle]:
    return [
        candle(
            0,
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
        ),
        candle(
            1,
            open_price=100.0,
            high=106.0,
            low=95.0,
            close=105.0,
        ),
        candle(
            2,
            open_price=105.0,
            high=111.0,
            low=104.0,
            close=110.0,
        ),
        candle(
            3,
            open_price=110.0,
            high=112.0,
            low=109.0,
            close=111.0,
        ),
    ]


class IntegrationStrategy(BaseStrategy):
    def __init__(
        self,
        signals: dict[int, SignalType],
        *,
        rejection_midpoint: float | None = None,
        scenario: str,
    ):
        super().__init__(
            name="M4.7Integration",
            params={"scenario": scenario},
        )
        self.signals = signals
        self.initial_midpoint = rejection_midpoint
        self.rejection_midpoint = rejection_midpoint
        self.feedback = []

    def on_new_candle(self, series):
        return self.signals.get(len(series))

    def on_execution_feedback(self, feedback) -> None:
        self.feedback.append(feedback)

    def reset(self) -> None:
        self.rejection_midpoint = self.initial_midpoint
        self.feedback = []


def run_reference(
    execution_config: ExecutionConfig,
):
    candles = reference_candles()
    strategy = IntegrationStrategy(
        {
            1: SignalType.BUY,
            3: SignalType.SELL,
        },
        rejection_midpoint=90.2,
        scenario="reference",
    )
    runtime = RuntimeContext(
        execution_config=execution_config,
        risk_per_trade_pct=1.0,
    )

    dataset_id = dataset_fingerprint(
        CONTEXT,
        REQUEST,
        candles,
    )
    manifest = build_backtest_run_manifest(
        CONTEXT,
        REQUEST,
        dataset_id,
        strategy,
        initial_capital=100_000.0,
        runtime_context=runtime,
    )
    config_id = backtest_configuration_fingerprint_v2(
        manifest
    )

    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=100_000.0,
        runtime_context=runtime,
        dataset_context=CONTEXT,
    )
    result = engine.run(candles)

    return {
        "strategy": strategy,
        "engine": engine,
        "result": result,
        "summary": PerformanceMetrics.summarize_backtest(
            result
        ),
        "dataset_id": dataset_id,
        "config_id": config_id,
        "result_id": stable_backtest_result_fingerprint(
            result
        ),
    }


def test_complete_reference_connects_execution_metrics_and_identity():
    run = run_reference(
        ExecutionConfig(
            slippage_pct=0.0,
            slippage_enabled=False,
            brokerage_enabled=False,
        )
    )

    result = run["result"]
    trade = result.trades[0]
    summary = run["summary"]

    assert [record.signal for record in result.bar_records] == [
        "BUY",
        None,
        "SELL",
        None,
    ]
    assert [
        record.execution_event
        for record in result.bar_records
    ] == [
        None,
        "BUY",
        None,
        "SELL",
    ]

    assert trade.entry_price == 100.0
    assert trade.exit_price == 110.0
    assert trade.stop_price == 90.0
    assert trade.quantity == 100
    assert trade.pnl == 1_000.0

    assert [
        record.cash for record in result.bar_records
    ] == pytest.approx(
        [
            100_000.0,
            90_000.0,
            90_000.0,
            101_000.0,
        ]
    )
    assert [
        record.equity for record in result.bar_records
    ] == pytest.approx(
        [
            100_000.0,
            100_500.0,
            101_000.0,
            101_000.0,
        ]
    )

    assert summary["account_pnl"] == 1_000.0
    assert summary["account_return_pct"] == pytest.approx(
        1.0
    )
    assert summary["max_equity_drawdown_pct"] == 0.0

    assert run["dataset_id"].startswith("sha256:")
    assert run["config_id"].startswith("sha256:")
    assert run["result_id"].startswith("sha256:")


def test_independent_runs_preserve_stable_research_identity():
    config = ExecutionConfig(
        slippage_pct=0.0,
        slippage_enabled=False,
        brokerage_enabled=False,
    )

    first = run_reference(config)
    second = run_reference(config)

    assert first["result"] is not second["result"]
    assert first["dataset_id"] == second["dataset_id"]
    assert first["config_id"] == second["config_id"]
    assert first["result_id"] == second["result_id"]


def test_friction_changes_config_and_result_but_not_dataset_identity():
    zero = run_reference(
        ExecutionConfig(
            slippage_pct=0.0,
            slippage_enabled=False,
            brokerage_enabled=False,
        )
    )
    friction = run_reference(
        ExecutionConfig(
            slippage_pct=0.001,
            slippage_enabled=True,
            brokerage_enabled=True,
        )
    )

    assert zero["dataset_id"] == friction["dataset_id"]
    assert zero["config_id"] != friction["config_id"]
    assert zero["result_id"] != friction["result_id"]

    assert zero["result"].trades[0].quantity == 100
    assert friction["result"].trades[0].quantity == 99
    assert (
        friction["summary"]["account_return_pct"]
        < zero["summary"]["account_return_pct"]
    )


def test_exact_daily_loss_boundary_blocks_same_period_reentry():
    candles = [
        candle(
            0,
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
        ),
        candle(
            1,
            open_price=100.0,
            high=101.0,
            low=91.0,
            close=100.0,
        ),
        candle(
            2,
            open_price=70.0,
            high=71.0,
            low=69.0,
            close=70.0,
        ),
        candle(
            3,
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
        ),
    ]
    strategy = IntegrationStrategy(
        {
            1: SignalType.BUY,
            3: SignalType.BUY,
        },
        rejection_midpoint=90.2,
        scenario="daily-loss-boundary",
    )
    runtime = RuntimeContext(
        execution_config=ExecutionConfig(
            slippage_pct=0.0,
            slippage_enabled=False,
            brokerage_enabled=False,
        ),
        risk_per_trade_pct=1.0,
    )

    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=100_000.0,
        runtime_context=runtime,
        dataset_context=CONTEXT,
    )
    result = engine.run(candles)
    summary = PerformanceMetrics.summarize_backtest(
        result
    )

    assert [
        event.event_type for event in strategy.feedback
    ] == [
        ExecutionFeedbackType.ENTRY_ACCEPTED,
        ExecutionFeedbackType.PROTECTIVE_EXIT,
        ExecutionFeedbackType.ENTRY_REJECTED,
    ]
    assert strategy.feedback[-1].rejection_reason is (
        ExecutionRejectionReason.DRAWDOWN_LIMIT
    )

    assert len(result.trades) == 1
    assert result.trades[0].entry_price == 100.0
    assert result.trades[0].exit_price == 70.0
    assert result.trades[0].exit_reason == "STOP_LOSS"
    assert result.trades[0].pnl == -3_000.0

    assert (
        engine.execution_engine.get_runtime_position(
            CONTEXT.symbol
        )
        is None
    )
    assert result.bar_records[-1].cash == 97_000.0
    assert result.bar_records[-1].equity == 97_000.0
    assert summary["account_return_pct"] == pytest.approx(
        -3.0
    )
    assert summary["max_equity_drawdown_pct"] == pytest.approx(
        3.0
    )


def test_invalid_entry_rejection_stays_flat_through_result_boundary():
    candles = [
        candle(
            0,
            open_price=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
        ),
        candle(
            1,
            open_price=100.0,
            high=102.0,
            low=99.0,
            close=101.0,
        ),
    ]
    request = TimeRange(
        candles[0].timestamp,
        candles[-1].timestamp + timedelta(minutes=15),
    )
    strategy = IntegrationStrategy(
        {1: SignalType.BUY},
        rejection_midpoint=101.0,
        scenario="invalid-entry",
    )
    runtime = RuntimeContext(
        execution_config=ExecutionConfig(
            slippage_pct=0.0,
            slippage_enabled=False,
            brokerage_enabled=False,
        ),
        risk_per_trade_pct=1.0,
    )

    dataset_id = dataset_fingerprint(
        CONTEXT,
        request,
        candles,
    )
    manifest = build_backtest_run_manifest(
        CONTEXT,
        request,
        dataset_id,
        strategy,
        initial_capital=100_000.0,
        runtime_context=runtime,
    )

    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=100_000.0,
        runtime_context=runtime,
        dataset_context=CONTEXT,
    )
    result = engine.run(candles)
    summary = PerformanceMetrics.summarize_backtest(
        result
    )

    assert len(strategy.feedback) == 1
    assert strategy.feedback[0].event_type is (
        ExecutionFeedbackType.ENTRY_REJECTED
    )
    assert strategy.feedback[0].rejection_reason is (
        ExecutionRejectionReason.INVALID_ENTRY
    )

    assert result.trades == []
    assert len(result.bar_records) == 2
    assert all(
        record.position_size == 0
        for record in result.bar_records
    )
    assert all(
        record.cash == 100_000.0
        for record in result.bar_records
    )
    assert all(
        record.equity == 100_000.0
        for record in result.bar_records
    )

    assert summary["account_pnl"] == 0.0
    assert summary["account_return_pct"] == 0.0
    assert (
        backtest_configuration_fingerprint_v2(
            manifest
        ).startswith("sha256:")
    )
    assert stable_backtest_result_fingerprint(
        result
    ).startswith("sha256:")

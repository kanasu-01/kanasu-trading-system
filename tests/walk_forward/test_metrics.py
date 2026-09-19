from datetime import datetime, timedelta

import pytest

from core.backtest.backtest_result import BacktestResult
from core.backtest.bar_record import BarRecord
from core.entities.trade import Trade
from core.walk_forward.metrics import WalkForwardMetrics


START = datetime(2026, 1, 2, 9, 15)


def trade() -> Trade:
    return Trade(
        symbol="TEST",
        entry_time=START,
        entry_price=100.0,
        exit_time=START + timedelta(minutes=15),
        exit_price=110.0,
        stop_price=98.0,
        quantity=10,
        direction="LONG",
        exit_reason="STRATEGY_EXIT",
        pnl=100.0,
        gross_pnl=100.0,
        transaction_cost=0.0,
        pnl_pct=10.0,
    )


def bar(index: int, equity: float) -> BarRecord:
    return BarRecord(
        timestamp=START + timedelta(minutes=15 * index),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1_000.0,
        strategy="M5.2",
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


def result(
    equities: list[float],
    *,
    trades: list[Trade] | None = None,
) -> BacktestResult:
    return BacktestResult(
        trades=trades or [],
        bar_records=[
            bar(index, equity)
            for index, equity in enumerate(equities)
        ],
        session_id="m5.2",
    )


def test_wfa_window_metrics_use_authoritative_account_equity() -> None:
    metrics = WalkForwardMetrics().compute(
        result(
            [100_000.0, 105_000.0, 102_000.0],
            trades=[trade()],
        )
    )

    assert metrics["completed_trade_count"] == 1
    assert metrics["mean_instrument_return_pct"] == pytest.approx(
        10.0
    )
    assert metrics["account_return_pct"] == pytest.approx(2.0)
    assert metrics["max_equity_drawdown_pct"] == pytest.approx(
        3_000.0 / 105_000.0 * 100
    )
    assert metrics["profitable"] is True

    # Temporary compatibility for pre-M5.4 aggregation.
    assert metrics["expectancy_pct"] == 10.0
    assert metrics["max_drawdown_pct"] == 0.0


def test_wfa_window_metrics_include_open_terminal_account_outcome() -> None:
    metrics = WalkForwardMetrics().compute(
        result([100_000.0, 101_000.0])
    )

    assert metrics["completed_trade_count"] == 0
    assert metrics["account_pnl"] == pytest.approx(1_000.0)
    assert metrics["account_return_pct"] == pytest.approx(1.0)
    assert metrics["max_equity_drawdown_pct"] == 0.0
    assert metrics["profitable"] is True


def test_wfa_profitability_uses_account_return_not_instrument_return() -> None:
    metrics = WalkForwardMetrics().compute(
        result(
            [100_000.0, 99_000.0],
            trades=[trade()],
        )
    )

    assert metrics["mean_instrument_return_pct"] == 10.0
    assert metrics["account_return_pct"] == pytest.approx(-1.0)
    assert metrics["profitable"] is False

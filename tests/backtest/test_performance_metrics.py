from datetime import datetime, timedelta
from math import inf, nan

import pytest

from core.backtest.backtest_result import BacktestResult
from core.backtest.bar_record import BarRecord
from core.backtest.performance_metrics import PerformanceMetrics
from core.entities.position import Position
from core.entities.trade import Trade
from core.execution.trade_builder import TradeBuilder


START = datetime(2026, 1, 2, 9, 15)

EXPECTED_KEYS = {
    "completed_trade_count",
    "net_profitable_trade_count",
    "net_losing_trade_count",
    "net_breakeven_trade_count",
    "net_profitable_trade_rate_pct",
    "mean_positive_instrument_return_pct",
    "mean_negative_instrument_return_pct",
    "mean_instrument_return_pct",
    "gross_realized_pnl",
    "net_realized_pnl",
    "mean_net_pnl_per_completed_trade",
    "completed_trade_transaction_cost_total",
    "account_pnl",
    "account_return_pct",
    "max_equity_drawdown_pct",
}


def trade(
    *,
    quantity: int = 100,
    pnl_pct: float = 10.0,
    gross_pnl: float = 1000.0,
    pnl: float = 1000.0,
    transaction_cost: float = 0.0,
) -> Trade:
    return Trade(
        symbol="TEST",
        entry_time=START,
        entry_price=100.0,
        exit_time=START + timedelta(minutes=15),
        exit_price=100.0 * (1 + pnl_pct / 100),
        stop_price=98.0,
        quantity=quantity,
        direction="LONG",
        exit_reason="STRATEGY_EXIT",
        pnl=pnl,
        gross_pnl=gross_pnl,
        transaction_cost=transaction_cost,
        pnl_pct=pnl_pct,
    )


def bar(index: int, equity: float, *, position_size: float = 0) -> BarRecord:
    return BarRecord(
        timestamp=START + timedelta(minutes=15 * index),
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=1000.0,
        strategy="test",
        state=None,
        signal=None,
        execution_event=None,
        execution_price=None,
        execution_quantity=None,
        decision_snapshot={},
        equity=equity,
        cash=equity,
        position_size=position_size,
        drawdown=0.0,
    )


def result(
    equities: list[float],
    *,
    trades: list[Trade] | None = None,
    final_position_size: float = 0,
) -> BacktestResult:
    records = [
        bar(
            index,
            equity,
            position_size=(
                final_position_size if index == len(equities) - 1 else 0
            ),
        )
        for index, equity in enumerate(equities)
    ]
    return BacktestResult(
        trades=trades or [],
        bar_records=records,
        session_id="m4.4-metrics",
    )


def test_trade_builder_preserves_instrument_fill_to_fill_return() -> None:
    position = Position(
        symbol="TEST",
        entry_time=START,
        entry_price=100.0,
        entry_transaction_cost=20.0,
        quantity=100,
        stop_price=98.0,
        direction="LONG",
        entry_index=0,
    )

    completed_trade = TradeBuilder.build_long_trade(
        position=position,
        exit_price=110.0,
        exit_reason="STRATEGY_EXIT",
        exit_time=START + timedelta(minutes=15),
        transaction_cost=70.0,
    )

    assert completed_trade.pnl_pct == pytest.approx(10.0)
    assert completed_trade.gross_pnl == pytest.approx(1000.0)
    assert completed_trade.pnl == pytest.approx(930.0)


def test_authoritative_contract_separates_instrument_and_account_returns() -> None:
    metrics = PerformanceMetrics.summarize_backtest(
        result([100000.0, 101000.0], trades=[trade()])
    )

    assert set(metrics) == EXPECTED_KEYS
    assert metrics["mean_instrument_return_pct"] == pytest.approx(10.0)
    assert metrics["account_pnl"] == pytest.approx(1000.0)
    assert metrics["account_return_pct"] == pytest.approx(1.0)
    assert "avg_win_pct" not in metrics
    assert "avg_loss_pct" not in metrics
    assert "expectancy_pct" not in metrics
    assert "max_drawdown_pct" not in metrics


def test_completed_trade_monetary_metrics_and_costs_remain_explicit() -> None:
    trades = [
        trade(
            quantity=10,
            pnl_pct=10.0,
            gross_pnl=100.0,
            pnl=93.0,
            transaction_cost=7.0,
        ),
        trade(
            quantity=20,
            pnl_pct=-5.0,
            gross_pnl=-100.0,
            pnl=-111.0,
            transaction_cost=11.0,
        ),
        trade(
            quantity=5,
            pnl_pct=0.0,
            gross_pnl=0.0,
            pnl=0.0,
            transaction_cost=0.0,
        ),
    ]

    metrics = PerformanceMetrics.summarize_backtest(
        result([100000.0, 99982.0], trades=trades)
    )

    assert metrics["completed_trade_count"] == 3
    assert metrics["net_profitable_trade_count"] == 1
    assert metrics["net_losing_trade_count"] == 1
    assert metrics["net_breakeven_trade_count"] == 1
    assert metrics["net_profitable_trade_rate_pct"] == pytest.approx(100 / 3)
    assert metrics["mean_positive_instrument_return_pct"] == pytest.approx(10.0)
    assert metrics["mean_negative_instrument_return_pct"] == pytest.approx(-5.0)
    assert metrics["mean_instrument_return_pct"] == pytest.approx(5 / 3)
    assert metrics["gross_realized_pnl"] == pytest.approx(0.0)
    assert metrics["net_realized_pnl"] == pytest.approx(-18.0)
    assert metrics["mean_net_pnl_per_completed_trade"] == pytest.approx(-6.0)
    assert metrics["completed_trade_transaction_cost_total"] == pytest.approx(
        18.0
    )


def test_transaction_cost_affects_account_return_through_equity() -> None:
    completed_trade = trade(
        gross_pnl=1000.0,
        pnl=950.0,
        transaction_cost=50.0,
    )

    metrics = PerformanceMetrics.summarize_backtest(
        result([100000.0, 100950.0], trades=[completed_trade])
    )

    assert metrics["gross_realized_pnl"] == pytest.approx(1000.0)
    assert metrics["net_realized_pnl"] == pytest.approx(950.0)
    assert metrics["account_pnl"] == pytest.approx(950.0)
    assert metrics["account_return_pct"] == pytest.approx(0.95)


def test_max_drawdown_uses_authoritative_equity_not_trade_compounding() -> None:
    unrelated_trade = trade(pnl_pct=80.0, gross_pnl=1.0, pnl=1.0)

    metrics = PerformanceMetrics.summarize_backtest(
        result(
            [100000.0, 105000.0, 94500.0, 102000.0],
            trades=[unrelated_trade],
        )
    )

    assert metrics["max_equity_drawdown_pct"] == pytest.approx(10.0)
    assert metrics["account_return_pct"] == pytest.approx(2.0)


def test_zero_completed_trades_still_report_final_unrealized_equity() -> None:
    metrics = PerformanceMetrics.summarize_backtest(
        result([100000.0, 105000.0, 101995.0], final_position_size=100)
    )

    assert metrics["completed_trade_count"] == 0
    assert metrics["completed_trade_transaction_cost_total"] == 0.0
    assert metrics["account_pnl"] == pytest.approx(1995.0)
    assert metrics["account_return_pct"] == pytest.approx(1.995)
    assert metrics["max_equity_drawdown_pct"] == pytest.approx(
        (105000.0 - 101995.0) / 105000.0 * 100
    )


def test_open_terminal_entry_cost_can_create_loss_without_completed_trade() -> None:
    metrics = PerformanceMetrics.summarize_backtest(
        result([100000.0, 99995.0], final_position_size=100)
    )

    assert metrics["completed_trade_count"] == 0
    assert metrics["net_realized_pnl"] == 0.0
    assert metrics["completed_trade_transaction_cost_total"] == 0.0
    assert metrics["account_pnl"] == pytest.approx(-5.0)
    assert metrics["account_return_pct"] == pytest.approx(-0.005)


@pytest.mark.parametrize(
    ("equities", "expected_return", "expected_drawdown"),
    [
        ([100000.0, 100000.0], 0.0, 0.0),
        ([100000.0, 98000.0], -2.0, 2.0),
        ([100000.0, 80000.0, 110000.0], 10.0, 20.0),
        ([100000.0], 0.0, 0.0),
        ([100000.0, -10000.0], -110.0, 110.0),
    ],
)
def test_account_return_and_drawdown_paths(
    equities: list[float],
    expected_return: float,
    expected_drawdown: float,
) -> None:
    metrics = PerformanceMetrics.summarize_backtest(result(equities))

    assert metrics["account_return_pct"] == pytest.approx(expected_return)
    assert metrics["max_equity_drawdown_pct"] == pytest.approx(
        expected_drawdown
    )


def test_equal_instrument_returns_do_not_replace_different_account_outcomes() -> None:
    small_position = PerformanceMetrics.summarize_backtest(
        result([100000.0, 101000.0], trades=[trade(quantity=100)])
    )
    large_position = PerformanceMetrics.summarize_backtest(
        result(
            [100000.0, 105000.0],
            trades=[
                trade(
                    quantity=500,
                    gross_pnl=5000.0,
                    pnl=5000.0,
                )
            ],
        )
    )

    assert small_position["mean_instrument_return_pct"] == 10.0
    assert large_position["mean_instrument_return_pct"] == 10.0
    assert small_position["account_return_pct"] == 1.0
    assert large_position["account_return_pct"] == 5.0


def test_empty_result_returns_complete_zero_contract() -> None:
    metrics = PerformanceMetrics.summarize_backtest(result([]))

    assert set(metrics) == EXPECTED_KEYS
    assert all(value == 0 for value in metrics.values())


def test_trades_without_equity_records_fail_explicitly() -> None:
    with pytest.raises(ValueError, match="trades require authoritative equity"):
        PerformanceMetrics.summarize_backtest(result([], trades=[trade()]))


@pytest.mark.parametrize("starting_equity", [0.0, -1.0])
def test_non_positive_starting_equity_fails(starting_equity: float) -> None:
    with pytest.raises(ValueError, match="strictly positive"):
        PerformanceMetrics.summarize_backtest(result([starting_equity]))


@pytest.mark.parametrize(
    "equities",
    [
        [nan],
        [inf],
        [-inf],
        [100000.0, nan],
        [100000.0, inf],
        [100000.0, -inf],
    ],
)
def test_non_finite_equity_fails(equities: list[float]) -> None:
    with pytest.raises(ValueError, match="must be finite"):
        PerformanceMetrics.summarize_backtest(result(equities))


@pytest.mark.parametrize(
    ("completed_trade", "profitable", "losing", "breakeven"),
    [
        (trade(pnl=10.0), 1, 0, 0),
        (trade(pnl=-10.0, pnl_pct=-1.0), 0, 1, 0),
        (trade(pnl=0.0, gross_pnl=0.0, pnl_pct=0.0), 0, 0, 1),
        (
            trade(
                pnl=-1.0,
                gross_pnl=10.0,
                transaction_cost=11.0,
                pnl_pct=1.0,
            ),
            0,
            1,
            0,
        ),
    ],
)
def test_net_trade_population_is_distinct_from_instrument_return(
    completed_trade: Trade,
    profitable: int,
    losing: int,
    breakeven: int,
) -> None:
    metrics = PerformanceMetrics.summarize_backtest(
        result([100000.0, 100000.0 + completed_trade.pnl], trades=[completed_trade])
    )

    assert metrics["net_profitable_trade_count"] == profitable
    assert metrics["net_losing_trade_count"] == losing
    assert metrics["net_breakeven_trade_count"] == breakeven
    assert metrics["mean_instrument_return_pct"] == completed_trade.pnl_pct


def test_programmatic_metrics_are_not_rounded() -> None:
    metrics = PerformanceMetrics.summarize_backtest(
        result([100000.0, 100123.456789])
    )
    expected = (100123.456789 - 100000.0) / 100000.0 * 100

    assert metrics["account_return_pct"] == expected
    assert metrics["account_return_pct"] != round(expected, 2)

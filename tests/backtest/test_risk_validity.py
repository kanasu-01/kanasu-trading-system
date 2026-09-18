from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.backtest.backtest_engine import BacktestEngine
from core.config.execution_config import ExecutionConfig
from core.entities.candle import Candle
from core.execution.execution_feedback import (
    ExecutionFeedbackType,
    ExecutionRejectionReason,
)
from core.execution.trade_execution_engine import TradeExecutionEngine
from core.runtime.runtime_context import RuntimeContext
from core.runtime.dataset_context import DatasetContext
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import SignalType


START = datetime(2025, 1, 6, 9, 15)


class NoopStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(name="Noop")

    def on_new_candle(self, series):
        return None

    def reset(self) -> None:
        pass


def make_candle(
    *,
    timestamp: datetime = START,
    open_price: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.0,
) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1_000,
    )


def make_engine(
    *,
    capital: float = 100_000.0,
    risk_per_trade_pct: float = 1.0,
    brokerage_enabled: bool = False,
    slippage_enabled: bool = False,
) -> TradeExecutionEngine:
    return TradeExecutionEngine(
        strategy=NoopStrategy(),
        account_capital=capital,
        session_id="m4.5-risk-validity",
        runtime_context=RuntimeContext(
            execution_config=ExecutionConfig(
                slippage_pct=0.0,
                slippage_enabled=slippage_enabled,
                brokerage_enabled=brokerage_enabled,
            )
        ),
        risk_per_trade_pct=risk_per_trade_pct,
    )


def process_buy(
    engine: TradeExecutionEngine,
    *,
    candle: Candle | None = None,
    decision_close: float | None = 100.0,
    rejection_midpoint: float | None = None,
):
    return engine.process_backtest_candle(
        pending_signal=SignalType.BUY,
        decision_close=decision_close,
        rejection_midpoint=rejection_midpoint,
        candle=candle or make_candle(),
        execution_index=1,
        symbol="TEST",
    )


def assert_rejected_entry_is_mutation_free(
    engine: TradeExecutionEngine,
    before,
) -> None:
    assert engine.portfolio_manager.snapshot() == before
    assert engine.get_runtime_position("TEST") is None
    assert engine.completed_trades == []
    assert engine.last_execution_event is None
    assert engine.last_execution_price is None
    assert engine.last_execution_quantity is None
    assert engine.last_transaction_cost == 0.0


def test_backtest_entry_sizes_from_current_pre_entry_equity() -> None:
    engine = make_engine()
    engine.portfolio_manager.update_equity(
        cash=50_000.0,
        position_size=0,
        current_price=0.0,
    )

    process_buy(engine, decision_close=90.0 / 0.98)

    position = engine.get_runtime_position("TEST")
    assert position is not None
    assert position.quantity == 50


def test_runtime_context_risk_setting_reaches_backtest_execution() -> None:
    backtest = BacktestEngine(
        strategy=NoopStrategy(),
        initial_capital=100_000.0,
        runtime_context=RuntimeContext(risk_per_trade_pct=2.5),
        dataset_context=DatasetContext(symbol="TEST"),
    )

    assert backtest.execution_engine.risk_manager.risk_per_trade_pct == 2.5


def test_current_open_sizing_does_not_observe_current_high_low_or_close() -> None:
    first = make_engine()
    second = make_engine()

    process_buy(
        first,
        candle=make_candle(high=101.0, low=99.0, close=100.0),
        decision_close=90.0 / 0.98,
    )
    process_buy(
        second,
        candle=make_candle(high=1_000.0, low=91.0, close=900.0),
        decision_close=90.0 / 0.98,
    )

    first_position = first.get_runtime_position("TEST")
    second_position = second.get_runtime_position("TEST")
    assert first_position is not None
    assert second_position is not None
    assert first_position.entry_price == second_position.entry_price == 100.0
    assert first_position.stop_price == second_position.stop_price == 90.0
    assert first_position.quantity == second_position.quantity == 100


@pytest.mark.parametrize(
    "decision_close",
    [
        pytest.param(None, id="missing"),
        pytest.param(0.0, id="zero"),
        pytest.param(-1.0, id="negative"),
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="positive-infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
        pytest.param(100.0 / 0.98, id="equal-to-fill"),
        pytest.param(101.0 / 0.98, id="above-fill"),
    ],
)
def test_invalid_derived_stop_is_rejected_without_mutation(decision_close) -> None:
    engine = make_engine()
    engine.last_execution_event = "STALE"
    engine.last_execution_price = 123.0
    engine.last_execution_quantity = 7
    engine.last_transaction_cost = 9.0
    before = engine.portfolio_manager.snapshot()

    feedback = process_buy(
        engine,
        decision_close=decision_close,
    )

    assert feedback[0].event_type is ExecutionFeedbackType.ENTRY_REJECTED
    assert feedback[0].rejection_reason is ExecutionRejectionReason.INVALID_ENTRY
    assert_rejected_entry_is_mutation_free(engine, before)


@pytest.mark.parametrize(
    "rejection_midpoint",
    [
        pytest.param(float("nan"), id="nan"),
        pytest.param(float("inf"), id="positive-infinity"),
        pytest.param(float("-inf"), id="negative-infinity"),
    ],
)
def test_non_finite_rejection_midpoint_is_rejected_without_mutation(
    rejection_midpoint: float,
) -> None:
    engine = make_engine()
    engine.last_execution_event = "STALE"
    engine.last_execution_price = 123.0
    engine.last_execution_quantity = 7
    engine.last_transaction_cost = 9.0
    before = engine.portfolio_manager.snapshot()

    feedback = process_buy(
        engine,
        rejection_midpoint=rejection_midpoint,
    )

    assert feedback[0].event_type is ExecutionFeedbackType.ENTRY_REJECTED
    assert feedback[0].rejection_reason is ExecutionRejectionReason.INVALID_ENTRY
    assert_rejected_entry_is_mutation_free(engine, before)


def test_fully_affordable_candidate_is_unchanged() -> None:
    engine = make_engine(capital=1_000.0, brokerage_enabled=True)
    engine.risk_manager.calculate_position_size_for_equity = lambda **_: 5

    process_buy(engine)

    position = engine.get_runtime_position("TEST")
    assert position is not None
    assert position.quantity == 5


def test_candidate_exceeding_cash_is_reduced_to_largest_affordable_quantity() -> None:
    engine = make_engine(capital=1_000.0, brokerage_enabled=True)
    engine.risk_manager.calculate_position_size_for_equity = lambda **_: 10

    process_buy(engine)

    position = engine.get_runtime_position("TEST")
    assert position is not None
    assert position.quantity == 9
    assert engine.portfolio_manager.cash == pytest.approx(99.28)
    assert engine.portfolio_manager.cash >= 0.0


def test_brokerage_can_make_raw_notional_unaffordable() -> None:
    with_brokerage = make_engine(capital=1_000.0, brokerage_enabled=True)
    without_brokerage = make_engine(capital=1_000.0, brokerage_enabled=False)
    with_brokerage.risk_manager.calculate_position_size_for_equity = lambda **_: 10
    without_brokerage.risk_manager.calculate_position_size_for_equity = lambda **_: 10

    process_buy(with_brokerage)
    process_buy(without_brokerage)

    assert with_brokerage.get_runtime_position("TEST").quantity == 9
    assert without_brokerage.get_runtime_position("TEST").quantity == 10
    assert without_brokerage.portfolio_manager.cash == 0.0


def test_no_affordable_share_rejects_without_mutating_account_state() -> None:
    engine = make_engine(capital=100.0, brokerage_enabled=True)
    engine.risk_manager.calculate_position_size_for_equity = lambda **_: 1
    engine.last_transaction_cost = 123.0
    before = engine.portfolio_manager.snapshot()

    feedback = process_buy(engine)

    after = engine.portfolio_manager.snapshot()
    assert feedback[0].event_type is ExecutionFeedbackType.ENTRY_REJECTED
    assert feedback[0].rejection_reason is ExecutionRejectionReason.INSUFFICIENT_CASH
    assert engine.get_runtime_position("TEST") is None
    assert after == before
    assert engine.completed_trades == []
    assert engine.last_transaction_cost == 0.0


@pytest.mark.parametrize(
    ("rejection_case", "expected_reason"),
    [
        ("drawdown", ExecutionRejectionReason.DRAWDOWN_LIMIT),
        ("invalid_entry", ExecutionRejectionReason.INVALID_ENTRY),
        ("invalid_quantity", ExecutionRejectionReason.INVALID_QUANTITY),
        ("portfolio_risk", ExecutionRejectionReason.PORTFOLIO_RISK_LIMIT),
        ("insufficient_cash", ExecutionRejectionReason.INSUFFICIENT_CASH),
    ],
)
def test_each_entry_rejection_class_is_mutation_free_and_clears_diagnostics(
    rejection_case: str,
    expected_reason: ExecutionRejectionReason,
) -> None:
    engine = make_engine(
        capital=100.0 if rejection_case == "insufficient_cash" else 100_000.0,
        brokerage_enabled=rejection_case == "insufficient_cash",
    )
    decision_close = 100.0

    if rejection_case == "drawdown":
        engine.drawdown_manager.update_equity_period(START, 100_000.0)
        engine.drawdown_manager.observe_equity(97_000.0)
    elif rejection_case == "invalid_entry":
        decision_close = None
    elif rejection_case == "invalid_quantity":
        engine.risk_manager.calculate_position_size_for_equity = lambda **_: None
    elif rejection_case == "portfolio_risk":
        engine.portfolio_risk_manager.can_open_new_trade = lambda **_: False
    elif rejection_case == "insufficient_cash":
        engine.risk_manager.calculate_position_size_for_equity = lambda **_: 1

    engine.last_execution_event = "STALE"
    engine.last_execution_price = 123.0
    engine.last_execution_quantity = 7
    engine.last_transaction_cost = 9.0
    before = engine.portfolio_manager.snapshot()

    feedback = process_buy(engine, decision_close=decision_close)

    assert feedback[0].event_type is ExecutionFeedbackType.ENTRY_REJECTED
    assert feedback[0].rejection_reason is expected_reason
    assert_rejected_entry_is_mutation_free(engine, before)


def test_one_share_affordability_below_equal_and_above_cost_boundary() -> None:
    engine = make_engine(capital=1_000.0, brokerage_enabled=True)
    required_cash = 100.0 + engine.brokerage_model.calculate(100.0).total_cost

    assert engine._largest_affordable_quantity(
        candidate_quantity=1,
        entry_price=100.0,
        available_cash=required_cash - 0.001,
    ) is None
    assert engine._largest_affordable_quantity(
        candidate_quantity=1,
        entry_price=100.0,
        available_cash=required_cash,
    ) == (1, pytest.approx(required_cash - 100.0))
    assert engine._largest_affordable_quantity(
        candidate_quantity=1,
        entry_price=100.0,
        available_cash=required_cash + 0.001,
    ) == (1, pytest.approx(required_cash - 100.0))


def test_affordability_handles_brokerage_cap_and_rounding_boundary() -> None:
    engine = make_engine(capital=100_000.0, brokerage_enabled=True)
    required_699 = 100.0 * 699 + engine.brokerage_model.calculate(69_900.0).total_cost
    required_700 = 100.0 * 700 + engine.brokerage_model.calculate(70_000.0).total_cost
    available_cash = (required_699 + required_700) / 2

    affordable = engine._largest_affordable_quantity(
        candidate_quantity=700,
        entry_price=100.0,
        available_cash=available_cash,
    )

    assert affordable == (699, engine.brokerage_model.calculate(69_900.0).total_cost)


def test_entry_cost_is_charged_exactly_once_and_observed_through_equity() -> None:
    engine = make_engine(capital=100_000.0, brokerage_enabled=True)
    engine.risk_manager.calculate_position_size_for_equity = lambda **_: 10

    process_buy(engine)

    position = engine.get_runtime_position("TEST")
    expected_cost = engine.brokerage_model.calculate(1_000.0).total_cost
    assert position is not None
    assert position.entry_transaction_cost == expected_cost
    assert engine.last_transaction_cost == expected_cost
    assert engine.portfolio_manager.cash == 100_000.0 - 1_000.0 - expected_cost
    assert engine.portfolio_manager.equity == 100_000.0 - expected_cost
    assert engine.drawdown_manager.daily_loss_pct == pytest.approx(
        expected_cost / 100_000.0 * 100
    )


def test_entry_transaction_cost_can_latch_equity_guard() -> None:
    engine = make_engine(capital=100_000.0, brokerage_enabled=True)
    engine.drawdown_manager.max_daily_loss_pct = 0.0001
    engine.risk_manager.calculate_position_size_for_equity = lambda **_: 10

    process_buy(engine)

    assert engine.get_runtime_position("TEST") is not None
    assert engine.drawdown_manager.daily_breached is True
    assert engine.drawdown_manager.can_trade() is False


def test_unrealized_mark_alone_can_latch_equity_guard() -> None:
    engine = make_engine()
    process_buy(engine, decision_close=90.0 / 0.98)

    engine.mark_open_position_to_market(symbol="TEST", price=60.0)

    assert engine.drawdown_manager.daily_loss_pct == pytest.approx(4.0)
    assert engine.drawdown_manager.daily_breached is True


def test_realized_loss_uses_post_close_equity_without_legacy_trade_aggregation() -> None:
    engine = make_engine()
    process_buy(engine, decision_close=90.0 / 0.98)

    feedback = engine.process_backtest_candle(
        pending_signal=SignalType.SELL,
        decision_close=100.0,
        rejection_midpoint=None,
        candle=make_candle(
            timestamp=START + timedelta(minutes=15),
            open_price=70.0,
            high=71.0,
            low=69.0,
            close=70.0,
        ),
        execution_index=2,
        symbol="TEST",
    )

    assert feedback[0].event_type is ExecutionFeedbackType.PROTECTIVE_EXIT
    assert engine.portfolio_manager.equity == pytest.approx(97_000.0)
    assert engine.drawdown_manager.daily_loss_pct == pytest.approx(3.0)
    assert engine.drawdown_manager.daily_pnl_pct == 0.0


def test_exit_transaction_cost_participates_in_post_close_period_loss() -> None:
    engine = make_engine(brokerage_enabled=True)
    engine.risk_manager.calculate_position_size_for_equity = lambda **_: 10
    process_buy(engine, decision_close=100.0)
    position = engine.get_runtime_position("TEST")
    assert position is not None

    engine.process_backtest_candle(
        pending_signal=None,
        decision_close=None,
        rejection_midpoint=None,
        candle=make_candle(
            timestamp=START + timedelta(minutes=15),
            open_price=90.0,
            high=91.0,
            low=89.0,
            close=90.0,
        ),
        execution_index=2,
        symbol="TEST",
    )

    entry_cost = engine.brokerage_model.calculate(1_000.0).total_cost
    exit_cost = engine.brokerage_model.calculate(900.0).total_cost
    expected_equity = 100_000.0 - 100.0 - entry_cost - exit_cost
    assert engine.portfolio_manager.equity == pytest.approx(expected_equity)
    assert engine.completed_trades[0].transaction_cost == pytest.approx(
        entry_cost + exit_cost
    )
    assert engine.drawdown_manager.daily_loss_pct == pytest.approx(
        (100_000.0 - expected_equity) / 100_000.0 * 100
    )
    assert engine.drawdown_manager.daily_pnl_pct == 0.0


def test_gap_stop_after_date_transition_belongs_to_new_period() -> None:
    engine = make_engine()
    process_buy(engine, decision_close=100.0)
    engine.mark_open_position_to_market(symbol="TEST", price=100.0)

    engine.process_backtest_candle(
        pending_signal=None,
        decision_close=None,
        rejection_midpoint=None,
        candle=make_candle(
            timestamp=START + timedelta(days=1),
            open_price=90.0,
            high=91.0,
            low=89.0,
            close=90.0,
        ),
        execution_index=2,
        symbol="TEST",
    )

    assert engine.drawdown_manager.daily_start_equity == 100_000.0
    assert engine.drawdown_manager.daily_loss_pct == pytest.approx(2.0)
    assert engine.drawdown_manager.daily_breached is False


def test_carried_position_weekly_baseline_uses_prior_marked_equity() -> None:
    engine = make_engine()
    friday = datetime(2025, 1, 10, 15, 15)
    monday = datetime(2025, 1, 13, 9, 15)
    process_buy(
        engine,
        candle=make_candle(timestamp=friday),
        decision_close=100.0,
    )
    engine.mark_open_position_to_market(symbol="TEST", price=105.0)
    assert engine.portfolio_manager.equity == 101_000.0

    engine.process_backtest_candle(
        pending_signal=None,
        decision_close=None,
        rejection_midpoint=None,
        candle=make_candle(
            timestamp=monday,
            open_price=90.0,
            high=91.0,
            low=89.0,
            close=90.0,
        ),
        execution_index=2,
        symbol="TEST",
    )

    assert engine.drawdown_manager.weekly_start_equity == 101_000.0
    assert engine.portfolio_manager.equity == 98_000.0
    assert engine.drawdown_manager.weekly_loss_pct == pytest.approx(
        3_000.0 / 101_000.0 * 100
    )


def test_latched_guard_blocks_new_entry_but_new_date_resets_daily_latch() -> None:
    engine = make_engine()
    engine.drawdown_manager.update_equity_period(START, 100_000.0)
    engine.drawdown_manager.observe_equity(97_000.0)

    blocked = process_buy(engine, decision_close=90.0 / 0.98)
    assert blocked[0].rejection_reason is ExecutionRejectionReason.DRAWDOWN_LIMIT

    accepted = process_buy(
        engine,
        candle=make_candle(timestamp=START + timedelta(days=1)),
        decision_close=90.0 / 0.98,
    )
    assert accepted[0].event_type is ExecutionFeedbackType.ENTRY_ACCEPTED


def test_latched_entry_guard_does_not_block_protective_exit() -> None:
    engine = make_engine()
    process_buy(engine, decision_close=100.0)
    engine.drawdown_manager.observe_equity(97_000.0)
    assert engine.drawdown_manager.can_trade() is False

    feedback = engine.process_backtest_candle(
        pending_signal=None,
        decision_close=None,
        rejection_midpoint=None,
        candle=make_candle(
            timestamp=START + timedelta(minutes=15),
            open_price=90.0,
            high=91.0,
            low=89.0,
            close=90.0,
        ),
        execution_index=2,
        symbol="TEST",
    )

    assert feedback[0].event_type is ExecutionFeedbackType.PROTECTIVE_EXIT
    assert engine.get_runtime_position("TEST") is None


def test_non_finite_authoritative_cash_is_an_invariant_failure() -> None:
    engine = make_engine()
    engine.portfolio_manager.cash = float("nan")

    with pytest.raises(ValueError, match="authoritative cash must be finite"):
        process_buy(engine)


def test_non_finite_authoritative_equity_is_an_invariant_failure() -> None:
    engine = make_engine()
    engine.portfolio_manager.equity = float("nan")

    with pytest.raises(ValueError, match="equity must be finite"):
        process_buy(engine)


@pytest.mark.parametrize("non_finite_fill", [float("nan"), float("inf")])
def test_non_finite_actual_fill_after_slippage_fails_at_execution_boundary(
    non_finite_fill: float,
) -> None:
    engine = make_engine(slippage_enabled=True)
    engine.slippage_model.apply_buy_slippage = lambda _: non_finite_fill
    engine.last_execution_event = "STALE"
    engine.last_execution_price = 123.0
    engine.last_execution_quantity = 7
    engine.last_transaction_cost = 9.0
    before = engine.portfolio_manager.snapshot()

    with pytest.raises(ValueError, match="actual entry fill must be finite"):
        process_buy(engine)

    assert_rejected_entry_is_mutation_free(engine, before)


def test_non_finite_entry_transaction_cost_is_an_invariant_failure() -> None:
    engine = make_engine(brokerage_enabled=True)
    engine.risk_manager.calculate_position_size_for_equity = lambda **_: 1
    engine.brokerage_model.calculate = lambda turnover: SimpleNamespace(
        total_cost=float("nan")
    )

    with pytest.raises(ValueError, match="entry transaction cost must be finite"):
        process_buy(engine)

    assert engine.get_runtime_position("TEST") is None
    assert engine.portfolio_manager.cash == 100_000.0

from datetime import datetime

import pytest

from core.risk.drawdown_risk_manager import (
    DrawdownRiskManager,
)


def test_daily_drawdown_resets_on_new_day():

    manager = DrawdownRiskManager(
        max_daily_loss_pct=3.0,
        max_weekly_loss_pct=6.0,
    )

    day_one = datetime(2026, 8, 24, 10, 0)
    day_two = datetime(2026, 8, 25, 10, 0)

    # Establish day one.
    manager.update_period(day_one)

    # Hit the daily loss limit.
    manager.record_trade_pnl(-3.0)

    assert manager.can_trade() is False

    # New trading day.
    manager.update_period(day_two)

    assert manager.can_trade() is True


def test_weekly_drawdown_resets_on_new_week():

    manager = DrawdownRiskManager(
        max_daily_loss_pct=3.0,
        max_weekly_loss_pct=6.0,
    )

    week_one = datetime(2026, 8, 24, 10, 0)
    week_two = datetime(2026, 8, 31, 10, 0)

    # Establish week one.
    manager.update_period(week_one)

    # Hit the weekly loss limit.
    manager.record_trade_pnl(-6.0)

    assert manager.can_trade() is False

    # New trading week.
    manager.update_period(week_two)

    assert manager.can_trade() is True


def test_daily_reset_does_not_reset_weekly_drawdown():

    manager = DrawdownRiskManager(
        max_daily_loss_pct=3.0,
        max_weekly_loss_pct=6.0,
    )

    monday = datetime(2026, 8, 24, 10, 0)
    tuesday = datetime(2026, 8, 25, 10, 0)

    # Establish Monday.
    manager.update_period(monday)

    # Lose 3% on Monday.
    manager.record_trade_pnl(-3.0)

    assert manager.can_trade() is False

    # Tuesday: daily P&L should reset.
    manager.update_period(tuesday)

    # Daily limit is cleared.
    assert manager.daily_pnl_pct == 0.0

    # But weekly loss must remain.
    assert manager.weekly_pnl_pct == -3.0

    # Weekly limit has NOT been reached yet.
    assert manager.can_trade() is True


def test_weekly_drawdown_resets_only_at_new_week():

    manager = DrawdownRiskManager(
        max_daily_loss_pct=3.0,
        max_weekly_loss_pct=6.0,
    )

    monday = datetime(2026, 8, 24, 10, 0)
    tuesday = datetime(2026, 8, 25, 10, 0)
    next_monday = datetime(2026, 8, 31, 10, 0)

    manager.update_period(monday)

    manager.record_trade_pnl(-3.0)

    # Same week: weekly loss must remain.
    manager.update_period(tuesday)

    assert manager.daily_pnl_pct == 0.0
    assert manager.weekly_pnl_pct == -3.0

    # New week: weekly loss resets.
    manager.update_period(next_monday)

    assert manager.daily_pnl_pct == 0.0
    assert manager.weekly_pnl_pct == 0.0


def test_equity_guard_below_daily_threshold_allows_entry():
    manager = DrawdownRiskManager(3.0, 6.0)
    manager.update_equity_period(datetime(2025, 1, 6), 100_000.0)
    manager.observe_equity(97_001.0)

    assert manager.daily_loss_pct == pytest.approx(2.999)
    assert manager.can_trade() is True


def test_exact_daily_threshold_latches_and_blocks_entry():
    manager = DrawdownRiskManager(3.0, 6.0)
    manager.update_equity_period(datetime(2025, 1, 6), 100_000.0)
    manager.observe_equity(97_000.0)

    assert manager.daily_loss_pct == pytest.approx(3.0)
    assert manager.daily_breached is True
    assert manager.can_trade() is False


def test_exact_weekly_threshold_latches_and_blocks_entry():
    manager = DrawdownRiskManager(10.0, 6.0)
    manager.update_equity_period(datetime(2025, 1, 6), 100_000.0)
    manager.observe_equity(94_000.0)

    assert manager.weekly_loss_pct == pytest.approx(6.0)
    assert manager.weekly_breached is True
    assert manager.can_trade() is False


def test_new_date_resets_daily_state_but_preserves_weekly_state():
    manager = DrawdownRiskManager(3.0, 6.0)
    manager.update_equity_period(datetime(2025, 1, 6), 100_000.0)
    manager.observe_equity(97_000.0)
    manager.update_equity_period(datetime(2025, 1, 7), 97_000.0)

    assert manager.daily_start_equity == 97_000.0
    assert manager.daily_loss_pct == 0.0
    assert manager.daily_breached is False
    assert manager.weekly_start_equity == 100_000.0
    assert manager.weekly_loss_pct == pytest.approx(3.0)


def test_new_iso_week_resets_weekly_state():
    manager = DrawdownRiskManager(10.0, 6.0)
    manager.update_equity_period(datetime(2025, 1, 3), 100_000.0)
    manager.observe_equity(94_000.0)
    manager.update_equity_period(datetime(2025, 1, 6), 94_000.0)

    assert manager.weekly_start_equity == 94_000.0
    assert manager.weekly_loss_pct == 0.0
    assert manager.weekly_breached is False


def test_same_iso_week_number_in_different_year_resets_weekly_state():
    manager = DrawdownRiskManager(10.0, 6.0)
    manager.update_equity_period(datetime(2025, 1, 2), 100_000.0)
    manager.observe_equity(94_000.0)
    manager.update_equity_period(datetime(2026, 1, 2), 94_000.0)

    assert manager.weekly_start_equity == 94_000.0
    assert manager.weekly_loss_pct == 0.0
    assert manager.weekly_breached is False


def test_gain_then_decline_is_measured_from_period_start_not_peak():
    manager = DrawdownRiskManager(4.0, 6.0)
    manager.update_equity_period(datetime(2025, 1, 6), 100_000.0)
    manager.observe_equity(110_000.0)
    manager.observe_equity(97_000.0)

    assert manager.daily_loss_pct == pytest.approx(3.0)
    assert manager.can_trade() is True


def test_breach_remains_sticky_after_recovery():
    manager = DrawdownRiskManager(3.0, 6.0)
    manager.update_equity_period(datetime(2025, 1, 6), 100_000.0)
    manager.observe_equity(97_000.0)
    manager.observe_equity(105_000.0)

    assert manager.daily_loss_pct == 0.0
    assert manager.daily_breached is True
    assert manager.can_trade() is False


def test_sparse_period_transition_uses_first_observed_candle():
    manager = DrawdownRiskManager(3.0, 6.0)
    manager.update_equity_period(datetime(2025, 1, 3), 100_000.0)
    manager.observe_equity(98_000.0)
    manager.update_equity_period(datetime(2025, 1, 20), 98_000.0)

    assert manager.daily_start_equity == 98_000.0
    assert manager.weekly_start_equity == 98_000.0
    assert manager.daily_loss_pct == 0.0
    assert manager.weekly_loss_pct == 0.0


@pytest.mark.parametrize("baseline", [0.0, -1.0])
def test_non_positive_period_baseline_latches_without_division(baseline: float):
    manager = DrawdownRiskManager(3.0, 6.0)
    manager.update_equity_period(datetime(2025, 1, 6), baseline)

    assert manager.daily_breached is True
    assert manager.weekly_breached is True
    assert manager.can_trade() is False


@pytest.mark.parametrize("equity", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_equity_fails_explicitly(equity: float):
    manager = DrawdownRiskManager(3.0, 6.0)

    with pytest.raises(ValueError, match="equity must be finite"):
        manager.update_equity_period(datetime(2025, 1, 6), equity)


def test_negative_equity_reports_unclipped_loss_above_one_hundred_percent():
    manager = DrawdownRiskManager(200.0, 200.0)
    manager.update_equity_period(datetime(2025, 1, 6), 100_000.0)
    manager.observe_equity(-10_000.0)

    assert manager.daily_loss_pct == pytest.approx(110.0)
    assert manager.weekly_loss_pct == pytest.approx(110.0)


def test_simultaneous_daily_and_weekly_breach_is_deterministic():
    manager = DrawdownRiskManager(3.0, 3.0)
    manager.update_equity_period(datetime(2025, 1, 6), 100_000.0)
    manager.observe_equity(97_000.0)

    assert manager.daily_breached is True
    assert manager.weekly_breached is True
    assert manager.can_trade() is False

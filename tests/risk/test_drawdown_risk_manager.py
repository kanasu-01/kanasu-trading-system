from datetime import datetime

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

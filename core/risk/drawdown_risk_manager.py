from datetime import datetime
from enum import Enum


class DrawdownPeriod(Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class DrawdownRiskManager:
    """
    Daily / weekly drawdown guard.

    Stops new trades after loss limits are breached.

    Daily P&L resets when a new calendar day begins.
    Weekly P&L resets when a new ISO calendar week begins.
    """

    def __init__(
        self,
        max_daily_loss_pct: float = 3.0,
        max_weekly_loss_pct: float = 6.0,
    ):
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_weekly_loss_pct = max_weekly_loss_pct

        self.daily_pnl_pct = 0.0
        self.weekly_pnl_pct = 0.0

        self._current_date = None
        self._current_week = None

    def update_period(
        self,
        timestamp: datetime,
    ) -> None:
        """
        Reset drawdown counters when the trading period changes.
        """

        current_date = timestamp.date()
        current_week = timestamp.isocalendar().week

        if self._current_date is None:
            self._current_date = current_date
            self._current_week = current_week
            return

        if current_date != self._current_date:
            self.daily_pnl_pct = 0.0
            self._current_date = current_date

        if current_week != self._current_week:
            self.weekly_pnl_pct = 0.0
            self._current_week = current_week

    def record_trade_pnl(
        self,
        pnl_pct: float,
    ) -> None:
        """
        Record P&L after a trade closes.
        """

        self.daily_pnl_pct += pnl_pct
        self.weekly_pnl_pct += pnl_pct

    def can_trade(self) -> bool:
        """
        Check whether new trades are allowed.
        """

        if self.daily_pnl_pct <= -self.max_daily_loss_pct:
            return False

        if self.weekly_pnl_pct <= -self.max_weekly_loss_pct:
            return False

        return True

    def reset(
        self,
        period: DrawdownPeriod,
    ) -> None:
        """
        Manual reset retained for explicit use when required.
        """

        if period == DrawdownPeriod.DAILY:
            self.daily_pnl_pct = 0.0

        elif period == DrawdownPeriod.WEEKLY:
            self.weekly_pnl_pct = 0.0

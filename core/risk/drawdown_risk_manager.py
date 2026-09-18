from datetime import datetime
from enum import Enum
from math import isfinite


class DrawdownPeriod(Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class DrawdownRiskManager:
    """
    Daily / weekly period-start equity-loss guard for canonical Backtests.

    The trade-P&L methods remain as a bounded compatibility path for legacy
    non-Backtest callers.
    """

    def __init__(
        self,
        max_daily_loss_pct: float = 3.0,
        max_weekly_loss_pct: float = 6.0,
    ):
        if not isfinite(max_daily_loss_pct) or max_daily_loss_pct <= 0:
            raise ValueError("max_daily_loss_pct must be finite and positive")
        if not isfinite(max_weekly_loss_pct) or max_weekly_loss_pct <= 0:
            raise ValueError("max_weekly_loss_pct must be finite and positive")

        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_weekly_loss_pct = max_weekly_loss_pct

        self.daily_pnl_pct = 0.0
        self.weekly_pnl_pct = 0.0

        self._current_date = None
        self._current_week = None

        self.daily_start_equity = None
        self.weekly_start_equity = None
        self.daily_loss_pct = 0.0
        self.weekly_loss_pct = 0.0
        self.daily_breached = False
        self.weekly_breached = False
        self._equity_current_date = None
        self._equity_current_week = None

    @staticmethod
    def _validate_equity(equity: float) -> None:
        if not isfinite(equity):
            raise ValueError("authoritative equity must be finite")

    @staticmethod
    def _week_identity(timestamp: datetime) -> tuple[int, int]:
        iso_calendar = timestamp.isocalendar()
        return (iso_calendar.year, iso_calendar.week)

    def update_equity_period(
        self,
        timestamp: datetime,
        carried_equity: float,
    ) -> None:
        """Initialize or transition equity-loss periods before execution."""

        self._validate_equity(carried_equity)
        current_date = timestamp.date()
        current_week = self._week_identity(timestamp)

        if current_date != self._equity_current_date:
            self._equity_current_date = current_date
            self.daily_start_equity = carried_equity
            self.daily_loss_pct = 0.0
            self.daily_breached = carried_equity <= 0

        if current_week != self._equity_current_week:
            self._equity_current_week = current_week
            self.weekly_start_equity = carried_equity
            self.weekly_loss_pct = 0.0
            self.weekly_breached = carried_equity <= 0

        self.observe_equity(carried_equity)

    def observe_equity(self, equity: float) -> None:
        """Observe authoritative equity and latch inclusive period breaches."""

        self._validate_equity(equity)
        if self.daily_start_equity is None or self.weekly_start_equity is None:
            raise RuntimeError("equity periods must be initialized before observation")

        if self.daily_start_equity > 0:
            self.daily_loss_pct = max(
                0.0,
                (self.daily_start_equity - equity)
                / self.daily_start_equity
                * 100,
            )
            if self.daily_loss_pct >= self.max_daily_loss_pct:
                self.daily_breached = True
        else:
            self.daily_breached = True

        if self.weekly_start_equity > 0:
            self.weekly_loss_pct = max(
                0.0,
                (self.weekly_start_equity - equity)
                / self.weekly_start_equity
                * 100,
            )
            if self.weekly_loss_pct >= self.max_weekly_loss_pct:
                self.weekly_breached = True
        else:
            self.weekly_breached = True

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

        if self.daily_breached or self.weekly_breached:
            return False

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
            self.daily_loss_pct = 0.0
            self.daily_breached = False

        elif period == DrawdownPeriod.WEEKLY:
            self.weekly_pnl_pct = 0.0
            self.weekly_loss_pct = 0.0
            self.weekly_breached = False

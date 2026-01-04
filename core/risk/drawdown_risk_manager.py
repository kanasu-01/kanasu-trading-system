from enum import Enum


class DrawdownPeriod(Enum):
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"


class DrawdownRiskManager:
    """
    Daily / weekly drawdown guard.
    STEP 7.4: Stops new trades after loss limits are breached.
    """

    def __init__(
        self,
        max_daily_loss_pct: float = 3.0,
        max_weekly_loss_pct: float = 6.0,
    ):
        """
        :param max_daily_loss_pct: Max allowed daily loss (%)
        :param max_weekly_loss_pct: Max allowed weekly loss (%)
        """
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_weekly_loss_pct = max_weekly_loss_pct

        self.daily_pnl_pct = 0.0
        self.weekly_pnl_pct = 0.0

    def record_trade_pnl(self, pnl_pct: float) -> None:
        """
        Record PnL after trade closes.
        """
        self.daily_pnl_pct += pnl_pct
        self.weekly_pnl_pct += pnl_pct

    def can_trade(self) -> bool:
        """
        Check if new trades are allowed.
        """

        if self.daily_pnl_pct <= -self.max_daily_loss_pct:
            return False

        if self.weekly_pnl_pct <= -self.max_weekly_loss_pct:
            return False

        return True

    def reset(self, period: DrawdownPeriod) -> None:
        """
        Reset PnL counters at period boundaries.
        """

        if period == DrawdownPeriod.DAILY:
            self.daily_pnl_pct = 0.0

        elif period == DrawdownPeriod.WEEKLY:
            self.weekly_pnl_pct = 0.0

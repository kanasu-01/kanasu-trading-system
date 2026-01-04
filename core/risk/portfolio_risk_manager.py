from typing import List


class PortfolioRiskManager:
    """
    Portfolio-level risk control.
    STEP 7.3: Limits total open risk across all positions.
    """

    def __init__(
        self,
        max_total_risk_pct: float = 5.0,
        max_open_trades: int = 5,
    ):
        """
        :param max_total_risk_pct: Max % of capital allowed at risk across portfolio
        :param max_open_trades: Max simultaneous open positions
        """
        self.max_total_risk_pct = max_total_risk_pct
        self.max_open_trades = max_open_trades

    def can_open_new_trade(
        self,
        open_trade_risks_pct: List[float],
        new_trade_risk_pct: float,
    ) -> bool:
        """
        Decide whether a new trade can be opened.
        """

        if len(open_trade_risks_pct) >= self.max_open_trades:
            return False

        current_risk = sum(open_trade_risks_pct)
        projected_risk = current_risk + new_trade_risk_pct

        if projected_risk > self.max_total_risk_pct:
            return False

        return True

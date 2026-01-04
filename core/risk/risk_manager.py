from typing import Optional


class RiskManager:
    """
    Fixed-fractional risk management.
    STEP 7.1: Converts trade signals into position size.
    """

    def __init__(
        self,
        account_capital: float,
        risk_per_trade_pct: float = 1.0,
        max_position_pct: float = 20.0,
    ):
        """
        :param account_capital: Total trading capital
        :param risk_per_trade_pct: % of capital to risk per trade
        :param max_position_pct: Max capital allowed in a single position
        """
        self.account_capital = account_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_pct = max_position_pct

    def calculate_position_size(
        self,
        entry_price: float,
        stop_price: float,
    ) -> Optional[int]:
        """
        Returns quantity to trade based on risk.
        """

        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share <= 0:
            return None

        capital_at_risk = (
            self.account_capital * self.risk_per_trade_pct / 100
        )

        raw_quantity = capital_at_risk / risk_per_share

        # Enforce max position size cap
        max_position_value = (
            self.account_capital * self.max_position_pct / 100
        )
        max_quantity = max_position_value / entry_price

        quantity = int(min(raw_quantity, max_quantity))

        if quantity <= 0:
            return None

        return quantity

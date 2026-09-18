from math import floor, isfinite
from typing import Optional


class RiskManager:
    """
    Fixed-fractional risk management with an explicit current-equity path.

    ``calculate_position_size`` retains fixed-capital legacy compatibility;
    canonical Backtests use ``calculate_position_size_for_equity``.
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
        if not isfinite(account_capital) or account_capital <= 0:
            raise ValueError("account_capital must be finite and positive")
        if not isfinite(risk_per_trade_pct) or risk_per_trade_pct <= 0:
            raise ValueError("risk_per_trade_pct must be finite and positive")
        if not isfinite(max_position_pct) or max_position_pct <= 0:
            raise ValueError("max_position_pct must be finite and positive")

        self.account_capital = account_capital
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_pct = max_position_pct

    def calculate_position_size_for_equity(
        self,
        *,
        account_equity: float,
        entry_price: float,
        stop_price: float,
    ) -> Optional[int]:
        """Return long quantity using authoritative current account equity."""

        if not isfinite(account_equity):
            raise ValueError("account_equity must be finite")
        if not isfinite(entry_price):
            raise ValueError("entry_price must be finite")
        if not isfinite(stop_price):
            raise ValueError("stop_price must be finite")

        if account_equity <= 0 or entry_price <= 0 or stop_price <= 0:
            return None

        price_risk_per_share = entry_price - stop_price
        if price_risk_per_share <= 0:
            return None

        risk_budget = account_equity * self.risk_per_trade_pct / 100
        risk_quantity = floor(risk_budget / price_risk_per_share)

        max_position_notional = account_equity * self.max_position_pct / 100
        max_position_quantity = floor(max_position_notional / entry_price)

        quantity = min(risk_quantity, max_position_quantity)
        return quantity if quantity >= 1 else None

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

from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerageResult:

    brokerage: float
    taxes: float
    total_cost: float


class BrokerageModel:
    """
    Simplified brokerage + tax calculator.

    MVP implementation.
    """

    def __init__(
        self,
        brokerage_rate: float = 0.0003,
        brokerage_cap: float = 20.0,
        tax_rate: float = 0.0005,
        rounding_digits: int = 2,
    ):
        self.brokerage_rate = brokerage_rate
        self.brokerage_cap = brokerage_cap
        self.tax_rate = tax_rate
        self.rounding_digits = rounding_digits

    def calculate(
        self,
        turnover: float,
    ) -> BrokerageResult:

        # -----------------------------------------
        # Brokerage
        # -----------------------------------------

        brokerage = min(
            turnover * self.brokerage_rate,
            self.brokerage_cap,
        )

        # -----------------------------------------
        # Taxes / charges (simplified)
        # -----------------------------------------

        taxes = turnover * self.tax_rate

        total_cost = brokerage + taxes

        return BrokerageResult(
            brokerage=round(brokerage, self.rounding_digits),
            taxes=round(taxes, self.rounding_digits),
            total_cost=round(total_cost, self.rounding_digits),
        )

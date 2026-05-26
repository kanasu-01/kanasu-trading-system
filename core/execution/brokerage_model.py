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

    def calculate(
        self,
        turnover: float,
    ) -> BrokerageResult:

        # -----------------------------------------
        # Brokerage
        # -----------------------------------------

        brokerage = min(
            turnover * 0.0003,
            20,
        )

        # -----------------------------------------
        # Taxes / charges (simplified)
        # -----------------------------------------

        taxes = turnover * 0.0005

        total_cost = brokerage + taxes

        return BrokerageResult(
            brokerage=round(brokerage, 2),
            taxes=round(taxes, 2),
            total_cost=round(total_cost, 2),
        )

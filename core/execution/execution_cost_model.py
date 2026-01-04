class ExecutionCostModel:
    """
    Slippage + transaction cost model.
    STEP 8.7: Adjust execution prices to reflect reality.
    """

    def __init__(
        self,
        slippage_pct: float = 0.05,
        brokerage_pct: float = 0.01,
    ):
        self.slippage_pct = slippage_pct
        self.brokerage_pct = brokerage_pct

    def apply_buy_costs(self, price: float) -> float:
        price *= (1 + self.slippage_pct / 100)
        price *= (1 + self.brokerage_pct / 100)
        return round(price, 2)

    def apply_sell_costs(self, price: float) -> float:
        price *= (1 - self.slippage_pct / 100)
        price *= (1 - self.brokerage_pct / 100)
        return round(price, 2)

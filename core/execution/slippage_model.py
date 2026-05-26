class SlippageModel:
    """
    Simplified deterministic slippage model.

    Applies configurable execution degradation.
    """

    def __init__(
        self,
        slippage_pct: float = 0.0005,
    ):
        self.slippage_pct = slippage_pct

    # -----------------------------------------
    # Buy slippage
    # -----------------------------------------

    def apply_buy_slippage(
        self,
        price: float,
    ) -> float:

        return price * (1 + self.slippage_pct)

    # -----------------------------------------
    # Sell slippage
    # -----------------------------------------

    def apply_sell_slippage(
        self,
        price: float,
    ) -> float:

        return price * (1 - self.slippage_pct)

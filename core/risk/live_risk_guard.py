class LiveRiskGuard:
    """
    Pre-trade live risk validation.
    """

    def __init__(self, min_required_balance: float):
        self.min_required_balance = min_required_balance

    def validate(self, broker) -> bool:
        try:
            balance = broker.get_account_balance()
        except Exception:
            return False

        return balance >= self.min_required_balance

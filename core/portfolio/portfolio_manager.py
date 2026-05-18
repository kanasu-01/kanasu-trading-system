from dataclasses import dataclass


@dataclass
class PortfolioState:
    cash: float
    position_size: float
    equity: float
    peak_equity: float
    drawdown: float


class PortfolioManager:

    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital

        self.cash = initial_capital

        self.equity = initial_capital
        self.peak_equity = initial_capital
        self.drawdown = 0.0

    # -------------------------------------
    # Trade execution
    # -------------------------------------

    # -------------------------------------
    # Portfolio valuation
    # -------------------------------------

    def update_equity(self, cash: float, position_size: int, current_price: float):

        position_value = position_size * current_price

        self.cash = cash
        self.equity = cash + position_value

        self.peak_equity = max(self.peak_equity, self.equity)

        if self.peak_equity > 0:
            self.drawdown = (self.equity - self.peak_equity) / self.peak_equity

    # -------------------------------------
    # Snapshot
    # -------------------------------------

    def snapshot(self) -> PortfolioState:

        return PortfolioState(
            cash=self.cash,
            position_size=0,
            equity=self.equity,
            peak_equity=self.peak_equity,
            drawdown=self.drawdown,
        )

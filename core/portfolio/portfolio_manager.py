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
        self.position_size = 0
        self.entry_price = None

        self.equity = initial_capital
        self.peak_equity = initial_capital
        self.drawdown = 0.0

    # -------------------------------------
    # Trade execution
    # -------------------------------------

    def enter_long(self, price: float):

        if self.position_size == 0:
            self.position_size = 1
            self.entry_price = price
            self.cash -= price

    def exit_long(self, price: float):

        if self.position_size > 0:
            self.cash += price * self.position_size
            self.position_size = 0
            self.entry_price = None

    # -------------------------------------
    # Portfolio valuation
    # -------------------------------------

    def update_equity(self, price: float):

        position_value = self.position_size * price

        self.equity = self.cash + position_value

        self.peak_equity = max(self.peak_equity, self.equity)

        if self.peak_equity > 0:
            self.drawdown = (
                self.equity - self.peak_equity
            ) / self.peak_equity

    # -------------------------------------
    # Snapshot
    # -------------------------------------

    def snapshot(self) -> PortfolioState:

        return PortfolioState(
            cash=self.cash,
            position_size=self.position_size,
            equity=self.equity,
            peak_equity=self.peak_equity,
            drawdown=self.drawdown,
        )
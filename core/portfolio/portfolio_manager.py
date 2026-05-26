from dataclasses import dataclass
from core.portfolio.pnl_snapshot import (
    PnLSnapshot,
)
from core.portfolio.position_book import (
    PositionBook,
)

from core.entities.position import Position


@dataclass
class PortfolioState:
    cash: float
    position_size: float
    equity: float

    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float

    peak_equity: float
    drawdown: float


class PortfolioManager:

    def __init__(self, initial_capital: float = 100000):
        self.initial_capital = initial_capital

        self.cash = initial_capital
        self.position_size = 0

        self.realized_pnl = 0.0

        self.unrealized_pnl = 0.0

        self.total_pnl = 0.0

        self.equity = initial_capital
        self.peak_equity = initial_capital
        self.drawdown = 0.0
        self.position_book = PositionBook()

    # -------------------------------------
    # Trade execution
    # -------------------------------------

    def add_position(
        self,
        symbol: str,
        position: Position,
    ) -> None:
        """
        Register active portfolio position.
        """

        self.position_book.add_position(
            symbol=symbol,
            position=position,
        )

    def remove_position(
        self,
        symbol: str,
    ) -> None:
        """
        Remove active portfolio position.
        """

        self.position_book.remove_position(
            symbol=symbol,
        )

    def active_positions(self) -> int:
        """
        Number of active portfolio positions.
        """

        return self.position_book.active_count()

    # -------------------------------------
    # Portfolio valuation
    # -------------------------------------

    def record_realized_pnl(
        self,
        pnl: float,
    ) -> None:
        """
        Record realized pnl from closed trades.
        """

        self.realized_pnl += pnl

        self.total_pnl = self.realized_pnl + self.unrealized_pnl

    def update_equity(self, cash: float, position_size: int, current_price: float):

        position_value = position_size * current_price
        self.cash = cash
        self.position_size = position_size
        self.equity = cash + position_value

        self.unrealized_pnl = self.equity - self.initial_capital

        self.total_pnl = self.realized_pnl + self.unrealized_pnl

        self.peak_equity = max(self.peak_equity, self.equity)

        if self.peak_equity > 0:
            self.drawdown = (self.equity - self.peak_equity) / self.peak_equity

    # -------------------------------------
    # Snapshot
    # -------------------------------------

    def snapshot(self) -> PortfolioState:

        return PortfolioState(
            cash=self.cash,
            position_size=self.position_size,
            equity=self.equity,
            realized_pnl=self.realized_pnl,
            unrealized_pnl=self.unrealized_pnl,
            total_pnl=self.total_pnl,
            peak_equity=self.peak_equity,
            drawdown=self.drawdown,
        )

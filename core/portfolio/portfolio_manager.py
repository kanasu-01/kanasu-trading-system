from dataclasses import dataclass
from math import isfinite
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
    position_value: float
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
        self.position_value = 0.0

        self.realized_pnl = 0.0

        self.unrealized_pnl = 0.0

        self.total_pnl = 0.0

        self.equity = initial_capital
        self.peak_equity = initial_capital
        self.drawdown = 0.0
        self.position_book = PositionBook()
        self._mark_prices: dict[str, float] = {}

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

    def open_position(self, position: Position) -> None:
        """Open and account for a long position."""

        if position.direction != "LONG":
            raise ValueError("Only long positions are supported")

        if self.position_book.get_position(position.symbol) is not None:
            raise ValueError(f"Position already open for {position.symbol}")

        required_cash = (
            position.entry_price * position.quantity
            + position.entry_transaction_cost
        )
        if not isfinite(self.cash) or not isfinite(required_cash):
            raise ValueError("authoritative cash and entry requirement must be finite")
        if required_cash > self.cash:
            raise ValueError("Insufficient cash to open long position")

        self.cash -= required_cash
        self.position_book.add_position(
            symbol=position.symbol,
            position=position,
        )
        self._mark_prices[position.symbol] = position.entry_price
        self._recalculate_accounting()

    def mark_to_market(self, prices: dict[str, float]) -> None:
        """Mark open positions using the supplied symbol prices."""

        for symbol, price in prices.items():
            if self.position_book.get_position(symbol) is not None:
                self._mark_prices[symbol] = price

        self._recalculate_accounting()

    def close_position(
        self,
        symbol: str,
        exit_price: float,
        exit_transaction_cost: float,
    ) -> None:
        """Close and account for a long position."""

        position = self.position_book.get_position(symbol)
        if position is None:
            raise ValueError(f"No open position for {symbol}")

        if position.direction != "LONG":
            raise ValueError("Only long positions are supported")

        self.cash += exit_price * position.quantity - exit_transaction_cost
        self.realized_pnl += (
            (exit_price - position.entry_price) * position.quantity
            - position.entry_transaction_cost
            - exit_transaction_cost
        )
        self.position_book.remove_position(symbol)
        self._mark_prices.pop(symbol, None)
        self._recalculate_accounting()

    def _recalculate_accounting(self) -> None:
        self.position_size = sum(
            position.quantity
            for position in self.position_book.positions.values()
        )
        self.position_value = sum(
            self._mark_prices.get(symbol, position.entry_price)
            * position.quantity
            for symbol, position in self.position_book.positions.items()
        )
        self.equity = self.cash + self.position_value
        self.total_pnl = self.equity - self.initial_capital
        self.unrealized_pnl = self.total_pnl - self.realized_pnl

        self.peak_equity = max(self.peak_equity, self.equity)

        if self.peak_equity > 0:
            self.drawdown = (self.equity - self.peak_equity) / self.peak_equity

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

        self.cash = cash
        self.position_size = position_size
        self.position_value = position_size * current_price
        self.equity = cash + self.position_value

        self.total_pnl = self.equity - self.initial_capital
        self.unrealized_pnl = self.total_pnl - self.realized_pnl

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
            position_value=self.position_value,
            equity=self.equity,
            realized_pnl=self.realized_pnl,
            unrealized_pnl=self.unrealized_pnl,
            total_pnl=self.total_pnl,
            peak_equity=self.peak_equity,
            drawdown=self.drawdown,
        )

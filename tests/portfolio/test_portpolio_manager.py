from datetime import datetime

import pytest

from core.entities.position import Position
from core.portfolio.portfolio_manager import (
    PortfolioManager,
)


def test_portfolio_equity_updates():

    portfolio = PortfolioManager(initial_capital=100000)

    portfolio.update_equity(
        cash=80000,
        position_size=100,
        current_price=250,
    )

    state = portfolio.snapshot()

    assert state.equity == 105000

    assert state.cash == 80000

    assert state.position_size == 100


def test_portfolio_accounts_for_complete_buy_mark_sell_lifecycle():
    initial_capital = 100000
    portfolio = PortfolioManager(initial_capital=initial_capital)
    position = Position(
        symbol="RELIANCE",
        entry_time=datetime(2026, 1, 2, 9, 15),
        entry_price=100,
        entry_transaction_cost=2,
        quantity=10,
        stop_price=90,
        direction="LONG",
        entry_index=0,
    )

    portfolio.open_position(position)

    entry_state = portfolio.snapshot()
    assert entry_state.cash == 98998

    portfolio.mark_to_market({"RELIANCE": 110})

    marked_state = portfolio.snapshot()
    assert marked_state.position_size == 10
    assert marked_state.position_value == 1100
    assert marked_state.equity == 100098
    assert marked_state.unrealized_pnl == 98
    assert marked_state.equity == marked_state.cash + marked_state.position_value
    assert marked_state.total_pnl == marked_state.equity - initial_capital
    assert marked_state.total_pnl == (
        marked_state.realized_pnl + marked_state.unrealized_pnl
    )

    portfolio.close_position(
        symbol="RELIANCE",
        exit_price=110,
        exit_transaction_cost=3,
    )

    final_state = portfolio.snapshot()
    assert final_state.cash == 100095
    assert final_state.position_size == 0
    assert final_state.position_value == 0
    assert final_state.equity == 100095
    assert final_state.realized_pnl == 95
    assert final_state.unrealized_pnl == 0
    assert final_state.total_pnl == 95
    assert portfolio.active_positions() == 0
    assert final_state.equity == final_state.cash + final_state.position_value
    assert final_state.total_pnl == final_state.equity - initial_capital
    assert final_state.total_pnl == (
        final_state.realized_pnl + final_state.unrealized_pnl
    )


def test_direct_unaffordable_long_open_is_rejected_without_mutation():
    portfolio = PortfolioManager(initial_capital=100)
    position = Position(
        symbol="RELIANCE",
        entry_time=datetime(2026, 1, 2, 9, 15),
        entry_price=100,
        entry_transaction_cost=0.08,
        quantity=1,
        stop_price=90,
        direction="LONG",
        entry_index=0,
    )
    before = portfolio.snapshot()

    with pytest.raises(ValueError, match="Insufficient cash"):
        portfolio.open_position(position)

    assert portfolio.snapshot() == before
    assert portfolio.active_positions() == 0


def test_direct_exactly_affordable_long_open_cannot_create_negative_cash():
    portfolio = PortfolioManager(initial_capital=100.08)
    position = Position(
        symbol="RELIANCE",
        entry_time=datetime(2026, 1, 2, 9, 15),
        entry_price=100,
        entry_transaction_cost=0.08,
        quantity=1,
        stop_price=90,
        direction="LONG",
        entry_index=0,
    )

    portfolio.open_position(position)

    assert portfolio.cash == pytest.approx(0.0)
    assert portfolio.cash >= 0.0

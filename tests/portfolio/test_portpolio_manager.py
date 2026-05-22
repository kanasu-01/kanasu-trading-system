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

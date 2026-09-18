import pytest

from core.risk.risk_manager import RiskManager


@pytest.mark.parametrize(
    ("equity", "expected_quantity"),
    [(100_000.0, 100), (110_000.0, 110), (90_000.0, 90), (50_000.0, 50)],
)
def test_current_equity_sizing_uses_authoritative_equity(
    equity: float,
    expected_quantity: int,
) -> None:
    manager = RiskManager(account_capital=100_000.0, risk_per_trade_pct=1.0)

    quantity = manager.calculate_position_size_for_equity(
        account_equity=equity,
        entry_price=100.0,
        stop_price=90.0,
    )

    assert quantity == expected_quantity


def test_max_position_cap_uses_current_equity() -> None:
    manager = RiskManager(
        account_capital=100_000.0,
        risk_per_trade_pct=50.0,
        max_position_pct=10.0,
    )

    quantity = manager.calculate_position_size_for_equity(
        account_equity=50_000.0,
        entry_price=100.0,
        stop_price=99.0,
    )

    assert quantity == 50


@pytest.mark.parametrize("equity", [0.0, -1.0])
def test_non_positive_equity_produces_no_quantity(equity: float) -> None:
    manager = RiskManager(account_capital=100_000.0)

    assert manager.calculate_position_size_for_equity(
        account_equity=equity,
        entry_price=100.0,
        stop_price=90.0,
    ) is None


@pytest.mark.parametrize("equity", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_equity_fails_explicitly(equity: float) -> None:
    manager = RiskManager(account_capital=100_000.0)

    with pytest.raises(ValueError, match="account_equity must be finite"):
        manager.calculate_position_size_for_equity(
            account_equity=equity,
            entry_price=100.0,
            stop_price=90.0,
        )


@pytest.mark.parametrize("stop_price", [0.0, -1.0, 100.0, 101.0])
def test_invalid_long_stop_produces_no_quantity(stop_price: float) -> None:
    manager = RiskManager(account_capital=100_000.0)

    assert manager.calculate_position_size_for_equity(
        account_equity=100_000.0,
        entry_price=100.0,
        stop_price=stop_price,
    ) is None


@pytest.mark.parametrize("stop_price", [float("nan"), float("inf")])
def test_non_finite_stop_fails_explicitly(stop_price: float) -> None:
    manager = RiskManager(account_capital=100_000.0)

    with pytest.raises(ValueError, match="stop_price must be finite"):
        manager.calculate_position_size_for_equity(
            account_equity=100_000.0,
            entry_price=100.0,
            stop_price=stop_price,
        )


@pytest.mark.parametrize(
    ("keyword", "value"),
    [
        ("risk_per_trade_pct", 0.0),
        ("risk_per_trade_pct", float("nan")),
        ("max_position_pct", 0.0),
        ("max_position_pct", float("inf")),
    ],
)
def test_invalid_risk_configuration_fails_explicitly(
    keyword: str,
    value: float,
) -> None:
    arguments = {
        "account_capital": 100_000.0,
        "risk_per_trade_pct": 1.0,
        "max_position_pct": 20.0,
    }
    arguments[keyword] = value

    with pytest.raises(ValueError):
        RiskManager(**arguments)


def test_max_position_percentage_above_one_hundred_is_allowed() -> None:
    manager = RiskManager(
        account_capital=100_000.0,
        risk_per_trade_pct=1.0,
        max_position_pct=150.0,
    )

    assert manager.calculate_position_size_for_equity(
        account_equity=100_000.0,
        entry_price=100.0,
        stop_price=90.0,
    ) == 100


def test_legacy_fixed_capital_sizing_remains_available() -> None:
    manager = RiskManager(account_capital=100_000.0, risk_per_trade_pct=1.0)

    assert manager.calculate_position_size(entry_price=100.0, stop_price=90.0) == 100

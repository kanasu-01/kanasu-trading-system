from datetime import datetime

from core.entities.trade import Trade
from core.walk_forward.metrics import WalkForwardMetrics


def test_wfa_window_metrics_retain_legacy_trade_only_contract() -> None:
    trade = Trade(
        symbol="TEST",
        entry_time=datetime(2026, 1, 2, 9, 15),
        entry_price=100.0,
        exit_time=datetime(2026, 1, 2, 9, 30),
        exit_price=110.0,
        stop_price=98.0,
        quantity=10,
        direction="LONG",
        exit_reason="STRATEGY_EXIT",
        pnl=100.0,
        gross_pnl=100.0,
        transaction_cost=0.0,
        pnl_pct=10.0,
    )

    metrics = WalkForwardMetrics().compute([trade])

    assert metrics["total_trades"] == 1
    assert metrics["expectancy_pct"] == 10.0
    assert metrics["max_drawdown_pct"] == 0.0
    assert metrics["profitable"] is True
    assert "account_return_pct" not in metrics
    assert "max_equity_drawdown_pct" not in metrics

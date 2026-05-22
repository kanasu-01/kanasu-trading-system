from datetime import datetime

from core.backtest.backtest_result import (
    BacktestResult,
)

from core.backtest.bar_record import (
    BarRecord,
)


def test_equity_curve_derivation():

    records = [
        BarRecord(
            timestamp=datetime(2020, 1, 1),
            open=100,
            high=101,
            low=99,
            close=100,
            volume=1000,
            signal=None,
            strategy="test",
            state=None,
            decision_snapshot={},
            execution_event=None,
            execution_price=None,
            execution_quantity=None,
            equity=100000,
            cash=100000,
            position_size=0,
            drawdown=0,
        ),
        BarRecord(
            timestamp=datetime(2020, 1, 2),
            open=101,
            high=102,
            low=100,
            close=101,
            volume=1000,
            signal=None,
            strategy="test",
            state=None,
            decision_snapshot={},
            execution_event=None,
            execution_price=None,
            execution_quantity=None,
            equity=101000,
            cash=101000,
            position_size=0,
            drawdown=0,
        ),
    ]

    result = BacktestResult(
        trades=[],
        bar_records=records,
        session_id="test",
    )

    curve = result.equity_curve

    assert len(curve) == 2

    assert curve[0][1] == 100000

    assert curve[1][1] == 101000

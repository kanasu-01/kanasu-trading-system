from datetime import datetime

import pytest

from core.execution.trade_execution_engine import (
    TradeExecutionEngine,
)
from core.runtime.runtime_context import (
    RuntimeContext,
)

from core.strategies.sma_crossover_strategy import (
    SMACrossOverStrategy,
)

from core.entities.candle import Candle

from core.strategies.signal import SignalType

from core.entities.candle_series import (
    CandleSeries,
)


def build_candle(price: float) -> Candle:

    return Candle(
        timestamp=datetime.now(),
        open=price,
        high=price + 1,
        low=price - 1,
        close=price,
        volume=1000,
    )


def test_execution_engine_creates_trade():

    strategy = SMACrossOverStrategy()

    engine = TradeExecutionEngine(
        strategy=strategy,
        account_capital=100000,
        session_id="test",
        runtime_context=RuntimeContext(),
    )

    candle = build_candle(100)

    series = CandleSeries([])

    engine.on_signal(
        signal=SignalType.BUY,
        candle=candle,
        series=series,
        symbol="TEST",
    )

    runtime_position = engine.get_runtime_position(
        symbol="TEST",
    )

    assert runtime_position is not None

    assert runtime_position.entry_price > 0

    open_state = engine.portfolio_manager.snapshot()

    assert open_state.cash < 100000
    assert open_state.equity == open_state.cash + open_state.position_value
    assert open_state.total_pnl == (
        open_state.realized_pnl + open_state.unrealized_pnl
    )

    exit_candle = build_candle(110)

    engine.on_signal(
        signal=SignalType.SELL,
        candle=exit_candle,
        series=series,
        symbol="TEST",
    )

    assert engine.get_runtime_position(symbol="TEST") is None
    assert len(engine.completed_trades) == 1

    completed_trade = engine.completed_trades[0]
    closed_state = engine.portfolio_manager.snapshot()

    assert closed_state.position_size == 0
    assert closed_state.position_value == 0
    assert closed_state.cash == pytest.approx(100000 + completed_trade.pnl)
    assert closed_state.equity == closed_state.cash
    assert closed_state.realized_pnl == pytest.approx(completed_trade.pnl)
    assert closed_state.total_pnl == pytest.approx(completed_trade.pnl)
    assert closed_state.unrealized_pnl == pytest.approx(0, abs=1e-9)

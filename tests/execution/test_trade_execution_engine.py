from datetime import datetime

import pytest

from core.execution.trade_execution_engine import (
    TradeExecutionEngine,
)
from core.execution.brokerage_model import BrokerageModel
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


def build_fixed_candle(
    *,
    minute: int,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    return Candle(
        timestamp=datetime(2026, 1, 2, 9, minute),
        open=open_price,
        high=high,
        low=low,
        close=close,
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


def test_buy_candle_low_does_not_stop_new_position():
    engine = TradeExecutionEngine(
        strategy=SMACrossOverStrategy(),
        account_capital=100000,
        session_id="same_bar_stop_causality",
        runtime_context=RuntimeContext(),
    )
    buy_candle = build_fixed_candle(
        minute=15,
        open_price=100,
        high=101,
        low=97,
        close=100,
    )

    engine.on_signal(
        signal=SignalType.BUY,
        candle=buy_candle,
        series=CandleSeries([]),
        symbol="TEST",
    )

    assert engine.get_runtime_position(symbol="TEST") is not None
    assert engine.completed_trades == []
    assert engine.last_execution_event == "BUY"


def test_subsequent_candle_low_stops_existing_position():
    engine = TradeExecutionEngine(
        strategy=SMACrossOverStrategy(),
        account_capital=100000,
        session_id="subsequent_bar_stop",
        runtime_context=RuntimeContext(),
    )
    series = CandleSeries([])
    buy_candle = build_fixed_candle(
        minute=15,
        open_price=100,
        high=101,
        low=97,
        close=100,
    )

    engine.on_signal(
        signal=SignalType.BUY,
        candle=buy_candle,
        series=series,
        symbol="TEST",
    )

    assert engine.get_runtime_position(symbol="TEST") is not None
    assert engine.completed_trades == []

    stop_candle = build_fixed_candle(
        minute=30,
        open_price=100,
        high=101,
        low=97,
        close=99,
    )

    engine.on_signal(
        signal=None,
        candle=stop_candle,
        series=series,
        symbol="TEST",
    )

    assert engine.get_runtime_position(symbol="TEST") is None
    assert len(engine.completed_trades) == 1
    assert engine.completed_trades[0].exit_reason == "STOP_LOSS"
    assert engine.last_execution_event == "STOP_EXIT"


def test_slippage_is_applied_once_and_brokerage_remains_explicit():
    runtime_context = RuntimeContext()
    engine = TradeExecutionEngine(
        strategy=SMACrossOverStrategy(),
        account_capital=100000,
        session_id="single_slippage",
        runtime_context=runtime_context,
    )
    series = CandleSeries([])
    buy_reference_price = 100
    sell_reference_price = 110
    slippage_pct = runtime_context.execution_config.slippage_pct
    expected_entry_fill = buy_reference_price * (1 + slippage_pct)
    expected_exit_fill = sell_reference_price * (1 - slippage_pct)

    engine.on_signal(
        signal=SignalType.BUY,
        candle=build_fixed_candle(
            minute=15,
            open_price=100,
            high=101,
            low=99,
            close=buy_reference_price,
        ),
        series=series,
        symbol="TEST",
    )

    position = engine.get_runtime_position(symbol="TEST")
    assert position is not None

    engine.on_signal(
        signal=SignalType.SELL,
        candle=build_fixed_candle(
            minute=30,
            open_price=110,
            high=111,
            low=109,
            close=sell_reference_price,
        ),
        series=series,
        symbol="TEST",
    )

    assert len(engine.completed_trades) == 1
    completed_trade = engine.completed_trades[0]
    brokerage_model = BrokerageModel()
    expected_entry_cost = brokerage_model.calculate(
        turnover=expected_entry_fill * position.quantity
    ).total_cost
    expected_exit_cost = brokerage_model.calculate(
        turnover=expected_exit_fill * position.quantity
    ).total_cost

    assert position.entry_price == pytest.approx(expected_entry_fill)
    assert completed_trade.exit_price == pytest.approx(expected_exit_fill)
    assert position.entry_transaction_cost == pytest.approx(expected_entry_cost)
    assert completed_trade.transaction_cost == pytest.approx(
        expected_entry_cost + expected_exit_cost
    )

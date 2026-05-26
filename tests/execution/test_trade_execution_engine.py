from datetime import datetime

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

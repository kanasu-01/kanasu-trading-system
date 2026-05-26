from datetime import datetime, timedelta

from core.entities.candle import Candle

from core.backtest.backtest_engine import (
    BacktestEngine,
)
from core.runtime.runtime_context import (
    RuntimeContext,
)
from core.runtime.dataset_context import (
    DatasetContext,
)

from core.strategies.sma_crossover_strategy import (
    SMACrossOverStrategy,
)


def build_dummy_candles(count: int):

    candles = []

    base_time = datetime(2020, 1, 1)

    price = 100

    for i in range(count):

        if i % 20 < 10:
            price += 2
        else:
            price -= 2

        candles.append(
            Candle(
                timestamp=(base_time + timedelta(minutes=i)),
                open=price,
                high=price + 1,
                low=price - 1,
                close=price,
                volume=1000,
            )
        )

    return candles


def test_backtest_engine_executes_successfully():

    candles = build_dummy_candles(500)

    strategy = SMACrossOverStrategy(
        params={
            "fast_period": 10,
            "slow_period": 30,
        }
    )

    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=100000,
        runtime_context=RuntimeContext(),
        dataset_context=DatasetContext(symbol="Test"),
    )

    result = engine.run(candles)

    assert result is not None

    assert result.session_id is not None

    assert result.bar_records is not None

    assert len(result.bar_records) > 0

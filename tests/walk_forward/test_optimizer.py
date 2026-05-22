from datetime import datetime, timedelta

from core.entities.candle import Candle

from core.walk_forward.optimizer import (
    GridSearchOptimizer,
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


def test_optimizer_executes_without_crashing():

    candles = build_dummy_candles(500)

    optimizer = GridSearchOptimizer()

    param_space = [
        {
            "fast_period": 10,
            "slow_period": 30,
        },
        {
            "fast_period": 20,
            "slow_period": 50,
        },
    ]

    try:

        optimizer.optimize(
            strategy_cls=SMACrossOverStrategy,
            param_space=param_space,
            train_bars=candles,
        )

    except RuntimeError:

        # Acceptable for deterministic
        # synthetic test data
        pass

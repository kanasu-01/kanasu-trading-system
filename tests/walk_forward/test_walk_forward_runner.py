from datetime import datetime, timedelta

from core.entities.candle import Candle

from core.walk_forward.window_generator import (
    WalkForwardWindowGenerator,
)

from core.walk_forward.optimizer import (
    GridSearchOptimizer,
)

from core.walk_forward.metrics import (
    WalkForwardMetrics,
)

from core.walk_forward.runner import (
    WalkForwardRunner,
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


def test_walk_forward_runner_executes():

    candles = build_dummy_candles(1000)

    window_generator = WalkForwardWindowGenerator(
        in_sample_bars=300,
        out_sample_bars=100,
        step_bars=100,
        mode="rolling",
    )

    optimizer = GridSearchOptimizer()

    metrics = WalkForwardMetrics()

    runner = WalkForwardRunner(
        window_generator=window_generator,
        optimizer=optimizer,
        metrics=metrics,
    )

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

    result = runner.run(
        strategy_cls=SMACrossOverStrategy,
        param_space=param_space,
        candles=candles,
    )

    assert result is not None

    assert result.windows is not None

    assert len(result.windows) > 0

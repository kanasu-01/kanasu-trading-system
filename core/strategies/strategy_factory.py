from core.strategies.base_strategy import BaseStrategy
from core.strategies.sma_crossover_strategy import (
    SMACrossOverStrategy,
)
from core.strategies.pivotboss_swing_strategy import (
    PivotBossSwingStrategy,
)

from core.config.backtest_config import (
    BacktestConfig,
)


def create_strategy(
    config: BacktestConfig,
) -> BaseStrategy:

    if config.strategy_name == "sma_crossover":

        return SMACrossOverStrategy(
            params=config.strategy_params
        )

    elif config.strategy_name == "pivotboss":

        return PivotBossSwingStrategy()

    raise ValueError(
        f"Unsupported strategy: "
        f"{config.strategy_name}"
    )
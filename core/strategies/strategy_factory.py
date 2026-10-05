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


_RESEARCH_PROCEDURE_STRATEGY_CLASSES = {
    "sma-crossover-v1": SMACrossOverStrategy,
}


def get_research_procedure_strategy_class(
    procedure_id: str,
) -> type[BaseStrategy] | None:
    """Resolve one explicitly accepted registered procedure implementation."""

    if not isinstance(procedure_id, str):
        raise TypeError(
            "procedure_id must be a string"
        )

    if not procedure_id:
        raise ValueError(
            "procedure_id must be non-empty"
        )

    return _RESEARCH_PROCEDURE_STRATEGY_CLASSES.get(
        procedure_id
    )


def create_strategy(
    config: BacktestConfig,
) -> BaseStrategy:

    if config.strategy_name == "sma_crossover":

        return SMACrossOverStrategy(params=config.strategy_params)

    elif config.strategy_name == "pivotboss":

        return PivotBossSwingStrategy()

    raise ValueError(f"Unsupported strategy: " f"{config.strategy_name}")


def get_strategy_class(
    config: BacktestConfig,
):

    if config.strategy_name == "sma_crossover":

        return SMACrossOverStrategy

    elif config.strategy_name == "pivotboss":

        return PivotBossSwingStrategy

    raise ValueError(f"Unsupported strategy: " f"{config.strategy_name}")

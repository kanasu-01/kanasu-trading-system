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


def create_registered_research_strategy(
    procedure_id: str,
    config: BacktestConfig,
) -> BaseStrategy:
    """Construct one canonical strategy for registered research execution."""

    expected_strategy_class = (
        get_research_procedure_strategy_class(
            procedure_id
        )
    )

    if expected_strategy_class is None:
        raise ValueError(
            "registered strategy procedure is unverifiable "
            "from canonical executable authority"
        )

    configured_strategy_class = (
        get_strategy_class(
            config
        )
    )

    if (
        configured_strategy_class
        is not expected_strategy_class
    ):
        raise ValueError(
            "Backtest strategy configuration does not match "
            "the registered procedure"
        )

    strategy = create_strategy(
        config
    )

    if type(strategy) is not expected_strategy_class:
        raise RuntimeError(
            "canonical registered strategy construction "
            "returned an unexpected implementation"
        )

    return strategy

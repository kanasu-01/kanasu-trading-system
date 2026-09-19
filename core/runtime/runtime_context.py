from dataclasses import dataclass

from core.config.execution_config import (
    ExecutionConfig,
    EXECUTION_CONFIG,
)
from core.config.backtest_economic_policy import (
    BacktestEconomicPolicy,
    BACKTEST_ECONOMIC_POLICY,
)


@dataclass(frozen=True)
class RuntimeContext:
    """
    Runtime-scoped configuration bundle.

    Future:
    - broker config
    - data config
    - execution config
    - risk config
    - feature flags
    """

    execution_config: ExecutionConfig = EXECUTION_CONFIG
    risk_per_trade_pct: float = 1.0
    economic_policy: BacktestEconomicPolicy = BACKTEST_ECONOMIC_POLICY

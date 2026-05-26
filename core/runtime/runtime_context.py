from dataclasses import dataclass

from core.config.execution_config import (
    ExecutionConfig,
    EXECUTION_CONFIG,
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

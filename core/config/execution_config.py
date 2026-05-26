from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutionConfig:

    slippage_pct: float = 0.0005

    brokerage_enabled: bool = True

    slippage_enabled: bool = True


EXECUTION_CONFIG = ExecutionConfig()

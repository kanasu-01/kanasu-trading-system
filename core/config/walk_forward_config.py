from dataclasses import dataclass
from typing import (
    List,
    Dict,
    Any,
    Literal,
)


@dataclass(frozen=True)
class WalkForwardConfig:

    # -----------------------------------------
    # Windowing
    # -----------------------------------------

    in_sample_bars: int

    out_sample_bars: int

    step_bars: int

    mode: Literal[
        "rolling",
        "expanding",
    ]

    # -----------------------------------------
    # Optimization
    # -----------------------------------------

    param_space: List[Dict[str, Any]]


WALK_FORWARD_CONFIG = WalkForwardConfig(
    # -----------------------------------------
    # Windowing
    # -----------------------------------------
    in_sample_bars=300,
    out_sample_bars=150,
    step_bars=150,
    mode="rolling",
    # -----------------------------------------
    # Optimization
    # -----------------------------------------
    param_space=[
        {"fast_period": 10, "slow_period": 30},
        {"fast_period": 10, "slow_period": 50},
        {"fast_period": 20, "slow_period": 50},
        {"fast_period": 20, "slow_period": 100},
        {"fast_period": 30, "slow_period": 100},
    ],
)

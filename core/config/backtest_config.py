from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class BacktestConfig:
    symbol: str
    timeframe: str

    strategy_name: str

    start: datetime
    end: datetime

    initial_capital: float

    enable_replay: bool
    enable_visualization: bool
    enable_exports: bool

    strategy_params: dict = field(default_factory=dict)


BACKTEST_CONFIG = BacktestConfig(
    symbol="RELIANCE",
    timeframe="15m",
    strategy_name="sma_crossover",
    start=datetime(2024, 1, 2),
    end=datetime(2025, 5, 25),
    initial_capital=100000,
    enable_replay=False,
    enable_visualization=True,
    enable_exports=True,
    strategy_params={
        "fast_period": 100,
        "slow_period": 200,
    },
)

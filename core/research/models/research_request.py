from dataclasses import dataclass
from datetime import datetime
from typing import Literal

ResearchMode = Literal[
    "BACKTEST",
    "WFA",
    "REPLAY",
]


@dataclass(frozen=True)
class ResearchRequest:
    """
    Unified research execution request.

    MVP v1 scope:
    - backtest
    - WFA
    - replay
    """

    strategy_name: str

    symbol: str

    timeframe: str

    start_date: datetime

    end_date: datetime

    mode: ResearchMode

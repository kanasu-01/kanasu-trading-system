from dataclasses import dataclass
from typing import List

from core.entities.trade import Trade
from core.backtest.bar_record import BarRecord


@dataclass(frozen=True)
class BacktestResult:
    """
    Canonical backtest execution result.

    This becomes the shared result contract for:
    - replay
    - WFA
    - analytics
    - exporters
    - visualization
    """

    trades: List[Trade]
    bar_records: List[BarRecord]
    session_id: str
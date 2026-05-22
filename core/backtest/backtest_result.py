from dataclasses import dataclass
from typing import List, Tuple

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

    @property
    def equity_curve(self) -> List[Tuple]:
        """
        Derived equity curve from canonical runtime bar records.

        Returns:
            List of (timestamp, equity)
        """
        return [(record.timestamp, record.equity) for record in self.bar_records]

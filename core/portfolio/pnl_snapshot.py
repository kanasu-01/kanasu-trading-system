from dataclasses import dataclass


@dataclass(frozen=True)
class PnLSnapshot:

    realized_pnl: float

    unrealized_pnl: float

    total_pnl: float

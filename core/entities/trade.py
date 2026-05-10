from dataclasses import dataclass
from datetime import datetime


@dataclass
class Trade:

    entry_time: datetime

    entry_price: float

    exit_time: datetime

    exit_price: float

    stop_price: float

    quantity: int

    direction: str

    exit_reason: str

    pnl: float

    pnl_pct: float
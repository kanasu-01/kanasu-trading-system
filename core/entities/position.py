from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:
    symbol: str

    entry_time: datetime

    entry_price: float

    entry_transaction_cost: float

    quantity: int

    stop_price: float

    direction: str

    entry_index: int

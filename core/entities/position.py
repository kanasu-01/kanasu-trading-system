from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:

    entry_time: datetime

    entry_price: float

    quantity: int

    stop_price: float

    direction: str

    entry_index: int
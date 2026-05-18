from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class BrokerPosition:

    symbol: str

    quantity: int

    average_price: float

    direction: str

    broker_position_id: Optional[str] = None

    opened_at: Optional[datetime] = None
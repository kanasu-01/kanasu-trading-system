from dataclasses import dataclass
from enum import Enum
from typing import Optional


class OrderStatus(Enum):
    PENDING = "PENDING"
    FILLED = "FILLED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


@dataclass
class OrderResponse:
    order_id: str
    status: OrderStatus
    filled_price: Optional[float] = None
    filled_quantity: Optional[int] = None
    message: Optional[str] = None

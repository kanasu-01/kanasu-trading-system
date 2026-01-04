from dataclasses import dataclass


@dataclass
class OrderResponse:
    success: bool
    order_id: str | None
    message: str

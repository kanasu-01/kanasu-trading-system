from dataclasses import dataclass


@dataclass
class OrderRequest:
    symbol: str
    side: str          # BUY / SELL
    quantity: int
    order_type: str    # MARKET / LIMIT
    price: float | None = None

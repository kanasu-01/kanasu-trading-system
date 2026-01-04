from typing import Optional

from core.broker.base_broker import BaseBroker
from core.broker.order import Order
from core.broker.order_response import OrderResponse, OrderStatus
from core.broker.angelone.angelone_config import AngelOneConfig


class AngelOneBroker(BaseBroker):
    """
    AngelOne SmartAPI adapter (safe skeleton).
    """

    def __init__(self, config: AngelOneConfig, paper_mode: bool = True):
        self.config = config
        self.paper_mode = paper_mode
        self._logged_in = False

    def login(self) -> bool:
        if self.paper_mode:
            self._logged_in = True
            return True
        return False

    def place_order(self, order: Order) -> OrderResponse:
        if not self._logged_in:
            return OrderResponse(
                order_id="NA",
                status=OrderStatus.REJECTED,
                message="Not logged in",
            )

        if self.paper_mode:
            return OrderResponse(
                order_id="PAPER_ORDER",
                status=OrderStatus.FILLED,
                filled_price=order.price,
                message="Paper trade",
            )

        return OrderResponse(
            order_id="NA",
            status=OrderStatus.REJECTED,
            message="Live trading disabled",
        )

    def cancel_order(self, order_id: str) -> bool:
        return True if self.paper_mode else False

    def get_order_status(self, order_id: str) -> Optional[OrderResponse]:
        return OrderResponse(
            order_id=order_id,
            status=OrderStatus.FILLED,
            message="Paper trade",
        )

    def get_account_balance(self) -> float:
        return 1_000_000.0 if self.paper_mode else 0.0

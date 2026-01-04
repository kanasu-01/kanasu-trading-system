from abc import ABC, abstractmethod
from core.execution.order_request import OrderRequest
from core.execution.order_response import OrderResponse


class BaseBroker(ABC):

    # -------- Market Data --------
    @abstractmethod
    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        start,
        end
    ):
        pass

    @abstractmethod
    def subscribe_live(self, symbol: str):
        pass

    # -------- Execution --------
    @abstractmethod
    def place_order(self, order: OrderRequest) -> OrderResponse:
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass

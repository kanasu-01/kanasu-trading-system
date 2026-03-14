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

    @abstractmethod
    def get_historical_limits(self) -> dict:
        """
            Return historical data limits for the broker
            
            Format:
            {
                "1m": max_days,
                "5m": max_days,
                "15m": max_days,
                "1d": max_days
            }
        """
        pass
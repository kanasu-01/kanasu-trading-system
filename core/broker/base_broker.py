from abc import ABC, abstractmethod
from core.execution.order import Order
from core.execution.order_response import OrderResponse
from core.entities.candle import Candle
from typing import List
from core.entities.broker_position import BrokerPosition


class BaseBroker(ABC):

    # -------- Authentication --------

    @abstractmethod
    def login(self) -> bool:
        pass

    # -------- Market Data --------
    @abstractmethod
    def get_historical_candles(
        self, symbol: str, timeframe: str, start, end
    ) -> List[Candle]:
        pass

    @abstractmethod
    def subscribe_live(self, symbol: str):
        pass

    # -------- Execution --------
    @abstractmethod
    def place_order(self, order: Order) -> OrderResponse:
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass

    @abstractmethod
    def get_order_status(
        self,
        order_id: str,
    ) -> OrderResponse:
        pass

    @abstractmethod
    def get_account_balance(self) -> float:
        pass

    @abstractmethod
    def get_open_positions(
        self,
    ) -> List[BrokerPosition]:
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

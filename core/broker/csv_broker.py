# core/broker/csv_broker.py

import csv
from typing import List
from datetime import datetime

from core.broker.base_broker import BaseBroker
from core.entities.candle import Candle
from core.execution.order import Order
from core.execution.order_response import OrderResponse, OrderStatus


class CSVBroker(BaseBroker):
    """
    CSV-backed broker for historical backtesting and replay.
    """

    def __init__(self, csv_path: str, symbol: str):
        self.csv_path = csv_path
        self.symbol = symbol

    # ---------- MARKET DATA ----------

    def get_historical_candles(
        self, symbol: str, timeframe: str, start, end
    ) -> List[Candle]:
        candles: List[Candle] = []

        with open(self.csv_path, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = datetime.fromisoformat(row["timestamp"])

                if start and ts < start:
                    continue
                if end and ts > end:
                    continue

                candles.append(
                    Candle(
                        timestamp=ts,
                        open=float(row["open"]),
                        high=float(row["high"]),
                        low=float(row["low"]),
                        close=float(row["close"]),
                        volume=float(row["volume"]),
                        symbol=self.symbol,
                    )
                )

        return candles

    def subscribe_live(self, symbol: str):
        raise NotImplementedError("CSVBroker does not support live subscriptions")

    # ---------- ORDER INTERFACE (NOT USED) ----------

    def login(self) -> bool:
        return True

    def place_order(self, order: Order) -> OrderResponse:
        return OrderResponse(
            order_id="CSV",
            status=OrderStatus.REJECTED,
            message="CSV broker does not support live orders",
        )

    def cancel_order(self, order_id: str) -> bool:
        return False

    def get_historical_limits(self) -> dict:

        return {
            "1m": 3650,
            "5m": 3650,
            "15m": 3650,
            "1d": 3650,
        }

    def get_order_status(
        self,
        order_id: str,
    ) -> OrderResponse:

        return OrderResponse(
            order_id=order_id,
            status=OrderStatus.REJECTED,
            message="CSV broker does not track order status",
        )

    def get_account_balance(self) -> float:
        return 0.0

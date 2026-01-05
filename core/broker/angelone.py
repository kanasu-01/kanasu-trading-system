from typing import Optional, List
from datetime import datetime

from core.broker.base_broker import BaseBroker
from core.execution.order import Order
from core.execution.order_response import OrderResponse, OrderStatus
from core.broker.angelone_config import AngelOneConfig
from core.entities.candle import Candle


class AngelOneBroker(BaseBroker):
    """
    AngelOne SmartAPI adapter (safe skeleton + historical data).
    """

    # ---------------- TIMEFRAME MAP ----------------
    _TIMEFRAME_MAP = {
        "1m": "ONE_MINUTE",
        "3m": "THREE_MINUTE",
        "5m": "FIVE_MINUTE",
        "15m": "FIFTEEN_MINUTE",
        "30m": "THIRTY_MINUTE",
        "1h": "ONE_HOUR",
        "1d": "ONE_DAY",
    }

    def __init__(self, config: AngelOneConfig, paper_mode: bool = True):
        self.config = config
        self.paper_mode = paper_mode
        self._logged_in = False

    # ---------------- AUTH ----------------

    def login(self) -> bool:
        if self.paper_mode:
            self._logged_in = True
            return True
        # Live login will be implemented later
        return False

    # ---------------- ORDERS ----------------

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

    # ---------------- HISTORICAL DATA ----------------

    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        start,
        end
    ) -> List[Candle]:
        """
        Fetch historical candles from AngelOne.
        In paper_mode, returns empty list (safe).
        """

        if timeframe not in self._TIMEFRAME_MAP:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        if self.paper_mode:
            # In Phase 10.9C we do NOT fetch live data yet
            # This keeps backtesting + CSV workflows intact
            return []

        if not self._logged_in:
            raise RuntimeError("Broker not logged in")

        # -------- LIVE IMPLEMENTATION (PHASE 11) --------
        # Example (to be implemented later):
        #
        # interval = self._TIMEFRAME_MAP[timeframe]
        # response = self.smart_api.getCandleData({
        #     "exchange": "NSE",
        #     "symboltoken": symbol,
        #     "interval": interval,
        #     "fromdate": start,
        #     "todate": end
        # })
        #
        # candles = []
        # for row in response["data"]:
        #     candles.append(
        #         Candle(
        #             timestamp=datetime.strptime(row[0], "%Y-%m-%d %H:%M"),
        #             open=float(row[1]),
        #             high=float(row[2]),
        #             low=float(row[3]),
        #             close=float(row[4]),
        #             volume=float(row[5]),
        #             symbol=symbol,
        #         )
        #     )
        # return candles

        return []
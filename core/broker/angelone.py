from typing import Optional, List
from datetime import datetime
import pytz

from smartapi import SmartConnect

from core.broker.base_broker import BaseBroker
from core.execution.order import Order
from core.execution.order_response import OrderResponse, OrderStatus
from core.broker.angelone_config import AngelOneConfig
from core.entities.candle import Candle


class AngelOneBroker(BaseBroker):
    """
    AngelOne SmartAPI adapter.
    - Paper trading supported
    - Historical data API wired (Phase 10.10-C)
    - Live trading intentionally disabled
    """

    def __init__(
        self,
        config: AngelOneConfig,
        paper_mode: bool = True,
        enable_historical_api: bool = False,
    ):
        self.config = config
        self.paper_mode = paper_mode
        self.enable_historical_api = enable_historical_api

        self._logged_in = False
        self._api: Optional[SmartConnect] = None

    # --------------------------------------------------
    # AUTH
    # --------------------------------------------------

    def login(self) -> bool:
        """
        Login to AngelOne SmartAPI.
        Paper mode logs in locally.
        """

        if self.paper_mode:
            self._logged_in = True
            return True

        self._api = SmartConnect(api_key=self.config.api_key)

        session = self._api.generateSession(
            self.config.client_code,
            self.config.password,
            self.config.totp,
        )

        if not session or "jwtToken" not in session:
            raise RuntimeError("AngelOne login failed")

        self._logged_in = True
        return True

    # --------------------------------------------------
    # ORDERS (PAPER ONLY)
    # --------------------------------------------------

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

    # --------------------------------------------------
    # HISTORICAL DATA (PHASE 10.10-C)
    # --------------------------------------------------

    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> List[Candle]:
        """
        Fetch historical candles from AngelOne SmartAPI.
        """

        if not self.enable_historical_api:
            raise RuntimeError(
                "AngelOne historical API disabled. "
                "Enable via enable_historical_api=True"
            )

        if not self._logged_in or self._api is None:
            raise RuntimeError("AngelOne broker not logged in")

        # ---- AngelOne timeframe mapping ----
        interval_map = {
            "1m": "ONE_MINUTE",
            "3m": "THREE_MINUTE",
            "5m": "FIVE_MINUTE",
            "15m": "FIFTEEN_MINUTE",
            "30m": "THIRTY_MINUTE",
            "1h": "ONE_HOUR",
            "1d": "ONE_DAY",
        }

        if timeframe not in interval_map:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        interval = interval_map[timeframe]

        # ---- Timezone normalization (IST) ----
        ist = pytz.timezone("Asia/Kolkata")
        start_dt = ist.localize(start) if start.tzinfo is None else start
        end_dt = ist.localize(end) if end.tzinfo is None else end

        # ---- Fetch data from AngelOne ----
        response = self._api.getCandleData({
            "exchange": self.config.exchange,
            "symboltoken": self.config.symbol_token_map[symbol],
            "interval": interval,
            "fromdate": start_dt.strftime("%Y-%m-%d %H:%M"),
            "todate": end_dt.strftime("%Y-%m-%d %H:%M"),
        })

        if not response or "data" not in response:
            raise RuntimeError("Invalid historical data response from AngelOne")

        candles: List[Candle] = []

        for row in response["data"]:
            ts = datetime.strptime(row[0], "%Y-%m-%d %H:%M")
            ts = ist.localize(ts)

            candles.append(
                Candle(
                    timestamp=ts,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                    symbol=symbol,
                )
            )

        if not candles:
            raise RuntimeError("No historical candles returned")

        return candles
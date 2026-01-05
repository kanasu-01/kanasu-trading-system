from typing import Optional, List
from datetime import datetime
import pytz

from core.broker.base_broker import BaseBroker
from core.execution.order import Order
from core.execution.order_response import OrderResponse, OrderStatus
from core.broker.angelone_config import AngelOneConfig
from core.entities.candle import Candle


class AngelOneBroker(BaseBroker):
    """
    AngelOne SmartAPI adapter (safe, API-ready, flag-controlled).
    """

    def __init__(
        self,
        config: AngelOneConfig,
        paper_mode: bool = True,
        enable_historical_api: bool = False,   # 🔹 NEW
    ):
        self.config = config
        self.paper_mode = paper_mode
        self.enable_historical_api = enable_historical_api
        self._logged_in = False

        # Placeholder for SmartAPI client (wired later)
        self._api = None

    # --------------------------------------------------
    # AUTH
    # --------------------------------------------------

    def login(self) -> bool:
        if self.paper_mode:
            self._logged_in = True
            return True

        # 🔒 Live login intentionally not implemented yet
        return False

    # --------------------------------------------------
    # ORDERS (EXISTING)
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
    # HISTORICAL DATA (PHASE 10.10-B)
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
        API-ready but disabled unless enable_historical_api=True
        """

        if not self.enable_historical_api:
            raise RuntimeError(
                "AngelOne historical API disabled. "
                "Enable via enable_historical_api=True"
            )

        # ---- Timeframe mapping (AngelOne-specific) ----
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

        # ---- Normalize timezone (IST) ----
        ist = pytz.timezone("Asia/Kolkata")
        start_dt = ist.localize(start) if start.tzinfo is None else start
        end_dt = ist.localize(end) if end.tzinfo is None else end

        # ---- API call placeholder ----
        # NOTE:
        # Actual SmartAPI wiring will be done in Phase 10.10-C
        # Expected response format documented, not yet called.

        raise NotImplementedError(
            "AngelOne historical API wiring pending (Phase 10.10-C)"
        )

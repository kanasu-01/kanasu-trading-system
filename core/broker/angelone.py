from typing import Optional, List
from datetime import datetime
import pytz
import pyotp

from SmartApi import SmartConnect

from core.broker.base_broker import BaseBroker
from core.execution.order import Order
from core.execution.order_response import OrderResponse, OrderStatus
from core.broker.angelone_config import AngelOneConfig
from core.entities.candle import Candle
from core.logging.logger import get_logger
from core.utils.retry import RetryPolicy


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
        login_retry_attempts: int = 2,
        login_retry_delay_seconds: float = 2.0,
    ):
        self.config = config
        self.paper_mode = paper_mode
        self.enable_historical_api = enable_historical_api
        self.login_retry_attempts = login_retry_attempts
        self.login_retry_delay_seconds = (
            login_retry_delay_seconds
        )

        self._logged_in = False
        self._api: Optional[SmartConnect] = None
        self._auth_token: Optional[str] = None
        self._feed_token: Optional[str] = None
        self.logger = get_logger(__name__)

    # --------------------------------------------------
    # AUTH
    # --------------------------------------------------

    def login(self) -> bool:
        """
        Login to AngelOne SmartAPI.

        NOTE:
            - Required for historical data
            - Required for live data
            - paper_mode affects ONLY order execution
        """

        self._api = SmartConnect(api_key=self.config.api_key)

        if not self.config.totp_secret:
            raise RuntimeError("TOTP secret not configured for AngelOne login")

        totp = pyotp.TOTP(self.config.totp_secret).now()

        retry_policy = RetryPolicy(
            max_retries=self.login_retry_attempts,
            delay_seconds=self.login_retry_delay_seconds,
        )

        try:
            session = retry_policy.execute(
                self._api.generateSession,
                self.config.client_id,
                self.config.client_pin,
                totp,
            )
        except Exception as e:
            self.logger.exception(
                "AngelOne login request failed"
            )
            raise RuntimeError(
                "AngelOne login request failed"
            ) from e

        if not isinstance(session, dict):
            raise RuntimeError("AngelOne login failed: invalid session response")
        self.logger.info(
            f"AngelOne login successful | " f"Session keys={list(session.keys())}"
        )

        ##print(self.config.client_id, self.config.client_pin, totp, self.config.api_key,self._api,session.jwtToken)

        if "data" not in session or not isinstance(session["data"], dict):
            raise RuntimeError("AngelOne login failed: data block missing")

        jwt_token = session["data"].get("jwtToken")
        if not isinstance(jwt_token, str) or not jwt_token:
            raise RuntimeError("AngelOne login failed: jwtToken missing")

        try:
            feed_token = self._api.getfeedToken()
        except Exception as e:
            raise RuntimeError(
                "AngelOne login failed: feed token unavailable"
            ) from e

        if not isinstance(feed_token, str) or not feed_token:
            raise RuntimeError(
                "AngelOne login failed: feed token unavailable"
            )

        self._auth_token = jwt_token
        self._feed_token = feed_token
        self._logged_in = True
        return True

    def get_live_market_data_session(self) -> tuple[str, str]:
        """Return authenticated material required by SmartWebSocketV2."""
        if (
            not self._logged_in
            or self._auth_token is None
            or self._feed_token is None
        ):
            raise RuntimeError(
                "AngelOne live market-data session unavailable"
            )

        return self._auth_token, self._feed_token

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

    def get_order_status(self, order_id: str) -> OrderResponse:
        return OrderResponse(
            order_id=order_id,
            status=OrderStatus.FILLED,
            message="Paper trade",
        )

    def get_account_balance(self) -> float:
        return 1_000_000.0 if self.paper_mode else 0.0

    def get_open_positions(self):

        return []

        # --------------------------------------------------

    # LIVE DATA (NOT SUPPORTED YET)
    # --------------------------------------------------

    def subscribe_live(self, Symbol: str):
        raise NotImplementedError(
            "Live data subscription not implemented for AngelOneBroker"
        )

    # -------------------------------------------------
    # HISTORICAL DATA LIMITS
    # -------------------------------------------------
    def get_historical_limits(self) -> dict:
        """
        Return historical data limits per timeframe for AngelOne SmartAPI.
        """
        return {
            "1m": 30,
            "3m": 60,
            "5m": 100,
            "10m": 100,
            "15m": 200,
            "30m": 200,
            "1h": 400,
            "1d": 2000,
        }

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
            "10m": "TEN_MINUTE",
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
        symbol_token_map = self.config.symbol_token_map
        if symbol_token_map is None:
            raise RuntimeError("Angelone symbol toke map is not configured")
        if symbol not in symbol_token_map:
            raise RuntimeError("error")
        symbol_token = symbol_token_map[symbol]

        try:

            response = self._api.getCandleData(
                {
                    "exchange": self.config.exchange,
                    "symboltoken": symbol_token,
                    "interval": interval,
                    "fromdate": start_dt.strftime("%Y-%m-%d %H:%M"),
                    "todate": end_dt.strftime("%Y-%m-%d %H:%M"),
                }
            )

        except Exception as e:

            self.logger.exception(
                f"AngelOne historical fetch failed | "
                f"Symbol={symbol} | "
                f"Timeframe={timeframe}"
            )

            raise RuntimeError("AngelOne historical data request failed") from e

        if not isinstance(response, dict):
            raise RuntimeError("Invalid historical data response from AngelOne")

        if "data" not in response:
            raise RuntimeError("Missing data in AngelOne historical response")

        data = response["data"]
        if not isinstance(data, list):
            raise RuntimeError("Invalid data in AngelOne historical response")

        candles: List[Candle] = []

        for row in data:
            ts = datetime.fromisoformat(row[0])

            candles.append(
                Candle(
                    timestamp=ts,
                    open=float(row[1]),
                    high=float(row[2]),
                    low=float(row[3]),
                    close=float(row[4]),
                    volume=float(row[5]),
                )
            )

        return candles

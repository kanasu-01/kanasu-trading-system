from collections.abc import Callable
from datetime import datetime
import pytz
from typing import Any

from SmartApi.smartWebSocketV2 import SmartWebSocketV2

from core.broker.angelone_config import AngelOneConfig
from core.logging.logger import get_logger
from core.market_data.live_market_update import LiveMarketUpdate


LiveMarketUpdateHandler = Callable[[LiveMarketUpdate], None]
WebSocketFactory = Callable[..., Any]

_IST = pytz.timezone("Asia/Kolkata")
_NSE_CM = 1
_QUOTE_MODE = 2
_NSE_PRICE_DIVISOR = 100.0
_CORRELATION_ID = "kanasuM630"


class AngelOneLiveMarketDataAdapter:
    """
    One-symbol AngelOne SmartWebSocketV2 market-data adapter.

    Provider messages are normalized into LiveMarketUpdate objects.
    Candle construction and completed-candle validity remain downstream.
    """

    def __init__(
        self,
        config: AngelOneConfig,
        auth_token: str,
        feed_token: str,
        symbol: str,
        on_update: LiveMarketUpdateHandler,
        websocket_factory: WebSocketFactory = SmartWebSocketV2,
    ) -> None:
        if config.exchange.upper() != "NSE":
            raise ValueError(
                "M6.3 AngelOne live market data supports NSE only"
            )

        if not isinstance(auth_token, str) or not auth_token:
            raise ValueError("AngelOne live auth token is required")

        if not isinstance(feed_token, str) or not feed_token:
            raise ValueError("AngelOne live feed token is required")

        symbol_token_map = config.symbol_token_map
        if symbol_token_map is None or symbol not in symbol_token_map:
            raise ValueError(
                f"AngelOne live symbol is not configured: {symbol}"
            )

        token = symbol_token_map[symbol]
        if not isinstance(token, str) or not token:
            raise ValueError(
                f"AngelOne live symbol token is invalid: {symbol}"
            )

        self.config = config
        self.auth_token = auth_token
        self.feed_token = feed_token
        self.symbol = symbol
        self.token = token
        self.on_update = on_update
        self._websocket_factory = websocket_factory
        self._socket: Any | None = None
        self.logger = get_logger(__name__)

    def connect(self) -> None:
        """
        Open the provider socket.

        SmartWebSocketV2.connect() is blocking. M6.3 does not create a
        background thread; runtime ownership belongs to a later milestone.
        """
        if self._socket is not None:
            raise RuntimeError(
                "AngelOne live market-data socket is already initialized"
            )

        socket = self._websocket_factory(
            self.auth_token,
            self.config.api_key,
            self.config.client_id,
            self.feed_token,
            max_retry_attempt=0,
        )

        socket.on_open = self._handle_open
        socket.on_data = self._handle_data
        socket.on_error = self._handle_error
        socket.on_close = self._handle_close

        self._socket = socket
        socket.connect()

    def close(self) -> None:
        """Close the provider socket if one has been initialized."""
        if self._socket is None:
            return

        socket = self._socket
        self._socket = None
        socket.close_connection()

    def normalize_message(
        self,
        message: object,
    ) -> LiveMarketUpdate:
        """Normalize one AngelOne Quote message."""
        if not isinstance(message, dict):
            raise ValueError(
                "AngelOne live market-data message must be a mapping"
            )

        subscription_mode = self._required_int(
            message,
            "subscription_mode",
        )
        if subscription_mode != _QUOTE_MODE:
            raise ValueError(
                "AngelOne live market-data message must use QUOTE mode"
            )

        exchange_type = self._required_int(
            message,
            "exchange_type",
        )
        if exchange_type != _NSE_CM:
            raise ValueError(
                "AngelOne live market-data message has invalid exchange type"
            )

        if "token" not in message:
            raise ValueError(
                "AngelOne live market-data message missing required field: token"
            )

        token = message["token"]
        if token != self.token:
            raise ValueError(
                "AngelOne live market-data message token does not match "
                "the configured symbol"
            )

        sequence = self._required_int(
            message,
            "sequence_number",
        )
        exchange_timestamp = self._required_int(
            message,
            "exchange_timestamp",
        )
        last_traded_price = self._required_int(
            message,
            "last_traded_price",
        )
        cumulative_volume = self._required_int(
            message,
            "volume_trade_for_the_day",
        )

        if exchange_timestamp <= 0:
            raise ValueError(
                "AngelOne live exchange timestamp must be positive"
            )

        try:
            timestamp = datetime.fromtimestamp(
                exchange_timestamp / 1000.0,
                tz=_IST,
            )
        except (OverflowError, OSError, ValueError) as e:
            raise ValueError(
                "AngelOne live exchange timestamp is invalid"
            ) from e

        return LiveMarketUpdate(
            timestamp=timestamp,
            price=last_traded_price / _NSE_PRICE_DIVISOR,
            cumulative_volume=float(cumulative_volume),
            sequence=sequence,
        )

    def _handle_open(self, _wsapp: object) -> None:
        if self._socket is None:
            raise RuntimeError(
                "AngelOne live market-data socket is not initialized"
            )

        self._socket.subscribe(
            _CORRELATION_ID,
            _QUOTE_MODE,
            [
                {
                    "exchangeType": _NSE_CM,
                    "tokens": [self.token],
                }
            ],
        )

    def _handle_data(
        self,
        _wsapp: object,
        message: object,
    ) -> None:
        try:
            update = self.normalize_message(message)
        except Exception:
            self.logger.exception(
                f"AngelOne live market-data message rejected | "
                f"Symbol={self.symbol}"
            )
            raise

        self.on_update(update)

    def _handle_error(
        self,
        _wsapp: object,
        error: object,
    ) -> None:
        self.logger.error(
            f"AngelOne live market-data socket error | "
            f"Symbol={self.symbol} | Error={error}"
        )

    def _handle_close(self, _wsapp: object) -> None:
        self.logger.info(
            f"AngelOne live market-data socket closed | "
            f"Symbol={self.symbol}"
        )

    @staticmethod
    def _required_int(
        message: dict,
        key: str,
    ) -> int:
        if key not in message:
            raise ValueError(
                f"AngelOne live market-data message missing required field: "
                f"{key}"
            )

        value = message[key]
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(
                f"AngelOne live market-data field must be an integer: {key}"
            )

        return value

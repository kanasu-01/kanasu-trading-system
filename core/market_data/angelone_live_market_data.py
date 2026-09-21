from collections.abc import Callable
from datetime import datetime
from functools import partial
from typing import Any

import pytz

from core.broker.angelone_config import AngelOneConfig
from core.market_data.angelone_verified_websocket import (
    VerifiedSmartWebSocketV2,
)
from core.logging.logger import get_logger
from core.market_data.live_market_update import LiveMarketUpdate


LiveMarketUpdateHandler = Callable[[LiveMarketUpdate], None]
ConnectionLostHandler = Callable[[], None]
WebSocketFactory = Callable[..., Any]

_IST = pytz.timezone("Asia/Kolkata")
_NSE_CM = 1
_QUOTE_MODE = 2
_NSE_PRICE_DIVISOR = 100.0
_CORRELATION_ID = "kanasuM630"


class FatalLiveMarketDataCallbackError(RuntimeError):
    """Fatal failure while processing a provider callback."""


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
        websocket_factory: WebSocketFactory = VerifiedSmartWebSocketV2,
        on_disconnect: ConnectionLostHandler | None = None,
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
        self.on_disconnect = on_disconnect
        self._websocket_factory = websocket_factory
        self._socket: Any | None = None
        self._disconnect_notified = False
        self._callback_failure: Exception | None = None
        self.logger = get_logger(__name__)

    def connect(self) -> None:
        """
        Open the provider socket.

        SmartWebSocketV2.connect() is blocking. M6.4 does not create a
        background thread; runtime ownership belongs to a later milestone.
        """
        if self._socket is not None:
            raise RuntimeError(
                "AngelOne live market-data socket is already initialized"
            )

        self._disconnect_notified = False
        self._callback_failure = None

        socket = self._websocket_factory(
            self.auth_token,
            self.config.api_key,
            self.config.client_id,
            self.feed_token,
            max_retry_attempt=0,
        )

        # Capture the provider socket in each callback. A late callback from
        # an older connection epoch must never affect a newer socket.
        socket.on_open = partial(self._handle_open, socket)
        socket.on_data = partial(self._handle_data, socket)
        socket.on_error = partial(self._handle_error, socket)
        socket.on_close = partial(self._handle_close, socket)

        self._socket = socket

        try:
            socket.connect()
        except Exception:
            if self._socket is socket:
                self._socket = None

            self._notify_disconnect()
            self._raise_callback_failure()
            raise

        if self._callback_failure is not None:
            if self._socket is socket:
                self._socket = None

            self._notify_disconnect()
            self._raise_callback_failure()

    def close(self) -> None:
        """Close the currently active provider socket."""
        if self._socket is None:
            return

        socket = self._socket

        # Detach before closing so any asynchronous close callback from this
        # socket is recognized as stale.
        self._socket = None
        self._disconnect_notified = True

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

    def _handle_open(
        self,
        socket: Any,
        _wsapp: object,
    ) -> None:
        if self._socket is not socket:
            return

        socket.subscribe(
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
        socket: Any,
        _wsapp: object,
        message: object,
    ) -> None:
        if self._socket is not socket:
            return

        try:
            update = self.normalize_message(message)
            self.on_update(update)
        except Exception as exc:
            self.logger.exception(
                f"AngelOne live market-data callback failed | "
                f"Symbol={self.symbol}"
            )
            self._record_callback_failure(
                socket,
                exc,
            )
            raise

    def _record_callback_failure(
        self,
        socket: Any,
        failure: Exception,
    ) -> None:
        if self._callback_failure is None:
            self._callback_failure = failure

        if self._socket is socket:
            self._socket = None

        self._notify_disconnect()

        try:
            socket.close_connection()
        except Exception:
            self.logger.exception(
                f"AngelOne live market-data socket close failed after "
                f"fatal callback | Symbol={self.symbol}"
            )

    def _raise_callback_failure(self) -> None:
        failure = self._callback_failure

        if failure is None:
            return

        raise FatalLiveMarketDataCallbackError(
            "AngelOne live market-data callback processing failed"
        ) from failure

    def _handle_error(
        self,
        socket: Any,
        _wsapp: object,
        error: object,
    ) -> None:
        if self._socket is not socket:
            return

        # Detach immediately. No update from this failed connection epoch may
        # reach the downstream candle pipeline after an error.
        self._socket = None

        self.logger.error(
            f"AngelOne live market-data socket error | "
            f"Symbol={self.symbol} | Error={error}"
        )

        self._notify_disconnect()

    def _handle_close(
        self,
        socket: Any,
        _wsapp: object,
    ) -> None:
        if self._socket is not socket:
            return

        self._socket = None

        self.logger.info(
            f"AngelOne live market-data socket closed | "
            f"Symbol={self.symbol}"
        )

        self._notify_disconnect()

    def _notify_disconnect(self) -> None:
        if self._disconnect_notified:
            return

        self._disconnect_notified = True

        if self.on_disconnect is not None:
            self.on_disconnect()

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

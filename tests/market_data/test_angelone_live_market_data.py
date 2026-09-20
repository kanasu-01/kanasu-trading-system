from datetime import datetime
import pytz

import pytest

import core.broker.angelone as angelone_module
from core.broker.angelone import AngelOneBroker
from core.broker.angelone_config import AngelOneConfig
from core.market_data.angelone_live_market_data import (
    AngelOneLiveMarketDataAdapter,
)
from core.market_data.live_market_update import LiveMarketUpdate


IST = pytz.timezone("Asia/Kolkata")
EVENT_TIMESTAMP = IST.localize(
    datetime(
        2026,
        1,
        2,
        10,
        15,
        3,
    )
)
EVENT_TIMESTAMP_MS = int(EVENT_TIMESTAMP.timestamp() * 1000)


class FakeTOTP:
    def __init__(self, secret):
        self.secret = secret

    def now(self):
        return "123456"


class FakeSmartConnect:
    def __init__(self, api_key):
        self.api_key = api_key

    def generateSession(self, client_id, client_pin, totp):
        assert client_id == "client-id"
        assert client_pin == "pin"
        assert totp == "123456"
        return {
            "data": {
                "jwtToken": "Bearer jwt-token",
            }
        }

    def getfeedToken(self):
        return "feed-token"


class FakeSocket:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.on_open = None
        self.on_data = None
        self.on_error = None
        self.on_close = None
        self.connected = False
        self.closed = False
        self.subscribe_calls = []

    def connect(self):
        self.connected = True
        self.on_open(self)

    def subscribe(self, correlation_id, mode, token_list):
        self.subscribe_calls.append(
            (correlation_id, mode, token_list)
        )

    def close_connection(self):
        self.closed = True


def _config(
    symbol_token_map=None,
    exchange="NSE",
):
    if symbol_token_map is None:
        symbol_token_map = {"RELIANCE": "2885"}

    return AngelOneConfig(
        api_key="api-key",
        client_id="client-id",
        client_pin="pin",
        totp_secret="totp-secret",
        exchange=exchange,
        symbol_token_map=symbol_token_map,
    )


def _adapter(
    on_update=lambda _update: None,
    websocket_factory=FakeSocket,
):
    return AngelOneLiveMarketDataAdapter(
        config=_config(),
        auth_token="Bearer jwt-token",
        feed_token="feed-token",
        symbol="RELIANCE",
        on_update=on_update,
        websocket_factory=websocket_factory,
    )


def _message():
    return {
        "subscription_mode": 2,
        "exchange_type": 1,
        "token": "2885",
        "sequence_number": 7,
        "exchange_timestamp": EVENT_TIMESTAMP_MS,
        "last_traded_price": 2451050,
        "volume_trade_for_the_day": 120500,
    }


def test_broker_login_retains_websocket_session_tokens(
    monkeypatch,
):
    monkeypatch.setattr(
        angelone_module,
        "SmartConnect",
        FakeSmartConnect,
    )
    monkeypatch.setattr(
        angelone_module.pyotp,
        "TOTP",
        FakeTOTP,
    )

    broker = AngelOneBroker(_config())

    assert broker.login() is True
    assert broker.get_live_market_data_session() == (
        "Bearer jwt-token",
        "feed-token",
    )


def test_broker_live_session_requires_login():
    broker = AngelOneBroker(_config())

    with pytest.raises(
        RuntimeError,
        match="session unavailable",
    ):
        broker.get_live_market_data_session()


def test_adapter_connects_and_subscribes_quote_mode():
    created = []

    def factory(*args, **kwargs):
        socket = FakeSocket(*args, **kwargs)
        created.append(socket)
        return socket

    adapter = _adapter(websocket_factory=factory)

    adapter.connect()

    assert len(created) == 1
    socket = created[0]

    assert socket.args == (
        "Bearer jwt-token",
        "api-key",
        "client-id",
        "feed-token",
    )
    assert socket.kwargs == {
        "max_retry_attempt": 0,
    }
    assert socket.connected is True
    assert socket.subscribe_calls == [
        (
            "kanasuM630",
            2,
            [
                {
                    "exchangeType": 1,
                    "tokens": ["2885"],
                }
            ],
        )
    ]


def test_quote_message_normalizes_and_delivers_update():
    created = []
    received = []

    def factory(*args, **kwargs):
        socket = FakeSocket(*args, **kwargs)
        created.append(socket)
        return socket

    adapter = _adapter(
        on_update=received.append,
        websocket_factory=factory,
    )
    adapter.connect()

    socket = created[0]
    socket.on_data(socket, _message())

    assert received == [
        LiveMarketUpdate(
            timestamp=EVENT_TIMESTAMP,
            price=24510.5,
            cumulative_volume=120500.0,
            sequence=7,
        )
    ]
    assert received[0].timestamp.tzinfo.zone == "Asia/Kolkata"


def test_close_closes_provider_socket():
    created = []

    def factory(*args, **kwargs):
        socket = FakeSocket(*args, **kwargs)
        created.append(socket)
        return socket

    adapter = _adapter(websocket_factory=factory)
    adapter.connect()

    adapter.close()

    assert created[0].closed is True

    # Close remains safe when already closed.
    adapter.close()


def test_unknown_symbol_is_rejected():
    with pytest.raises(
        ValueError,
        match="not configured",
    ):
        AngelOneLiveMarketDataAdapter(
            config=_config(),
            auth_token="Bearer jwt-token",
            feed_token="feed-token",
            symbol="UNKNOWN",
            on_update=lambda _update: None,
            websocket_factory=FakeSocket,
        )


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        (
            "subscription_mode",
            1,
            "QUOTE mode",
        ),
        (
            "exchange_type",
            2,
            "exchange type",
        ),
        (
            "token",
            "9999",
            "token does not match",
        ),
    ],
)
def test_provider_identity_must_match_subscription(
    field,
    value,
    match,
):
    adapter = _adapter()
    message = _message()
    message[field] = value

    with pytest.raises(ValueError, match=match):
        adapter.normalize_message(message)


@pytest.mark.parametrize(
    "field",
    [
        "sequence_number",
        "exchange_timestamp",
        "last_traded_price",
        "volume_trade_for_the_day",
    ],
)
def test_required_quote_fields_are_required(field):
    adapter = _adapter()
    message = _message()
    del message[field]

    with pytest.raises(
        ValueError,
        match="missing required field",
    ):
        adapter.normalize_message(message)


def test_non_mapping_provider_message_is_rejected():
    adapter = _adapter()

    with pytest.raises(
        ValueError,
        match="must be a mapping",
    ):
        adapter.normalize_message("not-a-message")


def test_invalid_exchange_timestamp_is_rejected():
    adapter = _adapter()
    message = _message()
    message["exchange_timestamp"] = 0

    with pytest.raises(
        ValueError,
        match="timestamp must be positive",
    ):
        adapter.normalize_message(message)

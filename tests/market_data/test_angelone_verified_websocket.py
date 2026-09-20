import ssl

import pytest

from core.broker.angelone_config import AngelOneConfig
from core.market_data import angelone_verified_websocket as transport_module
from core.market_data.angelone_live_market_data import (
    AngelOneLiveMarketDataAdapter,
)
from core.market_data.angelone_verified_websocket import (
    VerifiedSmartWebSocketV2,
)


class FakeWebSocketApp:
    plans = []
    instances = []

    def __init__(
        self,
        url,
        header=None,
        on_open=None,
        on_error=None,
        on_close=None,
        on_data=None,
        on_ping=None,
        on_pong=None,
    ):
        self.url = url
        self.header = header
        self.on_open = on_open
        self.on_error = on_error
        self.on_close = on_close
        self.on_data = on_data
        self.on_ping = on_ping
        self.on_pong = on_pong
        self.closed = False
        self.run_forever_kwargs = None

        type(self).instances.append(self)

    @classmethod
    def reset(cls, plans):
        cls.plans = list(plans)
        cls.instances = []

    def run_forever(self, **kwargs):
        self.run_forever_kwargs = kwargs

        if not type(self).plans:
            raise AssertionError(
                "No fake WebSocketApp plan remains"
            )

        plan = type(self).plans.pop(0)

        if plan == "tls_failure":
            self.on_error(
                self,
                ssl.SSLCertVerificationError(
                    1,
                    "certificate verify failed",
                ),
            )
            return True

        if plan == "normal_close":
            self.on_close(
                self,
                1000,
                "normal closure",
            )
            return False

        raise AssertionError(
            f"Unknown fake WebSocketApp plan: {plan}"
        )

    def close(self):
        self.closed = True


def _config() -> AngelOneConfig:
    return AngelOneConfig(
        api_key="api-key",
        client_id="client-id",
        client_pin="pin",
        totp_secret="totp-secret",
        exchange="NSE",
        symbol_token_map={"RELIANCE": "2885"},
    )


def test_verified_transport_requires_tls_verification_and_accepts_close_arity(
    monkeypatch,
) -> None:
    FakeWebSocketApp.reset(["normal_close"])

    monkeypatch.setattr(
        transport_module.websocket,
        "WebSocketApp",
        FakeWebSocketApp,
    )

    closed = []

    socket = VerifiedSmartWebSocketV2(
        "Bearer jwt-token",
        "api-key",
        "client-id",
        "feed-token",
        max_retry_attempt=0,
    )
    socket.on_close = closed.append

    socket.connect()

    assert len(FakeWebSocketApp.instances) == 1
    wsapp = FakeWebSocketApp.instances[0]

    assert wsapp.header == {
        "Authorization": "Bearer jwt-token",
        "x-api-key": "api-key",
        "x-client-code": "client-id",
        "x-feed-token": "feed-token",
    }

    assert wsapp.run_forever_kwargs == {
        "sslopt": {
            "cert_reqs": ssl.CERT_REQUIRED,
            "check_hostname": True,
        },
        "ping_interval": socket.HEART_BEAT_INTERVAL,
    }

    # websocket-client supplies wsapp/status/reason to on_close.
    assert closed == [wsapp]


def test_tls_certificate_failure_fails_closed_and_adapter_is_reusable(
    monkeypatch,
) -> None:
    FakeWebSocketApp.reset(
        [
            "tls_failure",
            "normal_close",
        ]
    )

    monkeypatch.setattr(
        transport_module.websocket,
        "WebSocketApp",
        FakeWebSocketApp,
    )

    received = []
    disconnects = []

    adapter = AngelOneLiveMarketDataAdapter(
        config=_config(),
        auth_token="Bearer jwt-token",
        feed_token="feed-token",
        symbol="RELIANCE",
        on_update=received.append,
        on_disconnect=lambda: disconnects.append("lost"),
    )

    assert (
        adapter._websocket_factory
        is VerifiedSmartWebSocketV2
    )

    with pytest.raises(
        ConnectionError,
        match="verified WebSocket transport failed",
    ):
        adapter.connect()

    assert received == []
    assert disconnects == ["lost"]
    assert FakeWebSocketApp.instances[0].closed is True

    first_sslopt = (
        FakeWebSocketApp.instances[0]
        .run_forever_kwargs["sslopt"]
    )
    assert first_sslopt["cert_reqs"] == ssl.CERT_REQUIRED
    assert first_sslopt["check_hostname"] is True

    # The failed provider epoch must have cleared adapter state.
    adapter.connect()

    assert received == []
    assert disconnects == ["lost", "lost"]
    assert len(FakeWebSocketApp.instances) == 2

import ssl

import websocket
from SmartApi.smartWebSocketV2 import SmartWebSocketV2


class VerifiedSmartWebSocketV2(SmartWebSocketV2):
    """
    AngelOne SmartWebSocketV2 transport with mandatory TLS verification.

    The upstream SDK disables certificate verification. Kanasu owns this
    transport boundary so authenticated live market data is accepted only
    over a certificate- and hostname-verified TLS connection.
    """

    def connect(self) -> None:
        headers = {
            "Authorization": self.auth_token,
            "x-api-key": self.api_key,
            "x-client-code": self.client_code,
            "x-feed-token": self.feed_token,
        }

        self.wsapp = websocket.WebSocketApp(
            self.ROOT_URI,
            header=headers,
            on_open=self._on_open,
            on_error=self._on_error,
            on_close=self._on_close,
            on_data=self._on_data,
            on_ping=self._on_ping,
            on_pong=self._on_pong,
        )

        transport_failed = self.wsapp.run_forever(
            sslopt={
                "cert_reqs": ssl.CERT_REQUIRED,
                "check_hostname": True,
            },
            ping_interval=self.HEART_BEAT_INTERVAL,
        )

        if transport_failed:
            raise ConnectionError(
                "AngelOne verified WebSocket transport failed"
            )

    def _on_close(
        self,
        wsapp,
        _close_status_code=None,
        _close_msg=None,
    ) -> None:
        """
        Adapt websocket-client's three-argument close callback to the
        one-argument callback contract exposed by SmartWebSocketV2.
        """
        self.on_close(wsapp)

import threading
from datetime import datetime, time

import pytz
import pytest

from core.broker.angelone_config import AngelOneConfig
from core.market_data.angelone_live_candle_feed import (
    AngelOneLiveCandleFeed,
)
from core.market_data.angelone_live_market_data import (
    AngelOneLiveMarketDataAdapter,
)


IST = pytz.timezone("Asia/Kolkata")
SESSION_START = time(9, 15)


def _ts(
    hour: int,
    minute: int,
) -> datetime:
    return IST.localize(
        datetime(
            2026,
            1,
            2,
            hour,
            minute,
        )
    )


def _message(
    hour: int,
    minute: int,
    price_paise: int,
    cumulative_volume: int,
    sequence: int,
) -> dict:
    return {
        "subscription_mode": 2,
        "exchange_type": 1,
        "token": "2885",
        "sequence_number": sequence,
        "exchange_timestamp": int(
            _ts(hour, minute).timestamp() * 1000
        ),
        "last_traded_price": price_paise,
        "volume_trade_for_the_day": cumulative_volume,
    }


def _config() -> AngelOneConfig:
    return AngelOneConfig(
        api_key="api-key",
        client_id="client-id",
        client_pin="pin",
        totp_secret="totp-secret",
        exchange="NSE",
        symbol_token_map={"RELIANCE": "2885"},
    )


class FakeSocket:
    def __init__(
        self,
        args,
        kwargs,
        script,
        connect_error=None,
    ):
        self.args = args
        self.kwargs = kwargs
        self.script = list(script)
        self.connect_error = connect_error

        self.on_open = None
        self.on_data = None
        self.on_error = None
        self.on_close = None

        self.connected = False
        self.closed = False
        self.subscribe_calls = []

    def connect(self):
        if self.connect_error is not None:
            raise self.connect_error

        self.connected = True
        self.on_open(self)

        for message in self.script:
            self.on_data(self, message)

    def subscribe(
        self,
        correlation_id,
        mode,
        token_list,
    ):
        self.subscribe_calls.append(
            (
                correlation_id,
                mode,
                token_list,
            )
        )

    def close_connection(self):
        self.closed = True

        if self.on_close is not None:
            self.on_close(self)


class ScriptedSocketFactory:
    def __init__(self, plans):
        self.plans = list(plans)
        self.sockets = []

    def __call__(self, *args, **kwargs):
        if not self.plans:
            raise AssertionError(
                "No scripted socket plan remains"
            )

        script, connect_error = self.plans.pop(0)

        socket = FakeSocket(
            args=args,
            kwargs=kwargs,
            script=script,
            connect_error=connect_error,
        )

        self.sockets.append(socket)
        return socket


def _feed(
    factory,
) -> AngelOneLiveCandleFeed:
    return AngelOneLiveCandleFeed(
        config=_config(),
        auth_token="Bearer jwt-token",
        feed_token="feed-token",
        symbol="RELIANCE",
        timeframe="15m",
        session_start=SESSION_START,
        websocket_factory=factory,
    )


def test_provider_messages_flow_to_one_completed_candle() -> None:
    factory = ScriptedSocketFactory(
        [
            (
                [
                    _message(10, 15, 10000, 500, 1),
                    _message(10, 20, 10500, 520, 2),
                    _message(10, 30, 10300, 530, 3),
                ],
                None,
            )
        ]
    )

    feed = _feed(factory)
    delivered = []

    feed.subscribe(delivered.append)

    assert len(delivered) == 1

    candle = delivered[0]
    assert candle.timestamp == _ts(10, 15)
    assert candle.open == 100.0
    assert candle.high == 105.0
    assert candle.low == 100.0
    assert candle.close == 105.0
    assert candle.volume == pytest.approx(20.0)

    assert factory.sockets[0].subscribe_calls == [
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

    feed.close()


def test_connected_clock_does_not_complete_without_source_boundary() -> None:
    factory = ScriptedSocketFactory(
        [
            (
                [
                    _message(10, 15, 10000, 500, 1),
                    _message(10, 20, 10500, 520, 2),
                ],
                None,
            )
        ]
    )

    feed = _feed(factory)
    delivered = []

    feed.subscribe(delivered.append)

    assert delivered == []

    feed.advance_time(_ts(10, 30))

    # Caller wall time is not proof that all exchange events from the
    # interval have arrived.
    assert delivered == []

    socket = factory.sockets[0]
    socket.on_data(
        socket,
        _message(10, 30, 10300, 530, 3),
    )

    assert len(delivered) == 1
    assert delivered[0].timestamp == _ts(10, 15)

    feed.close()


def test_disconnect_reconnect_discards_gap_and_ignores_stale_socket() -> None:
    factory = ScriptedSocketFactory(
        [
            (
                [
                    _message(10, 15, 10000, 500, 100),
                    _message(10, 20, 10100, 520, 101),
                ],
                None,
            ),
            (
                [
                    _message(10, 25, 10200, 540, 1),
                    _message(10, 30, 10300, 550, 2),
                    _message(10, 35, 10400, 560, 3),
                    _message(10, 45, 10500, 570, 4),
                ],
                None,
            ),
        ]
    )

    feed = _feed(factory)
    delivered = []

    feed.subscribe(delivered.append)

    assert delivered == []
    old_socket = factory.sockets[0]

    old_socket.on_error(
        old_socket,
        RuntimeError("provider connection lost"),
    )

    assert feed.connected is False

    feed.reconnect()

    assert len(delivered) == 1
    assert delivered[0].timestamp == _ts(10, 30)
    assert delivered[0].volume == pytest.approx(20.0)

    # A late callback from the detached first socket must not alter state.
    old_socket.on_data(
        old_socket,
        _message(10, 50, 99900, 999999, 999),
    )

    assert len(delivered) == 1

    feed.close()


def test_adapter_connect_failure_is_reusable_and_reports_disconnect() -> None:
    factory = ScriptedSocketFactory(
        [
            (
                [],
                ConnectionError("connect failed"),
            ),
            (
                [],
                None,
            ),
        ]
    )

    disconnects = []

    adapter = AngelOneLiveMarketDataAdapter(
        config=_config(),
        auth_token="Bearer jwt-token",
        feed_token="feed-token",
        symbol="RELIANCE",
        on_update=lambda _update: None,
        websocket_factory=factory,
        on_disconnect=lambda: disconnects.append("lost"),
    )

    with pytest.raises(
        ConnectionError,
        match="connect failed",
    ):
        adapter.connect()

    assert disconnects == ["lost"]

    # Failed connection state was cleared, so a new epoch can start.
    adapter.connect()

    assert len(factory.sockets) == 2
    assert factory.sockets[1].connected is True

    adapter.close()


def test_provider_delivery_and_clock_advance_are_serialized() -> None:
    factory = ScriptedSocketFactory(
        [
            (
                [
                    _message(10, 15, 10000, 500, 1),
                    _message(10, 20, 10100, 520, 2),
                    _message(10, 30, 10200, 530, 3),
                ],
                None,
            )
        ]
    )

    feed = _feed(factory)
    delivery_entered = threading.Event()
    release_delivery = threading.Event()
    clock_completed = threading.Event()
    delivered = []

    def on_candle(candle) -> None:
        delivered.append(candle)

        if len(delivered) == 1:
            delivery_entered.set()
            assert release_delivery.wait(timeout=1.0)

    provider_thread = threading.Thread(
        target=feed.subscribe,
        args=(on_candle,),
    )
    provider_thread.start()

    assert delivery_entered.wait(timeout=1.0)

    def advance_clock() -> None:
        feed.advance_time(_ts(10, 45))
        clock_completed.set()

    clock_thread = threading.Thread(
        target=advance_clock,
    )
    clock_thread.start()

    try:
        assert not clock_completed.wait(timeout=0.05)
    finally:
        release_delivery.set()

    provider_thread.join(timeout=1.0)
    clock_thread.join(timeout=1.0)

    assert not provider_thread.is_alive()
    assert not clock_thread.is_alive()
    assert clock_completed.is_set()
    assert [candle.timestamp for candle in delivered] == [
        _ts(10, 15),
    ]

    feed.close()


def test_exact_retransmission_does_not_reach_market_update_consumer() -> None:
    first = _message(10, 15, 10000, 500, 1)

    factory = ScriptedSocketFactory(
        [
            (
                [
                    first,
                    dict(first),
                    _message(10, 20, 10100, 520, 2),
                ],
                None,
            )
        ]
    )

    feed = _feed(factory)
    observed = []

    feed.subscribe(
        lambda _candle: None,
        lambda update, opens_new_bar: observed.append(
            (
                update.sequence,
                opens_new_bar,
            )
        ),
    )

    # The pipeline already defines an exact retransmission of the latest
    # accepted source update as idempotent. Execution/MTM must therefore
    # see each accepted source observation only once.
    assert observed == [
        (1, False),
        (2, False),
    ]

    feed.close()

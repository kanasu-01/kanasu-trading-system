import threading
from datetime import datetime, time

import pytz

from core.broker.angelone_config import AngelOneConfig
from core.config.execution_config import ExecutionConfig
from core.entities.candle_series import CandleSeries
from core.market_data.angelone_live_candle_feed import (
    AngelOneLiveCandleFeed,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.paper_runtime import run_live_paper_trading
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import SignalType


IST = pytz.timezone("Asia/Kolkata")
SESSION_START = time(9, 15)


def _ts(hour: int, minute: int) -> datetime:
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


class ScriptedEpochSocket:
    def __init__(
        self,
        *,
        args,
        kwargs,
        script,
        terminal_error=None,
        ready_event=None,
        block_after=False,
    ) -> None:
        self.args = args
        self.kwargs = kwargs
        self.script = list(script)
        self.terminal_error = terminal_error
        self.ready_event = ready_event
        self.block_after = block_after

        self.on_open = None
        self.on_data = None
        self.on_error = None
        self.on_close = None

        self.closed = threading.Event()
        self.subscribe_calls = []

    def connect(self) -> None:
        self.on_open(self)

        for message in self.script:
            self.on_data(self, message)

        if self.ready_event is not None:
            self.ready_event.set()

        if self.terminal_error is not None:
            raise self.terminal_error

        if self.block_after:
            if not self.closed.wait(timeout=2.0):
                raise RuntimeError(
                    "test provider socket was not closed"
                )

    def subscribe(
        self,
        correlation_id,
        mode,
        token_list,
    ) -> None:
        self.subscribe_calls.append(
            (
                correlation_id,
                mode,
                token_list,
            )
        )

    def close_connection(self) -> None:
        self.closed.set()


class ScriptedEpochFactory:
    def __init__(self, plans) -> None:
        self.plans = list(plans)
        self.sockets = []

    def __call__(self, *args, **kwargs):
        if not self.plans:
            raise AssertionError(
                "unexpected extra provider reconnect"
            )

        plan = self.plans.pop(0)

        socket = ScriptedEpochSocket(
            args=args,
            kwargs=kwargs,
            **plan,
        )
        self.sockets.append(socket)
        return socket


class BuyFirstDeliveredCandleStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="buy_first_delivered_candle"
        )
        self.seen_timestamps = []

    def on_new_candle(
        self,
        series: CandleSeries,
    ) -> SignalType | None:
        self.seen_timestamps.append(
            series[-1].timestamp
        )

        if len(series) == 1:
            return SignalType.BUY

        return None

    def reset(self) -> None:
        self.seen_timestamps.clear()


def test_live_paper_reconnect_preserves_next_bar_execution_and_discards_gap():
    second_epoch_ready = threading.Event()

    factory = ScriptedEpochFactory(
        [
            {
                "script": [
                    _message(
                        10,
                        15,
                        10000,
                        500,
                        1,
                    ),
                    _message(
                        10,
                        20,
                        10100,
                        520,
                        2,
                    ),
                    _message(
                        10,
                        30,
                        10200,
                        530,
                        3,
                    ),
                ],
                "terminal_error": ConnectionError(
                    "transport lost"
                ),
            },
            {
                "script": [
                    _message(
                        10,
                        35,
                        10300,
                        540,
                        1,
                    ),
                    _message(
                        10,
                        45,
                        12000,
                        550,
                        2,
                    ),
                    _message(
                        10,
                        50,
                        12100,
                        560,
                        3,
                    ),
                    _message(
                        11,
                        0,
                        12200,
                        570,
                        4,
                    ),
                ],
                "ready_event": second_epoch_ready,
                "block_after": True,
            },
        ]
    )

    feed = AngelOneLiveCandleFeed(
        config=_config(),
        auth_token="Bearer jwt-token",
        feed_token="feed-token",
        symbol="RELIANCE",
        timeframe="15m",
        session_start=SESSION_START,
        websocket_factory=factory,
    )

    strategy = BuyFirstDeliveredCandleStrategy()
    session_end = _ts(11, 15)

    def now() -> datetime:
        assert second_epoch_ready.wait(
            timeout=1.0
        )
        return session_end

    session = run_live_paper_trading(
        feed=feed,
        strategy=strategy,
        runtime_context=RuntimeContext(
            execution_config=ExecutionConfig(
                slippage_enabled=False,
                brokerage_enabled=False,
            ),
        ),
        dataset_context=DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
            timezone="Asia/Kolkata",
        ),
        session_end=session_end,
        now=now,
        reconnect_attempts=2,
        reconnect_delay_seconds=0.0,
        clock_interval_seconds=0.0,
        initial_capital=100_000.0,
    )

    assert len(factory.sockets) == 2
    assert factory.plans == []

    assert strategy.seen_timestamps == [
        _ts(10, 15),
        _ts(10, 45),
        _ts(11, 0),
    ]

    position = (
        session.execution_engine
        .get_runtime_position("RELIANCE")
    )

    assert position is not None
    assert position.entry_time == _ts(10, 45)
    assert position.entry_price == 120.0
    assert position.entry_index == 1

    assert session.status == "STOPPED"
    assert feed.connected is False
    assert factory.sockets[1].closed.is_set()

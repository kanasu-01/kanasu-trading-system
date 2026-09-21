import threading
from datetime import datetime, time

import pytz

from core.broker.angelone_config import AngelOneConfig
from core.config.execution_config import ExecutionConfig
from core.entities.candle_series import CandleSeries
from core.market_data.angelone_live_candle_feed import (
    AngelOneLiveCandleFeed,
)
from core.market_data.live_candle_pipeline import (
    LiveCandlePipeline,
)
from core.market_data.live_market_update import (
    LiveMarketUpdate,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.paper_candle_processor import (
    PaperCandleProcessor,
)
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import SignalType


IST = pytz.timezone("Asia/Kolkata")
SESSION_START = time(9, 15)


def _ts(
    hour: int,
    minute: int,
    second: int = 0,
    millisecond: int = 0,
) -> datetime:
    return IST.localize(
        datetime(
            2026,
            1,
            2,
            hour,
            minute,
            second,
            millisecond * 1000,
        )
    )


def _update(
    *,
    hour: int,
    minute: int,
    second: int = 0,
    millisecond: int = 0,
    price: float,
    cumulative_volume: float,
    sequence: int,
) -> LiveMarketUpdate:
    return LiveMarketUpdate(
        timestamp=_ts(
            hour,
            minute,
            second,
            millisecond,
        ),
        price=price,
        cumulative_volume=cumulative_volume,
        sequence=sequence,
    )


def _message(
    *,
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
            _ts(
                hour,
                minute,
            ).timestamp()
            * 1000
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


class BuyFirstCompletedCandleStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(
            name="buy_first_completed_candle"
        )

    def on_new_candle(
        self,
        series: CandleSeries,
    ) -> SignalType | None:
        if len(series) == 1:
            return SignalType.BUY

        return None

    def reset(self) -> None:
        return None


class ManualSocket:
    def __init__(
        self,
        args,
        kwargs,
    ) -> None:
        self.args = args
        self.kwargs = kwargs

        self.on_open = None
        self.on_data = None
        self.on_error = None
        self.on_close = None

        self.opened = threading.Event()
        self.closed = threading.Event()
        self.subscribe_calls = []

    def connect(self) -> None:
        self.on_open(self)
        self.opened.set()

        if not self.closed.wait(timeout=2.0):
            raise RuntimeError(
                "manual test socket was not closed"
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

    def emit(self, message: dict) -> None:
        self.on_data(
            self,
            message,
        )


class ManualSocketFactory:
    def __init__(self) -> None:
        self.socket: ManualSocket | None = None

    def __call__(self, *args, **kwargs):
        if self.socket is not None:
            raise AssertionError(
                "unexpected second socket"
            )

        self.socket = ManualSocket(
            args=args,
            kwargs=kwargs,
        )
        return self.socket


def test_live_intent_executes_when_next_bar_open_is_observed():
    factory = ManualSocketFactory()

    feed = AngelOneLiveCandleFeed(
        config=_config(),
        auth_token="Bearer jwt-token",
        feed_token="feed-token",
        symbol="RELIANCE",
        timeframe="15m",
        session_start=SESSION_START,
        websocket_factory=factory,
    )

    processor = PaperCandleProcessor(
        strategy=BuyFirstCompletedCandleStrategy(),
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
        initial_capital=100_000.0,
        session_id="causal-validity",
    )

    provider_thread = threading.Thread(
        target=feed.subscribe,
        args=(
            processor.on_live_completed_candle,
            processor.on_live_market_update,
        ),
    )
    provider_thread.start()

    assert factory.socket is not None
    assert factory.socket.opened.wait(
        timeout=1.0
    )

    try:
        factory.socket.emit(
            _message(
                hour=10,
                minute=15,
                price_paise=10000,
                cumulative_volume=500,
                sequence=1,
            )
        )
        factory.socket.emit(
            _message(
                hour=10,
                minute=20,
                price_paise=10100,
                cumulative_volume=520,
                sequence=2,
            )
        )

        # This is the first authoritative observation of
        # the 10:30 bar. It simultaneously proves that the
        # 10:15-10:30 candle is complete.
        factory.socket.emit(
            _message(
                hour=10,
                minute=30,
                price_paise=12000,
                cumulative_volume=530,
                sequence=3,
            )
        )

        position = (
            processor.execution_engine
            .get_runtime_position("RELIANCE")
        )

        # A strategy decision based only on the completed
        # prior candle must execute now, at the observed
        # next-bar open. It must not wait until that new
        # candle itself completes.
        assert position is not None
        assert position.entry_time == _ts(
            10,
            30,
        )
        assert position.entry_price == 120.0
    finally:
        feed.close()
        provider_thread.join(timeout=1.0)

    assert not provider_thread.is_alive()


def test_wall_clock_does_not_advance_source_event_watermark():
    pipeline = LiveCandlePipeline(
        timeframe="15m",
        session_start=SESSION_START,
    )
    pipeline.begin_connection()

    assert pipeline.on_update(
        _update(
            hour=10,
            minute=20,
            second=0,
            millisecond=300,
            price=100.0,
            cumulative_volume=500.0,
            sequence=1,
        )
    ) is None

    # Local wall clock advances beyond an exchange event
    # that is still legitimately in flight over the network.
    assert pipeline.advance_time(
        _ts(
            10,
            20,
            0,
            500,
        )
    ) is None

    # This source event is newer than the previous source
    # event even though its exchange timestamp is behind
    # the local wall clock.
    assert pipeline.on_update(
        _update(
            hour=10,
            minute=20,
            second=0,
            millisecond=400,
            price=101.0,
            cumulative_volume=510.0,
            sequence=2,
        )
    ) is None


def test_intraday_wall_clock_does_not_finalize_before_late_source_tick():
    pipeline = LiveCandlePipeline(
        timeframe="15m",
        session_start=SESSION_START,
    )
    pipeline.begin_connection()

    assert pipeline.on_update(
        _update(
            hour=10,
            minute=15,
            price=100.0,
            cumulative_volume=500.0,
            sequence=1,
        )
    ) is None

    assert pipeline.on_update(
        _update(
            hour=10,
            minute=29,
            second=59,
            millisecond=800,
            price=101.0,
            cumulative_volume=520.0,
            sequence=2,
        )
    ) is None

    # Reaching the nominal boundary on the local clock is
    # not sufficient proof that every exchange event from
    # the prior interval has arrived.
    assert pipeline.advance_time(
        _ts(
            10,
            30,
        )
    ) is None

    # A legitimate final tick from the prior interval may
    # arrive just after the local clock crosses 10:30.
    assert pipeline.on_update(
        _update(
            hour=10,
            minute=29,
            second=59,
            millisecond=900,
            price=103.0,
            cumulative_volume=525.0,
            sequence=3,
        )
    ) is None

    # The first source event in the next interval now proves
    # the prior candle complete.
    candle = pipeline.on_update(
        _update(
            hour=10,
            minute=30,
            second=0,
            millisecond=100,
            price=104.0,
            cumulative_volume=530.0,
            sequence=4,
        )
    )

    assert candle is not None
    assert candle.timestamp == _ts(
        10,
        15,
    )
    assert candle.close == 103.0

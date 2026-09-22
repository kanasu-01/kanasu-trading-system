import threading
from datetime import datetime, time

import pytz

from core.broker.angelone_config import AngelOneConfig
from core.config.execution_config import ExecutionConfig
from core.entities.candle import Candle
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



def _new_m76_causal_processor() -> PaperCandleProcessor:
    return PaperCandleProcessor(
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
        session_id="m76-design-baseline",
    )


def test_live_execution_path_does_not_delegate_to_backtest_processor(
    monkeypatch,
) -> None:
    processor = _new_m76_causal_processor()

    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 15),
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        )
    )

    def reject_historical_path(**_kwargs):
        raise AssertionError(
            "live execution delegated to process_backtest_candle"
        )

    monkeypatch.setattr(
        processor.execution_engine,
        "process_backtest_candle",
        reject_historical_path,
    )

    processor.on_live_market_update(
        _update(
            hour=10,
            minute=30,
            price=120.0,
            cumulative_volume=1_100.0,
            sequence=2,
        ),
        True,
    )

    position = (
        processor.execution_engine
        .get_runtime_position("RELIANCE")
    )

    assert position is not None
    assert position.entry_time == _ts(10, 30)
    assert position.entry_price == 120.0


def test_live_completed_candle_marks_close_before_strategy_decision(
    monkeypatch,
) -> None:
    processor = _new_m76_causal_processor()

    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 15),
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        )
    )

    processor.on_live_market_update(
        _update(
            hour=10,
            minute=30,
            price=120.0,
            cumulative_volume=1_100.0,
            sequence=2,
        ),
        True,
    )

    assert (
        processor.execution_engine
        .get_runtime_position("RELIANCE")
        is not None
    )

    order = []
    original_mark = (
        processor.execution_engine
        .mark_open_position_to_market
    )

    def record_mark(*, symbol, price):
        order.append(("mark", price))
        return original_mark(
            symbol=symbol,
            price=price,
        )

    def record_decision(candle):
        order.append(("decision", candle.close))
        return None

    monkeypatch.setattr(
        processor.execution_engine,
        "mark_open_position_to_market",
        record_mark,
    )
    monkeypatch.setattr(
        processor.strategy_runner,
        "on_new_candle",
        record_decision,
    )

    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 30),
            open=120.0,
            high=124.0,
            low=119.0,
            close=123.0,
            volume=1_200.0,
        )
    )

    assert order == [
        ("mark", 123.0),
        ("decision", 123.0),
    ]



def test_live_entry_observation_is_not_reused_for_post_entry_stop() -> None:
    processor = PaperCandleProcessor(
        strategy=BuyFirstCompletedCandleStrategy(),
        runtime_context=RuntimeContext(
            execution_config=ExecutionConfig(
                slippage_pct=0.001,
                slippage_enabled=True,
                brokerage_enabled=False,
            ),
        ),
        dataset_context=DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
            timezone="Asia/Kolkata",
        ),
        initial_capital=100_000.0,
        session_id="m76-protective-causality",
    )

    # decision_close * 0.98 = 100.009, while the first observed
    # N+1 price is 100.0 and the slipped BUY fill is 100.1.
    # The opening observation existed before the position was created
    # and therefore must not immediately stop the new position.
    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 15),
            open=101.0,
            high=103.0,
            low=101.0,
            close=102.05,
            volume=1_000.0,
        )
    )

    processor.on_live_market_update(
        _update(
            hour=10,
            minute=30,
            price=100.0,
            cumulative_volume=1_100.0,
            sequence=2,
        ),
        True,
    )

    position = (
        processor.execution_engine
        .get_runtime_position("RELIANCE")
    )

    assert position is not None
    assert position.entry_price == 100.1
    assert position.stop_price == 100.009
    assert processor.execution_engine.completed_trades == []

    # A later, genuinely post-entry observation may enforce protection.
    processor.on_live_market_update(
        _update(
            hour=10,
            minute=30,
            second=1,
            price=99.5,
            cumulative_volume=1_101.0,
            sequence=3,
        ),
        False,
    )

    assert (
        processor.execution_engine
        .get_runtime_position("RELIANCE")
        is None
    )
    assert len(
        processor.execution_engine.completed_trades
    ) == 1
    assert (
        processor.execution_engine
        .completed_trades[0]
        .exit_reason
        == "STOP_LOSS"
    )



class FeedbackOrderingStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(name="feedback_ordering")
        self.events = []
        self.decisions = 0

    def on_new_candle(
        self,
        series: CandleSeries,
    ) -> SignalType | None:
        self.decisions += 1
        self.events.append(
            f"decision:{self.decisions}"
        )

        if self.decisions == 1:
            return SignalType.BUY

        return None

    def on_execution_feedback(
        self,
        feedback,
    ) -> None:
        self.events.append(
            f"feedback:{feedback.event_type.value}"
        )

    def reset(self) -> None:
        self.events.clear()
        self.decisions = 0


def test_live_entry_remains_bound_to_first_observed_next_bar_update():
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

    processor = _new_m76_causal_processor()

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

        assert position is not None
        assert position.entry_time == _ts(10, 30)
        assert position.entry_price == 120.0

        # Later N+1 observations alter the completed candle but must never
        # rewrite the already-observed execution timestamp or price.
        factory.socket.emit(
            _message(
                hour=10,
                minute=35,
                price_paise=11000,
                cumulative_volume=540,
                sequence=4,
            )
        )
        factory.socket.emit(
            _message(
                hour=10,
                minute=40,
                price_paise=13000,
                cumulative_volume=550,
                sequence=5,
            )
        )
        factory.socket.emit(
            _message(
                hour=10,
                minute=45,
                price_paise=12500,
                cumulative_volume=560,
                sequence=6,
            )
        )

        position = (
            processor.execution_engine
            .get_runtime_position("RELIANCE")
        )

        assert position is not None
        assert position.entry_time == _ts(10, 30)
        assert position.entry_price == 120.0

        completed_next = processor.series[-1]
        assert completed_next.timestamp == _ts(10, 30)
        assert completed_next.open == 120.0
        assert completed_next.low == 110.0
        assert completed_next.high == 130.0
    finally:
        feed.close()
        provider_thread.join(timeout=1.0)

    assert not provider_thread.is_alive()


def test_live_feedback_precedes_next_completed_candle_decision() -> None:
    strategy = FeedbackOrderingStrategy()

    processor = PaperCandleProcessor(
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
        initial_capital=100_000.0,
        session_id="m76-feedback-order",
    )

    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 15),
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        )
    )

    processor.on_live_market_update(
        _update(
            hour=10,
            minute=30,
            price=120.0,
            cumulative_volume=1_100.0,
            sequence=2,
        ),
        True,
    )

    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 30),
            open=120.0,
            high=123.0,
            low=119.0,
            close=122.0,
            volume=1_200.0,
        )
    )

    assert strategy.events == [
        "decision:1",
        "feedback:ENTRY_ACCEPTED",
        "decision:2",
    ]


def test_duplicate_live_open_observation_cannot_execute_intent_twice() -> None:
    strategy = FeedbackOrderingStrategy()

    processor = PaperCandleProcessor(
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
        initial_capital=100_000.0,
        session_id="m76-duplicate-open",
    )

    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 15),
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        )
    )

    opening_update = _update(
        hour=10,
        minute=30,
        price=120.0,
        cumulative_volume=1_100.0,
        sequence=2,
    )

    processor.on_live_market_update(
        opening_update,
        True,
    )

    # Defensive processor-level idempotence: even if an upstream source
    # were to repeat the callback, the consumed pending intent cannot enter
    # a second position.
    processor.on_live_market_update(
        opening_update,
        True,
    )

    assert strategy.events.count(
        "feedback:ENTRY_ACCEPTED"
    ) == 1

    position = (
        processor.execution_engine
        .get_runtime_position("RELIANCE")
    )

    assert position is not None
    assert position.entry_time == _ts(10, 30)
    assert len(
        processor.execution_engine.completed_trades
    ) == 0


def test_boundary_provider_and_clock_orderings_are_market_equivalent() -> None:
    def ready_pipeline() -> LiveCandlePipeline:
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
                millisecond=900,
                price=101.0,
                cumulative_volume=520.0,
                sequence=2,
            )
        ) is None

        return pipeline

    boundary = _update(
        hour=10,
        minute=30,
        second=0,
        millisecond=100,
        price=104.0,
        cumulative_volume=530.0,
        sequence=3,
    )
    later_clock = _ts(
        10,
        30,
        0,
        500,
    )

    provider_first = ready_pipeline()
    provider_first_result = (
        provider_first.on_update_with_transition(
            boundary
        )
    )
    assert provider_first.advance_time(
        later_clock
    ) is None

    clock_first = ready_pipeline()
    assert clock_first.advance_time(
        later_clock
    ) is None
    clock_first_result = (
        clock_first.on_update_with_transition(
            boundary
        )
    )

    assert provider_first_result == clock_first_result

    candle, accepted, opens_new_interval = (
        provider_first_result
    )

    assert accepted is True
    assert opens_new_interval is True
    assert candle is not None
    assert candle.timestamp == _ts(10, 15)
    assert candle.close == 101.0


def test_clock_advance_alone_cannot_execute_pending_live_intent() -> None:
    processor = _new_m76_causal_processor()

    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 15),
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        )
    )

    pipeline = LiveCandlePipeline(
        timeframe="15m",
        session_start=SESSION_START,
    )
    pipeline.begin_connection()

    assert pipeline.advance_time(
        _ts(10, 30)
    ) is None

    assert (
        processor.execution_engine
        .get_runtime_position("RELIANCE")
        is None
    )


def test_completed_live_candle_cannot_execute_unresolved_intent() -> None:
    processor = _new_m76_causal_processor()

    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 15),
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        )
    )

    assert (
        processor.execution_engine
        .get_runtime_position("RELIANCE")
        is None
    )

    # Deliberately call only the completed-candle path. It must never use
    # this candle's open as a retrospective execution trigger.
    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 30),
            open=120.0,
            high=125.0,
            low=90.0,
            close=122.0,
            volume=1_200.0,
        )
    )

    assert (
        processor.execution_engine
        .get_runtime_position("RELIANCE")
        is None
    )
    assert (
        processor.execution_engine
        .completed_trades
        == []
    )



def test_live_pending_intent_does_not_execute_after_skipped_next_interval() -> None:
    processor = _new_m76_causal_processor()

    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 15),
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        )
    )

    assert processor._pending_intent is not None

    # The required execution interval for the 10:15 decision is 10:30.
    # If the next observed interval is instead 11:00, M7.6 must preserve
    # that gap ambiguity rather than silently treating 11:00 as N+1.
    processor.on_live_market_update(
        _update(
            hour=11,
            minute=0,
            price=140.0,
            cumulative_volume=1_300.0,
            sequence=10,
        ),
        True,
    )

    assert (
        processor.execution_engine
        .get_runtime_position("RELIANCE")
        is None
    )

    # Gap resolution/cancellation belongs to M7.7. M7.6 must at least
    # retain the unresolved intent rather than consuming it as a valid
    # immediate-next-interval execution.
    assert processor._pending_intent is not None

def test_live_reconciliation_invalidates_pending_intent_while_flat() -> None:
    processor = _new_m76_causal_processor()

    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 15),
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        )
    )

    assert processor._pending_intent is not None
    assert (
        processor.execution_engine
        .get_runtime_position("RELIANCE")
        is None
    )

    processor.begin_live_reconciliation()

    assert processor._pending_intent is None
    assert (
        processor.execution_engine
        .get_runtime_position("RELIANCE")
        is None
    )
    assert processor.execution_engine.completed_trades == []


def test_live_reconciliation_replays_history_without_creating_trade_intent() -> None:
    class SignalEveryCandleStrategy(BaseStrategy):
        def __init__(self) -> None:
            super().__init__(
                name="signal_every_candle"
            )
            self.decision_lengths = []

        def on_new_candle(
            self,
            series: CandleSeries,
        ) -> SignalType | None:
            self.decision_lengths.append(len(series))
            return SignalType.BUY

        def reset(self) -> None:
            self.decision_lengths.clear()

    strategy = SignalEveryCandleStrategy()

    processor = PaperCandleProcessor(
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
        initial_capital=100_000.0,
        session_id="m77-reconciliation",
    )

    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 15),
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        )
    )

    assert processor._pending_intent is not None

    processor.begin_live_reconciliation()

    recovered = [
        Candle(
            timestamp=_ts(10, 30),
            open=101.0,
            high=103.0,
            low=100.0,
            close=102.0,
            volume=1_100.0,
        ),
        Candle(
            timestamp=_ts(10, 45),
            open=102.0,
            high=104.0,
            low=101.0,
            close=103.0,
            volume=1_200.0,
        ),
    ]

    processor.apply_live_reconciliation_candles(
        recovered
    )

    assert list(processor.series) == [
        Candle(
            timestamp=_ts(10, 15),
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        ),
        *recovered,
    ]
    assert strategy.decision_lengths == [1, 2, 3]
    assert processor._pending_intent is None
    assert (
        processor.execution_engine
        .get_runtime_position("RELIANCE")
        is None
    )
    assert processor.execution_engine.completed_trades == []

def test_live_reconciliation_quarantines_first_epoch_interval_and_requests_gap() -> None:
    processor = _new_m76_causal_processor()

    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 15),
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        )
    )

    processor.begin_live_reconciliation()

    # Reconnect first observes the already-in-progress 10:45 interval.
    # That interval is quarantined; no historical request is ready yet.
    request = processor.observe_live_reconciliation_update(
        _update(
            hour=10,
            minute=47,
            price=110.0,
            cumulative_volume=1_150.0,
            sequence=20,
        ),
        True,
    )

    assert request is None

    assert processor.observe_live_reconciliation_update(
        _update(
            hour=10,
            minute=50,
            price=111.0,
            cumulative_volume=1_170.0,
            sequence=21,
        ),
        False,
    ) is None

    # The first real later interval transition is 11:00. At this point
    # 10:30 and the quarantined 10:45 interval are historically complete.
    request = processor.observe_live_reconciliation_update(
        _update(
            hour=11,
            minute=0,
            price=112.0,
            cumulative_volume=1_200.0,
            sequence=22,
        ),
        True,
    )

    assert request == (
        _ts(10, 30),
        _ts(11, 0),
    )
    assert processor._pending_intent is None
    assert (
        processor.execution_engine
        .get_runtime_position("RELIANCE")
        is None
    )

def test_live_reconciliation_with_open_position_uses_history_for_state_only() -> None:
    processor = _new_m76_causal_processor()

    processor.on_live_completed_candle(
        Candle(
            timestamp=_ts(10, 15),
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        )
    )

    processor.on_live_market_update(
        _update(
            hour=10,
            minute=30,
            price=110.0,
            cumulative_volume=1_100.0,
            sequence=10,
        ),
        True,
    )

    position_before = (
        processor.execution_engine.get_runtime_position(
            "RELIANCE"
        )
    )

    assert position_before is not None
    stop_price = position_before.stop_price

    processor.begin_live_reconciliation()

    # Historical OHLC proves that price traded below the stop while the
    # provider was unavailable. That information repairs strategy state
    # only; it must never manufacture a retrospective protective exit.
    processor.apply_live_reconciliation_candles(
        [
            Candle(
                timestamp=_ts(10, 30),
                open=110.0,
                high=112.0,
                low=stop_price - 5.0,
                close=108.0,
                volume=1_200.0,
            )
        ],
        expected_start=_ts(10, 30),
        expected_end=_ts(10, 45),
    )

    position_after = (
        processor.execution_engine.get_runtime_position(
            "RELIANCE"
        )
    )

    assert position_after is position_before
    assert position_after.stop_price == stop_price
    assert processor.execution_engine.completed_trades == []

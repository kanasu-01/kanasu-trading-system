import pytest
from datetime import datetime, timedelta, timezone

from core.config.execution_config import ExecutionConfig
from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.market_data.mock_live_feed import MockLiveFeed
from core.market_data.live_market_update import LiveMarketUpdate
from core.runtime.dataset_context import DatasetContext
import core.runtime.paper_runtime as paper_runtime_module
from core.runtime.paper_candle_processor import (
    PaperCandleProcessor,
)
from core.runtime.paper_runtime import (
    run_live_paper_trading,
    run_paper_trading,
)
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import SignalType


INDIA = timezone(
    timedelta(hours=5, minutes=30),
    name="Asia/Kolkata",
)
START = datetime(2026, 1, 2, 9, 15, tzinfo=INDIA)


class BuyFirstCandleStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(name="buy_first_candle")

    def on_new_candle(
        self,
        series: CandleSeries,
    ) -> SignalType | None:
        if len(series) == 1:
            return SignalType.BUY
        return None

    def reset(self) -> None:
        return None


def test_paper_signal_executes_on_next_candle_not_decision_candle() -> None:
    candles = [
        Candle(
            timestamp=START,
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        ),
        Candle(
            timestamp=START + timedelta(minutes=15),
            open=110.0,
            high=112.0,
            low=109.0,
            close=111.0,
            volume=1_100.0,
        ),
    ]

    session = run_paper_trading(
        feed=MockLiveFeed(
            candles=candles,
            interval_seconds=0.0,
        ),
        strategy=BuyFirstCandleStrategy(),
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
    )

    position = session.execution_engine.get_runtime_position(
        "RELIANCE"
    )

    assert position is not None
    assert position.entry_time == candles[1].timestamp
    assert position.entry_price == candles[1].open
    assert position.entry_index == 1


class RecordingFeedbackStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(name="recording_feedback")
        self.events: list[str] = []

    def on_new_candle(
        self,
        series: CandleSeries,
    ) -> SignalType | None:
        self.events.append(f"decision:{len(series)}")
        if len(series) == 1:
            return SignalType.BUY
        return None

    def on_execution_feedback(self, feedback) -> None:
        self.events.append(
            f"feedback:{feedback.event_type.value}"
        )

    def reset(self) -> None:
        self.events.clear()


class BuyThenSellStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(name="buy_then_sell")

    def on_new_candle(
        self,
        series: CandleSeries,
    ) -> SignalType | None:
        if len(series) == 1:
            return SignalType.BUY
        if len(series) == 2:
            return SignalType.SELL
        return None

    def reset(self) -> None:
        return None


def test_paper_delivers_execution_feedback_before_current_candle_decision() -> None:
    strategy = RecordingFeedbackStrategy()
    candles = [
        Candle(
            timestamp=START,
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        ),
        Candle(
            timestamp=START + timedelta(minutes=15),
            open=110.0,
            high=112.0,
            low=109.0,
            close=111.0,
            volume=1_100.0,
        ),
    ]

    run_paper_trading(
        feed=MockLiveFeed(
            candles=candles,
            interval_seconds=0.0,
        ),
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
    )

    assert strategy.events == [
        "decision:1",
        "feedback:ENTRY_ACCEPTED",
        "decision:2",
    ]


def test_paper_buy_and_sell_execute_on_following_candle_opens() -> None:
    candles = [
        Candle(
            timestamp=START,
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        ),
        Candle(
            timestamp=START + timedelta(minutes=15),
            open=110.0,
            high=112.0,
            low=109.0,
            close=111.0,
            volume=1_100.0,
        ),
        Candle(
            timestamp=START + timedelta(minutes=30),
            open=105.0,
            high=107.0,
            low=104.0,
            close=106.0,
            volume=1_200.0,
        ),
    ]

    session = run_paper_trading(
        feed=MockLiveFeed(
            candles=candles,
            interval_seconds=0.0,
        ),
        strategy=BuyThenSellStrategy(),
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
    )

    assert session.execution_engine.get_runtime_position(
        "RELIANCE"
    ) is None

    assert len(session.execution_engine.completed_trades) == 1
    trade = session.execution_engine.completed_trades[0]

    assert trade.entry_time == candles[1].timestamp
    assert trade.entry_price == candles[1].open
    assert trade.exit_time == candles[2].timestamp
    assert trade.exit_price == candles[2].open
    assert trade.exit_reason == "STRATEGY_EXIT"


def test_paper_honors_runtime_risk_per_trade_percentage() -> None:
    candles = [
        Candle(
            timestamp=START,
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        ),
        Candle(
            timestamp=START + timedelta(minutes=15),
            open=110.0,
            high=112.0,
            low=109.0,
            close=111.0,
            volume=1_100.0,
        ),
    ]

    session = run_paper_trading(
        feed=MockLiveFeed(
            candles=candles,
            interval_seconds=0.0,
        ),
        strategy=BuyFirstCandleStrategy(),
        runtime_context=RuntimeContext(
            execution_config=ExecutionConfig(
                slippage_enabled=False,
                brokerage_enabled=False,
            ),
            risk_per_trade_pct=0.5,
        ),
        dataset_context=DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
            timezone="Asia/Kolkata",
        ),
        initial_capital=100_000.0,
    )

    position = session.execution_engine.get_runtime_position(
        "RELIANCE"
    )

    assert position is not None
    assert position.quantity == 41
    assert session.execution_engine.risk_manager.risk_per_trade_pct == 0.5



def test_live_paper_runtime_executes_at_observed_next_bar_open(
    monkeypatch,
) -> None:
    candles = [
        Candle(
            timestamp=START,
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        ),
        Candle(
            timestamp=START + timedelta(minutes=15),
            open=110.0,
            high=112.0,
            low=109.0,
            close=111.0,
            volume=1_100.0,
        ),
    ]
    feed = object()
    captured = {}

    class SpyLivePaperRuntime:
        def __init__(self, **kwargs):
            captured["supervisor_kwargs"] = kwargs
            self.on_candle = kwargs["on_candle"]
            self.on_market_update = kwargs["on_market_update"]

        def run_until(self, **kwargs):
            captured["run_until_kwargs"] = kwargs

            self.on_candle(candles[0])
            self.on_market_update(
                LiveMarketUpdate(
                    timestamp=candles[1].timestamp,
                    price=candles[1].open,
                    cumulative_volume=1_100.0,
                    sequence=1,
                ),
                True,
            )

    monkeypatch.setattr(
        paper_runtime_module,
        "LivePaperRuntime",
        SpyLivePaperRuntime,
    )

    session = run_live_paper_trading(
        feed=feed,
        strategy=BuyFirstCandleStrategy(),
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
        session_end=START + timedelta(hours=6),
        now=lambda: START,
        reconnect_attempts=3,
        reconnect_delay_seconds=1.5,
        clock_interval_seconds=0.5,
        initial_capital=100_000.0,
    )

    assert captured["supervisor_kwargs"]["feed"] is feed
    assert captured["supervisor_kwargs"]["reconnect_attempts"] == 3
    assert (
        captured["supervisor_kwargs"]["reconnect_delay_seconds"]
        == 1.5
    )
    assert (
        captured["run_until_kwargs"]["clock_interval_seconds"]
        == 0.5
    )

    position = session.execution_engine.get_runtime_position(
        "RELIANCE"
    )

    assert position is not None
    assert position.entry_time == candles[1].timestamp
    assert position.entry_price == candles[1].open
    assert position.entry_index == 1
    assert session.status == "STOPPED"


class WarmupRecordingStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(name="warmup_recording")
        self.decision_lengths = []

    def warmup_bars(self) -> int:
        return 3

    def on_new_candle(
        self,
        series: CandleSeries,
    ) -> SignalType | None:
        self.decision_lengths.append(len(series))
        return None

    def reset(self) -> None:
        self.decision_lengths.clear()


def test_live_processor_seeds_history_without_replaying_decisions() -> None:
    history = [
        Candle(
            timestamp=START - timedelta(minutes=30),
            open=97.0,
            high=99.0,
            low=96.0,
            close=98.0,
            volume=900.0,
        ),
        Candle(
            timestamp=START - timedelta(minutes=15),
            open=98.0,
            high=100.0,
            low=97.0,
            close=99.0,
            volume=950.0,
        ),
    ]
    strategy = WarmupRecordingStrategy()

    processor = PaperCandleProcessor(
        strategy=strategy,
        runtime_context=RuntimeContext(),
        dataset_context=DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
            timezone="Asia/Kolkata",
        ),
        initial_capital=100_000.0,
        session_id="warmup-test",
        history_bars=history,
    )

    # Historical bars establish indicator context only. They must not replay
    # decisions, signals, execution feedback, or portfolio mutations.
    assert len(processor.series) == 2
    assert list(processor.series) == history
    assert strategy.decision_lengths == []
    assert (
        processor.execution_engine
        .get_runtime_position("RELIANCE")
        is None
    )

    live_candle = Candle(
        timestamp=START,
        open=99.0,
        high=102.0,
        low=98.0,
        close=101.0,
        volume=1_000.0,
    )

    processor.on_live_completed_candle(
        live_candle
    )

    # The first actual live completed candle becomes the first strategy
    # decision callback, with historical context already present.
    assert len(processor.series) == 3
    assert strategy.decision_lengths == [3]


def test_live_paper_runtime_wires_reconciliation_callback(
    monkeypatch,
) -> None:
    captured = {}

    class SpyLivePaperRuntime:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_until(self, **kwargs):
            pass

    monkeypatch.setattr(
        paper_runtime_module,
        "LivePaperRuntime",
        SpyLivePaperRuntime,
    )

    run_live_paper_trading(
        feed=object(),
        strategy=BuyFirstCandleStrategy(),
        runtime_context=RuntimeContext(),
        dataset_context=DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
            timezone="Asia/Kolkata",
        ),
        session_end=START + timedelta(hours=6),
        now=lambda: START,
        reconnect_attempts=2,
        reconnect_delay_seconds=0.0,
        clock_interval_seconds=0.0,
        initial_capital=100_000.0,
    )

    assert callable(
        captured["on_reconciliation_required"]
    )

def test_live_paper_reconciliation_retrieves_completed_gap_history(
    monkeypatch,
) -> None:
    recovered = [
        Candle(
            timestamp=START + timedelta(minutes=15),
            open=101.0,
            high=103.0,
            low=100.0,
            close=102.0,
            volume=1_100.0,
        ),
        Candle(
            timestamp=START + timedelta(minutes=30),
            open=102.0,
            high=104.0,
            low=101.0,
            close=103.0,
            volume=1_200.0,
        ),
    ]

    class SpyHistoricalSource:
        def __init__(self) -> None:
            self.requests = []

        def retrieve(self, context, request):
            self.requests.append(
                (
                    context,
                    request.start,
                    request.end,
                )
            )
            return list(recovered)

    source = SpyHistoricalSource()
    captured = {}

    class SpyLivePaperRuntime:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_until(self, **kwargs):
            # Establish completed live state at 09:15.
            captured["on_candle"](
                Candle(
                    timestamp=START,
                    open=99.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1_000.0,
                )
            )

            # Provider gap begins. Pending intent must be invalidated.
            captured["on_reconciliation_required"]()

            # First reconnect observation lands inside the 09:45 interval.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=32),
                    price=110.0,
                    cumulative_volume=1_150.0,
                    sequence=20,
                ),
                True,
            )

            # 10:00 is the next genuine source interval transition.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=45),
                    price=112.0,
                    cumulative_volume=1_200.0,
                    sequence=21,
                ),
                True,
            )
            captured["on_clock"]()

    monkeypatch.setattr(
        paper_runtime_module,
        "LivePaperRuntime",
        SpyLivePaperRuntime,
    )

    session = run_live_paper_trading(
        feed=object(),
        strategy=BuyFirstCandleStrategy(),
        runtime_context=RuntimeContext(),
        dataset_context=DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
            timezone="Asia/Kolkata",
        ),
        historical_source=source,
        session_end=START + timedelta(hours=6),
        now=lambda: START,
        reconnect_attempts=2,
        reconnect_delay_seconds=0.0,
        clock_interval_seconds=0.0,
        initial_capital=100_000.0,
    )

    assert source.requests == [
        (
            DatasetContext(
                symbol="RELIANCE",
                timeframe="15m",
                timezone="Asia/Kolkata",
            ),
            START + timedelta(minutes=15),
            START + timedelta(minutes=45),
        )
    ]

    assert list(session.strategy_runner.series) == [
        Candle(
            timestamp=START,
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        ),
        *recovered,
    ]

    assert session.execution_engine.get_runtime_position(
        "RELIANCE"
    ) is None

def test_live_paper_reconciliation_rejects_incomplete_gap_history(
    monkeypatch,
) -> None:
    class IncompleteHistoricalSource:
        def retrieve(self, context, request):
            # [START + 15m, START + 45m) requires both the
            # +15m and +30m completed candles. Return only one.
            return [
                Candle(
                    timestamp=START + timedelta(minutes=15),
                    open=101.0,
                    high=103.0,
                    low=100.0,
                    close=102.0,
                    volume=1_100.0,
                )
            ]

    captured = {}

    class SpyLivePaperRuntime:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_until(self, **kwargs):
            captured["on_candle"](
                Candle(
                    timestamp=START,
                    open=99.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1_000.0,
                )
            )

            captured["on_reconciliation_required"]()

            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=32),
                    price=110.0,
                    cumulative_volume=1_150.0,
                    sequence=20,
                ),
                True,
            )

            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=45),
                    price=112.0,
                    cumulative_volume=1_200.0,
                    sequence=21,
                ),
                True,
            )
            captured["on_clock"]()

    monkeypatch.setattr(
        paper_runtime_module,
        "LivePaperRuntime",
        SpyLivePaperRuntime,
    )

    with pytest.raises(
        RuntimeError,
        match="incomplete live reconciliation history",
    ):
        run_live_paper_trading(
            feed=object(),
            strategy=BuyFirstCandleStrategy(),
            runtime_context=RuntimeContext(),
            dataset_context=DatasetContext(
                symbol="RELIANCE",
                timeframe="15m",
                timezone="Asia/Kolkata",
            ),
            historical_source=IncompleteHistoricalSource(),
            session_end=START + timedelta(hours=6),
            now=lambda: START,
            reconnect_attempts=2,
            reconnect_delay_seconds=0.0,
            clock_interval_seconds=0.0,
            initial_capital=100_000.0,
        )

def test_live_paper_reconciliation_resumes_only_after_fully_live_candle(
    monkeypatch,
) -> None:
    class AlwaysBuyStrategy(BaseStrategy):
        def __init__(self) -> None:
            super().__init__(name="always_buy")

        def on_new_candle(
            self,
            series: CandleSeries,
        ) -> SignalType | None:
            return SignalType.BUY

        def reset(self) -> None:
            return None

    recovered = [
        Candle(
            timestamp=START + timedelta(minutes=15),
            open=101.0,
            high=103.0,
            low=100.0,
            close=102.0,
            volume=1_100.0,
        ),
        Candle(
            timestamp=START + timedelta(minutes=30),
            open=102.0,
            high=104.0,
            low=101.0,
            close=103.0,
            volume=1_200.0,
        ),
    ]

    class HistoricalSource:
        def retrieve(self, context, request):
            return list(recovered)

    captured = {}

    class SpyLivePaperRuntime:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_until(self, **kwargs):
            # Initial live candle creates a BUY intent.
            captured["on_candle"](
                Candle(
                    timestamp=START,
                    open=99.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1_000.0,
                )
            )

            # The gap invalidates that intent.
            captured["on_reconciliation_required"]()

            # First reconnect observation is inside the quarantined 09:45 bar.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=32),
                    price=110.0,
                    cumulative_volume=1_150.0,
                    sequence=20,
                ),
                True,
            )

            # Provider completion of the quarantined 09:45 candle must not
            # enter strategy state directly.
            captured["on_candle"](
                Candle(
                    timestamp=START + timedelta(minutes=30),
                    open=109.0,
                    high=113.0,
                    low=108.0,
                    close=111.0,
                    volume=1_190.0,
                )
            )

            # 10:00 proves the historical gap is complete. Recovered BUY
            # signals are strategy-state-only and this source observation
            # must not execute any of them.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=45),
                    price=112.0,
                    cumulative_volume=1_200.0,
                    sequence=21,
                ),
                True,
            )
            captured["on_clock"]()

            # 10:00-10:15 is now the first fully observed live interval.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=50),
                    price=114.0,
                    cumulative_volume=1_250.0,
                    sequence=22,
                ),
                False,
            )

            captured["on_candle"](
                Candle(
                    timestamp=START + timedelta(minutes=45),
                    open=112.0,
                    high=116.0,
                    low=111.0,
                    close=115.0,
                    volume=1_300.0,
                )
            )

            # Only the strategy decision from the fully observed 10:00
            # candle may execute on the genuine 10:15 opening observation.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=60),
                    price=120.0,
                    cumulative_volume=1_350.0,
                    sequence=23,
                ),
                True,
            )

    monkeypatch.setattr(
        paper_runtime_module,
        "LivePaperRuntime",
        SpyLivePaperRuntime,
    )

    session = run_live_paper_trading(
        feed=object(),
        strategy=AlwaysBuyStrategy(),
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
        historical_source=HistoricalSource(),
        session_end=START + timedelta(hours=6),
        now=lambda: START,
        reconnect_attempts=2,
        reconnect_delay_seconds=0.0,
        clock_interval_seconds=0.0,
        initial_capital=100_000.0,
    )

    position = session.execution_engine.get_runtime_position(
        "RELIANCE"
    )

    assert position is not None
    assert position.entry_time == START + timedelta(minutes=60)
    assert position.entry_price == 120.0
    assert position.entry_index == 4

    assert [
        candle.timestamp
        for candle in session.strategy_runner.series
    ] == [
        START,
        START + timedelta(minutes=15),
        START + timedelta(minutes=30),
        START + timedelta(minutes=45),
    ]

    assert session.execution_engine.completed_trades == []

def test_live_paper_reconciliation_protects_open_position_from_first_reconnect_tick(
    monkeypatch,
) -> None:
    captured = {}

    class SpyLivePaperRuntime:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_until(self, **kwargs):
            # 09:15 strategy decision creates a pending BUY.
            captured["on_candle"](
                Candle(
                    timestamp=START,
                    open=99.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1_000.0,
                )
            )

            # 09:30 observed live price executes the entry at 110.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=15),
                    price=110.0,
                    cumulative_volume=1_100.0,
                    sequence=10,
                ),
                True,
            )

            position = captured_session_processor[
                "processor"
            ].execution_engine.get_runtime_position(
                "RELIANCE"
            )
            assert position is not None
            assert position.stop_price == pytest.approx(98.0)

            # Provider gap: freeze new strategy execution, but preserve
            # the already-open position.
            captured["on_reconciliation_required"]()

            # First accepted reconnect tick is currently below the stop.
            # Protection must act on this live price immediately rather
            # than waiting for historical reconstruction.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=32),
                    price=95.0,
                    cumulative_volume=1_150.0,
                    sequence=20,
                ),
                True,
            )

    captured_session_processor = {}

    original_processor = paper_runtime_module.PaperCandleProcessor

    class CapturingProcessor(original_processor):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            captured_session_processor["processor"] = self

    monkeypatch.setattr(
        paper_runtime_module,
        "PaperCandleProcessor",
        CapturingProcessor,
    )
    monkeypatch.setattr(
        paper_runtime_module,
        "LivePaperRuntime",
        SpyLivePaperRuntime,
    )

    session = run_live_paper_trading(
        feed=object(),
        strategy=BuyFirstCandleStrategy(),
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
        historical_source=object(),
        session_end=START + timedelta(hours=6),
        now=lambda: START,
        reconnect_attempts=2,
        reconnect_delay_seconds=0.0,
        clock_interval_seconds=0.0,
        initial_capital=100_000.0,
    )

    assert session.execution_engine.get_runtime_position(
        "RELIANCE"
    ) is None

    assert len(session.execution_engine.completed_trades) == 1
    trade = session.execution_engine.completed_trades[0]

    assert trade.entry_time == START + timedelta(minutes=15)
    assert trade.entry_price == 110.0
    assert trade.exit_time == START + timedelta(minutes=32)
    assert trade.exit_price == 95.0
    assert trade.exit_reason == "STOP_LOSS"


def test_live_paper_reconciliation_ignores_historical_stop_breach_when_current_price_is_safe(
    monkeypatch,
) -> None:
    recovered = [
        Candle(
            timestamp=START + timedelta(minutes=15),
            open=110.0,
            high=112.0,
            low=90.0,
            close=104.0,
            volume=1_150.0,
        ),
        Candle(
            timestamp=START + timedelta(minutes=30),
            open=104.0,
            high=108.0,
            low=94.0,
            close=106.0,
            volume=1_200.0,
        ),
    ]

    class HistoricalSource:
        def retrieve(self, context, request):
            return list(recovered)

    captured = {}
    processor_holder = {}

    original_processor = paper_runtime_module.PaperCandleProcessor

    class CapturingProcessor(original_processor):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            processor_holder["processor"] = self

    class SpyLivePaperRuntime:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_until(self, **kwargs):
            captured["on_candle"](
                Candle(
                    timestamp=START,
                    open=99.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1_000.0,
                )
            )

            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=15),
                    price=110.0,
                    cumulative_volume=1_100.0,
                    sequence=10,
                ),
                True,
            )

            position = (
                processor_holder["processor"]
                .execution_engine
                .get_runtime_position("RELIANCE")
            )

            assert position is not None
            assert position.stop_price == pytest.approx(98.0)

            captured["on_reconciliation_required"]()

            # Reconnect price is currently above the stop, so keep holding.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=32),
                    price=105.0,
                    cumulative_volume=1_220.0,
                    sequence=20,
                ),
                True,
            )

            # Still safe at the genuine next interval boundary. This triggers
            # historical recovery. Recovered OHLC contains lows below the
            # stop, but those historical lows must not create an exit.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=45),
                    price=106.0,
                    cumulative_volume=1_250.0,
                    sequence=21,
                ),
                True,
            )
            captured["on_clock"]()

    monkeypatch.setattr(
        paper_runtime_module,
        "PaperCandleProcessor",
        CapturingProcessor,
    )
    monkeypatch.setattr(
        paper_runtime_module,
        "LivePaperRuntime",
        SpyLivePaperRuntime,
    )

    session = run_live_paper_trading(
        feed=object(),
        strategy=BuyFirstCandleStrategy(),
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
        historical_source=HistoricalSource(),
        session_end=START + timedelta(hours=6),
        now=lambda: START,
        reconnect_attempts=2,
        reconnect_delay_seconds=0.0,
        clock_interval_seconds=0.0,
        initial_capital=100_000.0,
    )

    position = session.execution_engine.get_runtime_position(
        "RELIANCE"
    )

    assert position is not None
    assert position.entry_time == START + timedelta(minutes=15)
    assert position.entry_price == 110.0
    assert position.stop_price == pytest.approx(98.0)
    assert session.execution_engine.completed_trades == []

def test_live_paper_reconciliation_keeps_protecting_position_on_later_live_ticks(
    monkeypatch,
) -> None:
    captured = {}
    processor_holder = {}

    original_processor = paper_runtime_module.PaperCandleProcessor

    class CapturingProcessor(original_processor):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            processor_holder["processor"] = self

    class SpyLivePaperRuntime:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_until(self, **kwargs):
            captured["on_candle"](
                Candle(
                    timestamp=START,
                    open=99.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1_000.0,
                )
            )

            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=15),
                    price=110.0,
                    cumulative_volume=1_100.0,
                    sequence=10,
                ),
                True,
            )

            position = (
                processor_holder["processor"]
                .execution_engine
                .get_runtime_position("RELIANCE")
            )

            assert position is not None
            assert position.stop_price == pytest.approx(98.0)

            captured["on_reconciliation_required"]()

            # First reconnect tick is safe. Keep holding.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=32),
                    price=105.0,
                    cumulative_volume=1_150.0,
                    sequence=20,
                ),
                True,
            )

            position = (
                processor_holder["processor"]
                .execution_engine
                .get_runtime_position("RELIANCE")
            )
            assert position is not None

            # A later real live tick crosses the stop while historical
            # reconciliation is still incomplete. Exit immediately using
            # this currently observed live price.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=34),
                    price=96.0,
                    cumulative_volume=1_175.0,
                    sequence=21,
                ),
                False,
            )

    monkeypatch.setattr(
        paper_runtime_module,
        "PaperCandleProcessor",
        CapturingProcessor,
    )
    monkeypatch.setattr(
        paper_runtime_module,
        "LivePaperRuntime",
        SpyLivePaperRuntime,
    )

    session = run_live_paper_trading(
        feed=object(),
        strategy=BuyFirstCandleStrategy(),
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
        historical_source=object(),
        session_end=START + timedelta(hours=6),
        now=lambda: START,
        reconnect_attempts=2,
        reconnect_delay_seconds=0.0,
        clock_interval_seconds=0.0,
        initial_capital=100_000.0,
    )

    assert session.execution_engine.get_runtime_position(
        "RELIANCE"
    ) is None

    assert len(session.execution_engine.completed_trades) == 1
    trade = session.execution_engine.completed_trades[0]

    assert trade.entry_price == 110.0
    assert trade.exit_time == START + timedelta(minutes=34)
    assert trade.exit_price == 96.0
    assert trade.exit_reason == "STOP_LOSS"

def test_live_paper_history_failure_does_not_disable_open_position_protection(
    monkeypatch,
) -> None:
    class FailingHistoricalSource:
        def __init__(self) -> None:
            self.calls = 0

        def retrieve(self, context, request):
            self.calls += 1
            raise RuntimeError(
                "historical recovery unavailable"
            )

    source = FailingHistoricalSource()
    captured = {}
    processor_holder = {}

    original_processor = paper_runtime_module.PaperCandleProcessor

    class CapturingProcessor(original_processor):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            processor_holder["processor"] = self

    class SpyLivePaperRuntime:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_until(self, **kwargs):
            captured["on_candle"](
                Candle(
                    timestamp=START,
                    open=99.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1_000.0,
                )
            )

            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=15),
                    price=110.0,
                    cumulative_volume=1_100.0,
                    sequence=10,
                ),
                True,
            )

            position = (
                processor_holder["processor"]
                .execution_engine
                .get_runtime_position("RELIANCE")
            )
            assert position is not None
            assert position.stop_price == pytest.approx(98.0)

            captured["on_reconciliation_required"]()

            # First reconnect tick is safe.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=32),
                    price=105.0,
                    cumulative_volume=1_150.0,
                    sequence=20,
                ),
                True,
            )

            # The genuine next boundary makes historical recovery possible,
            # but the historical service is temporarily unavailable.
            # This must not terminate live protective monitoring.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=45),
                    price=104.0,
                    cumulative_volume=1_200.0,
                    sequence=21,
                ),
                True,
            )
            captured["on_clock"]()

            # A subsequent currently observed live tick crosses the stop.
            # The position must still be protected despite failed history.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=47),
                    price=96.0,
                    cumulative_volume=1_225.0,
                    sequence=22,
                ),
                False,
            )

    monkeypatch.setattr(
        paper_runtime_module,
        "PaperCandleProcessor",
        CapturingProcessor,
    )
    monkeypatch.setattr(
        paper_runtime_module,
        "LivePaperRuntime",
        SpyLivePaperRuntime,
    )

    session = run_live_paper_trading(
        feed=object(),
        strategy=BuyFirstCandleStrategy(),
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
        historical_source=source,
        session_end=START + timedelta(hours=6),
        now=lambda: START,
        reconnect_attempts=2,
        reconnect_delay_seconds=0.0,
        clock_interval_seconds=0.0,
        initial_capital=100_000.0,
    )

    assert source.calls == 1
    assert session.execution_engine.get_runtime_position(
        "RELIANCE"
    ) is None

    assert len(session.execution_engine.completed_trades) == 1
    trade = session.execution_engine.completed_trades[0]

    assert trade.exit_time == START + timedelta(minutes=47)
    assert trade.exit_price == 96.0
    assert trade.exit_reason == "STOP_LOSS"

def test_live_paper_reconciliation_retries_history_after_temporary_failure(
    monkeypatch,
) -> None:
    requests = []

    class RecoveringHistoricalSource:
        def retrieve(self, context, request):
            requests.append(
                (
                    request.start,
                    request.end,
                )
            )

            if len(requests) == 1:
                raise RuntimeError(
                    "historical recovery temporarily unavailable"
                )

            return [
                Candle(
                    timestamp=START + timedelta(minutes=15),
                    open=110.0,
                    high=112.0,
                    low=90.0,
                    close=104.0,
                    volume=1_150.0,
                ),
                Candle(
                    timestamp=START + timedelta(minutes=30),
                    open=104.0,
                    high=108.0,
                    low=94.0,
                    close=106.0,
                    volume=1_200.0,
                ),
                Candle(
                    timestamp=START + timedelta(minutes=45),
                    open=106.0,
                    high=109.0,
                    low=103.0,
                    close=108.0,
                    volume=1_250.0,
                ),
            ]

    source = RecoveringHistoricalSource()
    captured = {}
    processor_holder = {}

    original_processor = paper_runtime_module.PaperCandleProcessor

    class CapturingProcessor(original_processor):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            processor_holder["processor"] = self

    class SpyLivePaperRuntime:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_until(self, **kwargs):
            captured["on_candle"](
                Candle(
                    timestamp=START,
                    open=99.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1_000.0,
                )
            )

            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=15),
                    price=110.0,
                    cumulative_volume=1_100.0,
                    sequence=10,
                ),
                True,
            )

            position = (
                processor_holder["processor"]
                .execution_engine
                .get_runtime_position("RELIANCE")
            )
            assert position is not None
            assert position.stop_price == pytest.approx(98.0)

            captured["on_reconciliation_required"]()

            # First reconnect interval is quarantined.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=32),
                    price=105.0,
                    cumulative_volume=1_150.0,
                    sequence=20,
                ),
                True,
            )

            # First recovery attempt at 10:00 fails temporarily.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=45),
                    price=106.0,
                    cumulative_volume=1_200.0,
                    sequence=21,
                ),
                True,
            )
            captured["on_clock"]()

            # This completed live candle is still suppressed because
            # reconciliation has not succeeded yet.
            captured["on_candle"](
                Candle(
                    timestamp=START + timedelta(minutes=45),
                    open=106.0,
                    high=109.0,
                    low=103.0,
                    close=108.0,
                    volume=1_250.0,
                )
            )

            # The next genuine boundary retries recovery. The historical
            # range now extends through the completed 10:00 candle.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=60),
                    price=109.0,
                    cumulative_volume=1_300.0,
                    sequence=22,
                ),
                True,
            )
            captured["on_clock"]()

    monkeypatch.setattr(
        paper_runtime_module,
        "PaperCandleProcessor",
        CapturingProcessor,
    )
    monkeypatch.setattr(
        paper_runtime_module,
        "LivePaperRuntime",
        SpyLivePaperRuntime,
    )

    session = run_live_paper_trading(
        feed=object(),
        strategy=BuyFirstCandleStrategy(),
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
        historical_source=source,
        session_end=START + timedelta(hours=6),
        now=lambda: START,
        reconnect_attempts=2,
        reconnect_delay_seconds=0.0,
        clock_interval_seconds=0.0,
        initial_capital=100_000.0,
    )

    assert requests == [
        (
            START + timedelta(minutes=15),
            START + timedelta(minutes=45),
        ),
        (
            START + timedelta(minutes=15),
            START + timedelta(minutes=60),
        ),
    ]

    assert [
        candle.timestamp
        for candle in session.strategy_runner.series
    ] == [
        START,
        START + timedelta(minutes=15),
        START + timedelta(minutes=30),
        START + timedelta(minutes=45),
    ]

    position = session.execution_engine.get_runtime_position(
        "RELIANCE"
    )
    assert position is not None
    assert position.entry_price == 110.0
    assert session.execution_engine.completed_trades == []

def test_live_paper_history_recovery_runs_off_provider_callback_thread() -> None:
    import threading

    calling_thread = threading.current_thread()

    class ThreadRecordingHistoricalSource:
        def __init__(self) -> None:
            self.called = threading.Event()
            self.thread = None

        def retrieve(self, context, request):
            self.thread = threading.current_thread()
            self.called.set()

            return [
                Candle(
                    timestamp=START + timedelta(minutes=15),
                    open=110.0,
                    high=112.0,
                    low=104.0,
                    close=106.0,
                    volume=1_150.0,
                ),
                Candle(
                    timestamp=START + timedelta(minutes=30),
                    open=106.0,
                    high=109.0,
                    low=103.0,
                    close=108.0,
                    volume=1_200.0,
                ),
            ]

    source = ThreadRecordingHistoricalSource()

    class ReconnectingFeed:
        def __init__(self) -> None:
            self.boundary_started = threading.Event()
            self.closed = threading.Event()
            self.on_candle = None
            self.on_market_update = None

        def subscribe(
            self,
            on_candle,
            on_market_update=None,
        ) -> None:
            self.on_candle = on_candle
            self.on_market_update = on_market_update

            on_candle(
                Candle(
                    timestamp=START,
                    open=99.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1_000.0,
                )
            )

            on_market_update(
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=15),
                    price=110.0,
                    cumulative_volume=1_100.0,
                    sequence=10,
                ),
                True,
            )

            # Returning represents the provider disconnect.
            return

        def reconnect(self) -> None:
            self.on_market_update(
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=32),
                    price=105.0,
                    cumulative_volume=1_150.0,
                    sequence=20,
                ),
                True,
            )

            self.on_market_update(
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=45),
                    price=106.0,
                    cumulative_volume=1_200.0,
                    sequence=21,
                ),
                True,
            )

            self.boundary_started.set()

            self.closed.wait(timeout=1.0)

        def advance_time(self, timestamp) -> None:
            pass

        def close(self) -> None:
            self.closed.set()

    feed = ReconnectingFeed()
    now_calls = 0
    session_end = START + timedelta(hours=6)

    def now():
        nonlocal now_calls
        now_calls += 1

        if now_calls == 1:
            assert feed.boundary_started.wait(timeout=1.0)
            return START + timedelta(minutes=46)

        assert source.called.wait(timeout=1.0)
        return session_end

    session = run_live_paper_trading(
        feed=feed,
        strategy=BuyFirstCandleStrategy(),
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
        historical_source=source,
        session_end=session_end,
        now=now,
        reconnect_attempts=2,
        reconnect_delay_seconds=0.0,
        clock_interval_seconds=0.0,
        initial_capital=100_000.0,
    )

    assert source.called.is_set()
    assert source.thread is calling_thread

    position = session.execution_engine.get_runtime_position(
        "RELIANCE"
    )
    assert position is not None
    assert position.entry_price == 110.0

def test_live_paper_reconciliation_requarantines_each_reconnect_epoch(
    monkeypatch,
) -> None:
    requests = []

    recovered = [
        Candle(
            timestamp=START + timedelta(minutes=15),
            open=101.0,
            high=103.0,
            low=100.0,
            close=102.0,
            volume=1_100.0,
        ),
        Candle(
            timestamp=START + timedelta(minutes=30),
            open=102.0,
            high=104.0,
            low=101.0,
            close=103.0,
            volume=1_200.0,
        ),
        Candle(
            timestamp=START + timedelta(minutes=45),
            open=103.0,
            high=105.0,
            low=102.0,
            close=104.0,
            volume=1_300.0,
        ),
    ]

    class HistoricalSource:
        def retrieve(self, context, request):
            requests.append(
                (
                    request.start,
                    request.end,
                )
            )
            return list(recovered)

    captured = {}

    class SpyLivePaperRuntime:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_until(self, **kwargs):
            captured["on_candle"](
                Candle(
                    timestamp=START,
                    open=99.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1_000.0,
                )
            )

            # First provider gap.
            captured["on_reconciliation_required"]()

            # First interval of reconnect epoch 1 is quarantined.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=32),
                    price=110.0,
                    cumulative_volume=1_150.0,
                    sequence=20,
                ),
                True,
            )

            # This genuine boundary schedules recovery for epoch 1,
            # but the clock has not processed it yet.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=45),
                    price=111.0,
                    cumulative_volume=1_200.0,
                    sequence=21,
                ),
                True,
            )

            # The provider disconnects again before that recovery runs.
            # The stale epoch-1 recovery request must be discarded.
            captured["on_reconciliation_required"]()

            # First interval of reconnect epoch 2 must be quarantined again.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=47),
                    price=112.0,
                    cumulative_volume=1_225.0,
                    sequence=30,
                ),
                True,
            )

            captured["on_clock"]()

            # No historical retrieval is allowed from the stale epoch-1
            # request or from the first observation of epoch 2.
            assert requests == []

            # Only the next genuine transition in epoch 2 proves a valid
            # completed recovery range.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=60),
                    price=113.0,
                    cumulative_volume=1_300.0,
                    sequence=31,
                ),
                True,
            )

            captured["on_clock"]()

    monkeypatch.setattr(
        paper_runtime_module,
        "LivePaperRuntime",
        SpyLivePaperRuntime,
    )

    session = run_live_paper_trading(
        feed=object(),
        strategy=BuyFirstCandleStrategy(),
        runtime_context=RuntimeContext(),
        dataset_context=DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
            timezone="Asia/Kolkata",
        ),
        historical_source=HistoricalSource(),
        session_end=START + timedelta(hours=6),
        now=lambda: START,
        reconnect_attempts=2,
        reconnect_delay_seconds=0.0,
        clock_interval_seconds=0.0,
        initial_capital=100_000.0,
    )

    assert requests == [
        (
            START + timedelta(minutes=15),
            START + timedelta(minutes=60),
        )
    ]

    assert [
        candle.timestamp
        for candle in session.strategy_runner.series
    ] == [
        START,
        START + timedelta(minutes=15),
        START + timedelta(minutes=30),
        START + timedelta(minutes=45),
    ]

    assert session.execution_engine.get_runtime_position(
        "RELIANCE"
    ) is None

def test_live_paper_ignores_stale_history_failure_after_new_provider_gap(
    monkeypatch,
) -> None:
    import threading

    retrieval_started = threading.Event()
    release_retrieval = threading.Event()
    clock_failures = []
    captured = {}

    class BlockingFailingHistoricalSource:
        def retrieve(self, context, request):
            retrieval_started.set()

            assert release_retrieval.wait(timeout=1.0)

            raise RuntimeError(
                "obsolete historical recovery failed"
            )

    class SpyLivePaperRuntime:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def run_until(self, **kwargs):
            captured["on_candle"](
                Candle(
                    timestamp=START,
                    open=99.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1_000.0,
                )
            )

            # Epoch 1 begins.
            captured["on_reconciliation_required"]()

            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=32),
                    price=105.0,
                    cumulative_volume=1_150.0,
                    sequence=20,
                ),
                True,
            )

            # This boundary schedules historical request A.
            captured["on_market_update"](
                LiveMarketUpdate(
                    timestamp=START + timedelta(minutes=45),
                    price=106.0,
                    cumulative_volume=1_200.0,
                    sequence=21,
                ),
                True,
            )

            def run_clock() -> None:
                try:
                    captured["on_clock"]()
                except Exception as exc:
                    clock_failures.append(exc)

            clock_thread = threading.Thread(
                target=run_clock,
                name="test-reconciliation-clock",
            )
            clock_thread.start()

            assert retrieval_started.wait(timeout=1.0)

            # A second provider gap supersedes request A while A is
            # still in flight.
            captured["on_reconciliation_required"]()

            release_retrieval.set()
            clock_thread.join(timeout=1.0)

            assert not clock_thread.is_alive()

    monkeypatch.setattr(
        paper_runtime_module,
        "LivePaperRuntime",
        SpyLivePaperRuntime,
    )

    session = run_live_paper_trading(
        feed=object(),
        strategy=BuyFirstCandleStrategy(),
        runtime_context=RuntimeContext(),
        dataset_context=DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
            timezone="Asia/Kolkata",
        ),
        historical_source=BlockingFailingHistoricalSource(),
        session_end=START + timedelta(hours=6),
        now=lambda: START,
        reconnect_attempts=2,
        reconnect_delay_seconds=0.0,
        clock_interval_seconds=0.0,
        initial_capital=100_000.0,
    )

    assert clock_failures == []
    assert session.execution_engine.get_runtime_position(
        "RELIANCE"
    ) is None

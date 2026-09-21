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

import re
from types import SimpleNamespace

import pytest

import core.execution.trade_execution_engine as execution_module
import core.runtime.paper_runtime as paper_runtime_module
from core.paper_trading.paper_trading_session import PaperTradingSession
from core.runtime.dataset_context import DatasetContext
from core.runtime.paper_runtime import (
    run_live_paper_trading,
    run_paper_trading,
)
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy


MOCK_SESSION_ID = re.compile(
    r"^paper-mock-\d{8}-\d{6}-RELIANCE-[0-9a-f]{8}$"
)
LIVE_SESSION_ID = re.compile(
    r"^paper-live-\d{8}-\d{6}-RELIANCE-[0-9a-f]{8}$"
)


class NoSignalStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(name="no_signal")

    def on_new_candle(self, series):
        return None

    def reset(self) -> None:
        pass


class EmptyFeed:
    def subscribe(self, on_candle) -> None:
        return None


class FailingFeed:
    def subscribe(self, on_candle) -> None:
        raise ValueError("paper feed failed")


class NoopJournal:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id

    def log_trade(self, trade) -> None:
        pass


def _dataset_context() -> DatasetContext:
    return DatasetContext(
        symbol="RELIANCE",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )


def test_paper_session_snapshot_reads_authoritative_runtime_state() -> None:
    session = PaperTradingSession(
        session_id="paper-test",
        strategy_name="test-strategy",
        symbol="RELIANCE",
        initial_capital=100_000.0,
    )

    position = SimpleNamespace(
        symbol="RELIANCE",
        direction="LONG",
        quantity=10,
        entry_time=SimpleNamespace(
            isoformat=lambda: "2026-01-02T10:00:00+05:30"
        ),
        entry_price=101.5,
        stop_price=98.0,
    )
    portfolio_state = SimpleNamespace(
        cash=98_985.0,
        position_size=10.0,
        position_value=1_020.0,
        equity=100_005.0,
        realized_pnl=0.0,
        unrealized_pnl=5.0,
        total_pnl=5.0,
        peak_equity=100_005.0,
        drawdown=0.0,
    )
    engine = SimpleNamespace(
        portfolio_manager=SimpleNamespace(
            snapshot=lambda: portfolio_state,
        ),
        get_runtime_position=lambda symbol: position,
        completed_trades=[object(), object()],
        last_execution_event="BUY",
        last_execution_price=101.5,
        last_execution_quantity=10,
    )

    session.execution_engine = engine
    session.start()

    snapshot = session.snapshot()

    assert snapshot.session_id == "paper-test"
    assert snapshot.status == "RUNNING"
    assert snapshot.initial_capital == 100_000.0
    assert snapshot.cash == 98_985.0
    assert snapshot.position_value == 1_020.0
    assert snapshot.equity == 100_005.0
    assert snapshot.realized_pnl == 0.0
    assert snapshot.unrealized_pnl == 5.0
    assert snapshot.total_pnl == 5.0
    assert snapshot.completed_trade_count == 2
    assert snapshot.last_execution_event == "BUY"
    assert snapshot.last_execution_price == 101.5
    assert snapshot.last_execution_quantity == 10

    assert snapshot.active_position is not None
    assert snapshot.active_position.symbol == "RELIANCE"
    assert snapshot.active_position.direction == "LONG"
    assert snapshot.active_position.quantity == 10
    assert snapshot.active_position.entry_price == 101.5
    assert snapshot.active_position.stop_price == 98.0


def test_paper_session_failure_is_terminal_and_visible() -> None:
    session = PaperTradingSession(
        session_id="paper-test",
        strategy_name="test-strategy",
        symbol="RELIANCE",
        initial_capital=100_000.0,
    )
    session.start()

    session.fail(ValueError("provider boom"))

    assert session.status == "FAILED"
    assert session.stopped_at is not None

    snapshot = session.snapshot()
    assert snapshot.failure_type == "ValueError"
    assert snapshot.failure_message == "provider boom"

    session.stop()

    assert session.status == "FAILED"


def test_mock_paper_runtime_stops_after_feed_completion(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        execution_module,
        "TradeJournal",
        NoopJournal,
    )

    session = run_paper_trading(
        feed=EmptyFeed(),
        strategy=NoSignalStrategy(),
        runtime_context=RuntimeContext(),
        dataset_context=_dataset_context(),
        initial_capital=100_000.0,
    )

    assert session.status == "STOPPED"
    assert session.stopped_at is not None


def test_mock_paper_runtime_uses_human_readable_unique_session_ids(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        execution_module,
        "TradeJournal",
        NoopJournal,
    )

    first = run_paper_trading(
        feed=EmptyFeed(),
        strategy=NoSignalStrategy(),
        runtime_context=RuntimeContext(),
        dataset_context=_dataset_context(),
        initial_capital=100_000.0,
    )
    second = run_paper_trading(
        feed=EmptyFeed(),
        strategy=NoSignalStrategy(),
        runtime_context=RuntimeContext(),
        dataset_context=_dataset_context(),
        initial_capital=100_000.0,
    )

    assert first.session_id != second.session_id
    assert MOCK_SESSION_ID.fullmatch(first.session_id)
    assert MOCK_SESSION_ID.fullmatch(second.session_id)

    assert first.execution_engine.session_id == first.session_id
    assert second.execution_engine.session_id == second.session_id
    assert first.execution_engine.journal.session_id == first.session_id
    assert second.execution_engine.journal.session_id == second.session_id


def test_mock_paper_runtime_marks_failure_before_reraising(
    monkeypatch,
) -> None:
    holder = {}

    class CapturingSession(PaperTradingSession):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            holder["session"] = self

    monkeypatch.setattr(
        execution_module,
        "TradeJournal",
        NoopJournal,
    )
    monkeypatch.setattr(
        paper_runtime_module,
        "PaperTradingSession",
        CapturingSession,
    )

    with pytest.raises(
        ValueError,
        match="paper feed failed",
    ):
        run_paper_trading(
            feed=FailingFeed(),
            strategy=NoSignalStrategy(),
            runtime_context=RuntimeContext(),
            dataset_context=_dataset_context(),
            initial_capital=100_000.0,
        )

    session = holder["session"]

    assert session.status == "FAILED"
    assert session.snapshot().failure_type == "ValueError"
    assert session.snapshot().failure_message == "paper feed failed"


def test_live_paper_runtime_marks_failure_and_uses_readable_id(
    monkeypatch,
) -> None:
    holder = {}

    class CapturingSession(PaperTradingSession):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            holder["session"] = self

    class FailingLivePaperRuntime:
        def __init__(self, **kwargs) -> None:
            pass

        def run_until(self, **kwargs) -> None:
            raise ValueError("live runtime failed")

    monkeypatch.setattr(
        execution_module,
        "TradeJournal",
        NoopJournal,
    )
    monkeypatch.setattr(
        paper_runtime_module,
        "PaperTradingSession",
        CapturingSession,
    )
    monkeypatch.setattr(
        paper_runtime_module,
        "LivePaperRuntime",
        FailingLivePaperRuntime,
    )

    with pytest.raises(
        ValueError,
        match="live runtime failed",
    ):
        run_live_paper_trading(
            feed=object(),
            strategy=NoSignalStrategy(),
            runtime_context=RuntimeContext(),
            dataset_context=_dataset_context(),
            session_end=object(),
            now=lambda: object(),
            reconnect_attempts=2,
            reconnect_delay_seconds=0.0,
            clock_interval_seconds=0.0,
            initial_capital=100_000.0,
        )

    session = holder["session"]

    assert LIVE_SESSION_ID.fullmatch(session.session_id)
    assert session.execution_engine.session_id == session.session_id
    assert session.execution_engine.journal.session_id == session.session_id
    assert session.status == "FAILED"
    assert session.snapshot().failure_type == "ValueError"
    assert session.snapshot().failure_message == "live runtime failed"


def test_stopped_paper_session_remains_terminal() -> None:
    session = PaperTradingSession(
        session_id="paper-test",
        strategy_name="test-strategy",
        symbol="RELIANCE",
        initial_capital=100_000.0,
    )
    session.start()
    session.stop()

    stopped_at = session.stopped_at

    session.fail(ValueError("late failure"))

    assert session.status == "STOPPED"
    assert session.stopped_at == stopped_at
    assert session.failure_type is None
    assert session.failure_message is None


def test_snapshot_preserves_most_recent_execution_after_later_noop_candle(
    monkeypatch,
) -> None:
    from datetime import datetime, timedelta, timezone

    from core.config.execution_config import ExecutionConfig
    from core.entities.candle import Candle
    from core.market_data.mock_live_feed import MockLiveFeed
    from core.strategies.signal import SignalType

    class BuyOnceStrategy(BaseStrategy):
        def __init__(self) -> None:
            super().__init__(name="buy_once")

        def on_new_candle(self, series):
            if len(series) == 1:
                return SignalType.BUY
            return None

        def reset(self) -> None:
            pass

    monkeypatch.setattr(
        execution_module,
        "TradeJournal",
        NoopJournal,
    )

    start = datetime(
        2026,
        1,
        2,
        9,
        15,
        tzinfo=timezone(timedelta(hours=5, minutes=30)),
    )

    candles = [
        Candle(
            timestamp=start,
            open=99.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=1_000.0,
        ),
        Candle(
            timestamp=start + timedelta(minutes=15),
            open=110.0,
            high=112.0,
            low=109.0,
            close=111.0,
            volume=1_100.0,
        ),
        Candle(
            timestamp=start + timedelta(minutes=30),
            open=112.0,
            high=114.0,
            low=110.0,
            close=113.0,
            volume=1_200.0,
        ),
    ]

    session = run_paper_trading(
        feed=MockLiveFeed(
            candles=candles,
            interval_seconds=0.0,
        ),
        strategy=BuyOnceStrategy(),
        runtime_context=RuntimeContext(
            execution_config=ExecutionConfig(
                slippage_enabled=False,
                brokerage_enabled=False,
            ),
        ),
        dataset_context=_dataset_context(),
        initial_capital=100_000.0,
    )

    snapshot = session.snapshot()

    assert snapshot.last_execution_event == "BUY"
    assert snapshot.last_execution_price == 110.0
    assert snapshot.last_execution_quantity is not None

import threading
from datetime import datetime, timedelta, timezone

import pytest

import core.runtime.paper_runtime as paper_runtime
from core.paper_trading.paper_trading_session import PaperTradingSession
from core.runtime.dataset_context import DatasetContext
from core.runtime.live_paper_runtime import LivePaperRuntime
from core.runtime.runtime_context import RuntimeContext
from core.strategies.sma_crossover_strategy import SMACrossOverStrategy


INDIA = timezone(
    timedelta(hours=5, minutes=30),
    name="Asia/Kolkata",
)
NOW = datetime(
    2026,
    1,
    5,
    10,
    0,
    tzinfo=INDIA,
)
END = datetime(
    2026,
    1,
    5,
    15,
    30,
    tzinfo=INDIA,
)


class DormantFeed:
    def subscribe(
        self,
        on_candle,
        on_market_update=None,
    ):
        raise AssertionError(
            "prepared runtime must not start provider"
        )

    def reconnect(self):
        raise AssertionError(
            "prepared runtime must not reconnect provider"
        )

    def advance_time(self, timestamp):
        pass

    def close(self):
        pass


def test_prepare_exposes_created_authoritative_graph(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    feed = DormantFeed()
    strategy = SMACrossOverStrategy(
        params={
            "fast_period": 1,
            "slow_period": 2,
        }
    )

    prepared = paper_runtime.prepare_live_paper_trading(
        feed=feed,
        strategy=strategy,
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0,
        ),
        dataset_context=DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
            timezone="Asia/Kolkata",
        ),
        session_end=END,
        now=lambda: NOW,
        reconnect_attempts=2,
        reconnect_delay_seconds=0.0,
        clock_interval_seconds=0.0,
        initial_capital=100000,
    )

    assert prepared.session.status == "CREATED"
    assert prepared.session.started_at is None
    assert prepared.session.stopped_at is None

    assert prepared.session.feed is feed
    assert prepared.session.strategy is strategy

    assert prepared.session.execution_engine is not None
    assert prepared.session.strategy_runner is not None

    assert isinstance(
        prepared.runtime,
        LivePaperRuntime,
    )

    assert prepared.session_end == END
    assert prepared.now() == NOW


def test_execute_prepared_run_owns_session_lifecycle():
    session = PaperTradingSession(
        session_id="paper-live-test",
        strategy_name="SMACrossOver",
        symbol="RELIANCE",
        initial_capital=100000,
    )

    observed = {}

    class ImmediateRuntime:
        def run_until(
            self,
            *,
            session_end,
            now,
            clock_interval_seconds,
        ):
            observed["status"] = session.status
            observed["session_end"] = session_end
            observed["now"] = now()
            observed["clock_interval_seconds"] = (
                clock_interval_seconds
            )

    prepared = paper_runtime.PreparedLivePaperRun(
        session=session,
        runtime=ImmediateRuntime(),
        state_lock=threading.RLock(),
        session_end=END,
        now=lambda: NOW,
        clock_interval_seconds=0.25,
    )

    result = (
        paper_runtime.execute_prepared_live_paper_trading(
            prepared
        )
    )

    assert result is session
    assert observed["status"] == "RUNNING"
    assert observed["session_end"] == END
    assert observed["now"] == NOW
    assert observed["clock_interval_seconds"] == 0.25

    assert session.status == "STOPPED"
    assert session.started_at is not None
    assert session.stopped_at is not None


def test_execute_prepared_run_records_failure():
    session = PaperTradingSession(
        session_id="paper-live-failed",
        strategy_name="SMACrossOver",
        symbol="RELIANCE",
        initial_capital=100000,
    )

    class FailingRuntime:
        def run_until(self, **kwargs):
            raise ConnectionError(
                "provider disconnected"
            )

    prepared = paper_runtime.PreparedLivePaperRun(
        session=session,
        runtime=FailingRuntime(),
        state_lock=threading.RLock(),
        session_end=END,
        now=lambda: NOW,
        clock_interval_seconds=0.0,
    )

    with pytest.raises(
        ConnectionError,
        match="provider disconnected",
    ):
        paper_runtime.execute_prepared_live_paper_trading(
            prepared
        )

    assert session.status == "FAILED"
    assert session.failure_type == "ConnectionError"
    assert (
        session.failure_message
        == "provider disconnected"
    )
    assert session.stopped_at is not None


def test_live_wrapper_delegates_to_prepared_execution(
    monkeypatch,
):
    prepared = object()
    expected_session = object()
    captured = {}

    def prepare(**kwargs):
        captured.update(kwargs)
        return prepared

    def execute(value):
        assert value is prepared
        return expected_session

    monkeypatch.setattr(
        paper_runtime,
        "prepare_live_paper_trading",
        prepare,
    )
    monkeypatch.setattr(
        paper_runtime,
        "execute_prepared_live_paper_trading",
        execute,
    )

    feed = object()
    strategy = object()
    runtime_context = object()
    dataset_context = object()
    historical_source = object()
    history_bars = [object()]

    result = paper_runtime.run_live_paper_trading(
        feed=feed,
        strategy=strategy,
        runtime_context=runtime_context,
        dataset_context=dataset_context,
        session_end=END,
        now=lambda: NOW,
        reconnect_attempts=3,
        reconnect_delay_seconds=1.5,
        clock_interval_seconds=0.5,
        initial_capital=250000,
        history_bars=history_bars,
        historical_source=historical_source,
    )

    assert result is expected_session

    assert captured["feed"] is feed
    assert captured["strategy"] is strategy
    assert (
        captured["runtime_context"]
        is runtime_context
    )
    assert (
        captured["dataset_context"]
        is dataset_context
    )
    assert captured["session_end"] == END
    assert captured["now"]() == NOW
    assert captured["reconnect_attempts"] == 3
    assert (
        captured["reconnect_delay_seconds"]
        == 1.5
    )
    assert (
        captured["clock_interval_seconds"]
        == 0.5
    )
    assert captured["initial_capital"] == 250000
    assert captured["history_bars"] is history_bars
    assert (
        captured["historical_source"]
        is historical_source
    )

class BlockingStartFeed:
    def __init__(self):
        self.closed = threading.Event()

    def subscribe(
        self,
        on_candle,
        on_market_update=None,
    ):
        self.closed.wait(timeout=2.0)

    def reconnect(self):
        self.closed.wait(timeout=2.0)

    def advance_time(self, timestamp):
        pass

    def close(self):
        self.closed.set()


def test_live_runtime_acknowledges_provider_start():
    feed = BlockingStartFeed()

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=lambda candle: None,
    )

    assert (
        runtime.wait_until_started(
            timeout_seconds=0.0
        )
        is False
    )

    runtime.start()

    try:
        assert (
            runtime.wait_until_started(
                timeout_seconds=1.0
            )
            is True
        )
        assert runtime.provider_thread.is_alive()
    finally:
        runtime.stop()

    assert not runtime.provider_thread.is_alive()


class StopDuringProviderStartupFeed:
    def __init__(self):
        self.first_close = threading.Event()
        self.closed = threading.Event()
        self.close_calls = 0

    def subscribe(
        self,
        on_candle,
        on_market_update=None,
    ):
        if not self.first_close.wait(
            timeout=1.0
        ):
            raise RuntimeError(
                "first close was not observed"
            )

        if not self.closed.wait(
            timeout=1.0
        ):
            raise RuntimeError(
                "later close was not observed"
            )

    def reconnect(self):
        self.closed.wait(timeout=1.0)

    def advance_time(self, timestamp):
        pass

    def close(self):
        self.close_calls += 1

        if self.close_calls == 1:
            # Simulate the first close happening before provider
            # subscription has become closeable.
            self.first_close.set()
            return

        self.closed.set()


def test_stop_survives_close_before_provider_subscription_is_ready():
    feed = StopDuringProviderStartupFeed()

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=lambda candle: None,
        join_timeout_seconds=0.5,
    )

    runtime.start()

    assert runtime.wait_until_started(
        timeout_seconds=1.0
    )

    runtime.stop()

    assert feed.close_calls >= 2
    assert feed.closed.is_set()
    assert not runtime.provider_thread.is_alive()


class ConcurrentStopGuardFeed:
    def __init__(self):
        self.closed = threading.Event()
        self._close_guard = threading.Lock()

    def subscribe(
        self,
        on_candle,
        on_market_update=None,
    ):
        self.closed.wait(timeout=1.0)

    def reconnect(self):
        self.closed.wait(timeout=1.0)

    def advance_time(self, timestamp):
        pass

    def close(self):
        if not self._close_guard.acquire(
            blocking=False
        ):
            raise RuntimeError(
                "concurrent feed close"
            )

        try:
            # Hold close briefly so simultaneous stop callers would
            # deterministically overlap without runtime serialization.
            threading.Event().wait(0.05)
            self.closed.set()
        finally:
            self._close_guard.release()


def test_concurrent_runtime_stop_is_serialized():
    feed = ConcurrentStopGuardFeed()

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=lambda candle: None,
        join_timeout_seconds=0.5,
    )

    runtime.start()

    assert runtime.wait_until_started(
        timeout_seconds=1.0
    )

    barrier = threading.Barrier(3)
    errors = []

    def stop_runtime():
        barrier.wait()

        try:
            runtime.stop()
        except Exception as exc:
            errors.append(exc)

    first = threading.Thread(
        target=stop_runtime
    )
    second = threading.Thread(
        target=stop_runtime
    )

    first.start()
    second.start()
    barrier.wait()

    first.join(timeout=1.0)
    second.join(timeout=1.0)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert feed.closed.is_set()
    assert not runtime.provider_thread.is_alive()

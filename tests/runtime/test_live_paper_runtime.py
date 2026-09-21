import threading

import pytest

from core.runtime.live_paper_runtime import LivePaperRuntime


class BlockingFeed:
    def __init__(self) -> None:
        self.subscribe_thread: threading.Thread | None = None
        self.subscribed = threading.Event()
        self.closed = threading.Event()

    def subscribe(self, on_candle) -> None:
        self.subscribe_thread = threading.current_thread()
        self.subscribed.set()
        self.closed.wait(timeout=1.0)

    def close(self) -> None:
        self.closed.set()


def test_live_paper_runtime_owns_non_daemon_provider_thread_and_joins_on_stop() -> None:
    feed = BlockingFeed()

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=lambda candle: None,
    )

    runtime.start()

    assert feed.subscribed.wait(timeout=1.0)
    assert feed.subscribe_thread is not None
    assert feed.subscribe_thread is not threading.current_thread()
    assert feed.subscribe_thread.daemon is False
    assert runtime.provider_thread is feed.subscribe_thread
    assert runtime.provider_thread.is_alive()

    runtime.stop()

    assert feed.closed.is_set()
    assert not runtime.provider_thread.is_alive()


class FailingFeed:
    def __init__(self) -> None:
        self.subscribed = threading.Event()
        self.closed = threading.Event()

    def subscribe(self, on_candle) -> None:
        self.subscribed.set()
        raise ValueError("provider boom")

    def close(self) -> None:
        self.closed.set()


def test_live_paper_runtime_surfaces_provider_thread_failure() -> None:
    feed = FailingFeed()

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=lambda candle: None,
    )

    runtime.start()

    assert feed.subscribed.wait(timeout=1.0)

    runtime.provider_thread.join(timeout=1.0)
    assert not runtime.provider_thread.is_alive()

    with pytest.raises(
        RuntimeError,
        match="Live paper provider thread failed",
    ) as exc_info:
        runtime.raise_if_failed()

    assert isinstance(exc_info.value.__cause__, ValueError)
    assert str(exc_info.value.__cause__) == "provider boom"

    runtime.stop()
    assert feed.closed.is_set()


class ReconnectBlockingFeed:
    def __init__(self) -> None:
        self.subscribed = threading.Event()
        self.reconnect_started = threading.Event()
        self.closed = threading.Event()
        self.reconnect_calls = 0
        self.reconnect_thread: threading.Thread | None = None

    def subscribe(self, on_candle) -> None:
        self.subscribed.set()
        # Simulate the blocking provider connection returning after an
        # unexpected disconnect.

    def reconnect(self) -> None:
        self.reconnect_calls += 1
        self.reconnect_thread = threading.current_thread()
        self.reconnect_started.set()
        self.closed.wait(timeout=1.0)

    def close(self) -> None:
        self.closed.set()


def test_live_paper_runtime_reconnects_after_unexpected_provider_return() -> None:
    feed = ReconnectBlockingFeed()

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=lambda candle: None,
    )

    runtime.start()

    assert feed.subscribed.wait(timeout=1.0)

    assert feed.reconnect_started.wait(timeout=1.0)
    assert feed.reconnect_calls == 1
    assert feed.reconnect_thread is runtime.provider_thread
    assert runtime.provider_thread.is_alive()

    runtime.raise_if_failed()

    runtime.stop()

    assert feed.closed.is_set()
    assert not runtime.provider_thread.is_alive()


class FailingReconnectFeed:
    def __init__(self) -> None:
        self.subscribed = threading.Event()
        self.closed = threading.Event()
        self.reconnect_calls = 0

    def subscribe(self, on_candle) -> None:
        self.subscribed.set()

    def reconnect(self) -> None:
        self.reconnect_calls += 1
        raise ConnectionError(
            f"reconnect failed {self.reconnect_calls}"
        )

    def close(self) -> None:
        self.closed.set()


def test_live_paper_runtime_retries_reconnect_until_attempt_budget_exhausted() -> None:
    feed = FailingReconnectFeed()

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=lambda candle: None,
        reconnect_attempts=2,
    )

    runtime.start()

    assert feed.subscribed.wait(timeout=1.0)

    runtime.provider_thread.join(timeout=1.0)

    assert not runtime.provider_thread.is_alive()
    assert feed.reconnect_calls == 2

    with pytest.raises(
        RuntimeError,
        match="Live paper provider thread failed",
    ) as exc_info:
        runtime.raise_if_failed()

    assert isinstance(
        exc_info.value.__cause__,
        ConnectionError,
    )
    assert str(exc_info.value.__cause__) == "reconnect failed 2"

    runtime.stop()
    assert feed.closed.is_set()


class DelayedRetryFeed:
    def __init__(self) -> None:
        self.subscribed = threading.Event()
        self.first_reconnect_failed = threading.Event()
        self.second_reconnect_started = threading.Event()
        self.closed = threading.Event()
        self.reconnect_calls = 0

    def subscribe(self, on_candle) -> None:
        self.subscribed.set()

    def reconnect(self) -> None:
        self.reconnect_calls += 1

        if self.reconnect_calls == 1:
            self.first_reconnect_failed.set()
            raise ConnectionError("first reconnect failed")

        self.second_reconnect_started.set()
        self.closed.wait(timeout=1.0)

    def close(self) -> None:
        self.closed.set()


def test_live_paper_runtime_waits_between_reconnect_attempts_and_stop_interrupts_wait() -> None:
    feed = DelayedRetryFeed()

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=lambda candle: None,
        reconnect_attempts=2,
        reconnect_delay_seconds=10.0,
    )

    runtime.start()

    assert feed.subscribed.wait(timeout=1.0)
    assert feed.first_reconnect_failed.wait(timeout=1.0)

    # A long retry delay must prevent the next reconnect from starting
    # immediately.
    assert not feed.second_reconnect_started.wait(timeout=0.05)
    assert feed.reconnect_calls == 1

    # Shutdown must interrupt the retry wait rather than blocking for the
    # configured delay.
    runtime.stop()

    assert feed.closed.is_set()
    assert feed.reconnect_calls == 1
    assert not runtime.provider_thread.is_alive()

    runtime.raise_if_failed()


class ClockRecordingFeed:
    def __init__(self) -> None:
        self.subscribed = threading.Event()
        self.closed = threading.Event()
        self.advance_calls = []
        self.advance_thread: threading.Thread | None = None

    def subscribe(self, on_candle) -> None:
        self.subscribed.set()
        self.closed.wait(timeout=1.0)

    def reconnect(self) -> None:
        self.closed.wait(timeout=1.0)

    def close(self) -> None:
        self.closed.set()

    def advance_time(self, timestamp) -> None:
        self.advance_calls.append(timestamp)
        self.advance_thread = threading.current_thread()


def test_live_paper_runtime_advances_clock_on_calling_thread() -> None:
    feed = ClockRecordingFeed()

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=lambda candle: None,
    )

    runtime.start()
    assert feed.subscribed.wait(timeout=1.0)

    timestamp = object()
    calling_thread = threading.current_thread()

    try:
        runtime.advance_time(timestamp)

        assert feed.advance_calls == [timestamp]
        assert feed.advance_thread is calling_thread
        assert feed.advance_thread is not runtime.provider_thread
    finally:
        runtime.stop()

    assert not runtime.provider_thread.is_alive()

from datetime import datetime, timedelta, timezone


class RunLoopFeed:
    def __init__(self) -> None:
        self.subscribed = threading.Event()
        self.closed = threading.Event()
        self.advance_calls = []

    def subscribe(self, on_candle) -> None:
        self.subscribed.set()
        self.closed.wait(timeout=1.0)

    def reconnect(self) -> None:
        self.closed.wait(timeout=1.0)

    def close(self) -> None:
        self.closed.set()

    def advance_time(self, timestamp) -> None:
        self.advance_calls.append(
            (timestamp, threading.current_thread())
        )


def test_live_paper_runtime_run_until_advances_clock_and_stops_at_session_end() -> None:
    feed = RunLoopFeed()
    start = datetime(2026, 1, 2, 9, 15, tzinfo=timezone.utc)
    session_end = start + timedelta(seconds=2)
    times = iter(
        [
            start,
            start + timedelta(seconds=1),
            session_end + timedelta(milliseconds=250),
        ]
    )

    def now():
        assert feed.subscribed.wait(timeout=1.0)
        return next(times)

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=lambda candle: None,
    )

    runtime.run_until(
        session_end=session_end,
        now=now,
        clock_interval_seconds=0.0,
    )

    assert [item[0] for item in feed.advance_calls] == [
        start,
        start + timedelta(seconds=1),
        session_end,
    ]
    assert all(
        thread is threading.current_thread()
        for _, thread in feed.advance_calls
    )
    assert feed.closed.is_set()
    assert not runtime.provider_thread.is_alive()


class InitialSubscribeFailureFeed:
    def __init__(self) -> None:
        self.subscribed = threading.Event()
        self.reconnect_started = threading.Event()
        self.closed = threading.Event()
        self.subscribe_calls = 0
        self.reconnect_calls = 0

    def subscribe(self, on_candle) -> None:
        self.subscribe_calls += 1
        self.subscribed.set()
        raise ConnectionError("initial connect failed")

    def reconnect(self) -> None:
        self.reconnect_calls += 1
        self.reconnect_started.set()
        self.closed.wait(timeout=1.0)

    def close(self) -> None:
        self.closed.set()

    def advance_time(self, timestamp) -> None:
        pass


def test_live_paper_runtime_retries_after_initial_subscribe_failure() -> None:
    feed = InitialSubscribeFailureFeed()

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=lambda candle: None,
        reconnect_attempts=2,
        reconnect_delay_seconds=0.0,
    )

    runtime.start()

    try:
        assert feed.subscribed.wait(timeout=1.0)
        assert feed.reconnect_started.wait(timeout=0.2)
        assert feed.subscribe_calls == 1
        assert feed.reconnect_calls == 1
        runtime.raise_if_failed()
    finally:
        runtime.stop()

    assert feed.closed.is_set()
    assert not runtime.provider_thread.is_alive()


class FatalReconnectFeed:
    def __init__(self) -> None:
        self.subscribed = threading.Event()
        self.closed = threading.Event()
        self.reconnect_calls = 0

    def subscribe(self, on_candle) -> None:
        self.subscribed.set()

    def reconnect(self) -> None:
        self.reconnect_calls += 1
        raise ValueError(
            "fatal reconnect failure"
        )

    def close(self) -> None:
        self.closed.set()

    def advance_time(self, timestamp) -> None:
        pass


def test_live_paper_runtime_does_not_retry_fatal_reconnect_failure() -> None:
    feed = FatalReconnectFeed()

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=lambda candle: None,
        reconnect_attempts=5,
    )

    runtime.start()

    assert feed.subscribed.wait(timeout=1.0)

    runtime.provider_thread.join(timeout=1.0)

    assert not runtime.provider_thread.is_alive()
    assert feed.reconnect_calls == 1

    with pytest.raises(
        RuntimeError,
        match="Live paper provider thread failed",
    ) as exc_info:
        runtime.raise_if_failed()

    assert isinstance(
        exc_info.value.__cause__,
        ValueError,
    )
    assert str(
        exc_info.value.__cause__
    ) == "fatal reconnect failure"

    runtime.stop()
    assert feed.closed.is_set()


class FatalClockFeed:
    def __init__(self) -> None:
        self.subscribed = threading.Event()
        self.closed = threading.Event()
        self.advance_calls = 0

    def subscribe(self, on_candle) -> None:
        self.subscribed.set()
        self.closed.wait(timeout=1.0)

    def reconnect(self) -> None:
        self.closed.wait(timeout=1.0)

    def close(self) -> None:
        self.closed.set()

    def advance_time(self, timestamp) -> None:
        self.advance_calls += 1
        raise ValueError(
            "fatal clock failure"
        )


def test_live_paper_runtime_surfaces_clock_failure_without_reconnect() -> None:
    feed = FatalClockFeed()
    now_value = datetime(
        2026,
        1,
        2,
        9,
        15,
        tzinfo=timezone.utc,
    )

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=lambda candle: None,
    )

    with pytest.raises(
        ValueError,
        match="fatal clock failure",
    ):
        runtime.run_until(
            session_end=now_value + timedelta(hours=1),
            now=lambda: now_value,
            clock_interval_seconds=0.0,
        )

    assert feed.advance_calls == 1
    assert feed.closed.is_set()
    assert not runtime.provider_thread.is_alive()


class StateThenDisconnectFeed:
    def __init__(self) -> None:
        self.subscribed = threading.Event()
        self.closed = threading.Event()
        self.reconnect_calls = 0

    def subscribe(
        self,
        on_candle,
        on_market_update=None,
    ) -> None:
        self.subscribed.set()

        # One completed candle has now entered strategy/execution state.
        on_candle(object())

        # Returning simulates transport loss/provider termination after
        # authoritative paper state has begun.

    def reconnect(self) -> None:
        self.reconnect_calls += 1
        raise ConnectionError("reconnect should not be attempted")

    def close(self) -> None:
        self.closed.set()

    def advance_time(self, timestamp) -> None:
        pass


def test_runtime_refuses_reconnect_after_completed_candle_state_begins() -> None:
    feed = StateThenDisconnectFeed()

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=lambda _candle: None,
        reconnect_attempts=1,
        reconnect_delay_seconds=0.0,
    )

    runtime.start()

    assert feed.subscribed.wait(timeout=1.0)

    runtime.provider_thread.join(timeout=1.0)
    assert not runtime.provider_thread.is_alive()

    with pytest.raises(
        RuntimeError,
        match="Live paper provider thread failed",
    ) as exc_info:
        runtime.raise_if_failed()

    assert isinstance(
        exc_info.value.__cause__,
        RuntimeError,
    )
    assert "reconciliation" in str(
        exc_info.value.__cause__
    )
    assert feed.reconnect_calls == 0

    runtime.stop()
    assert feed.closed.is_set()


class SessionEndRaceFeed:
    def __init__(self) -> None:
        self.subscribed = threading.Event()
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
        self.subscribed.set()
        self.closed.wait(timeout=1.0)

    def reconnect(self) -> None:
        self.closed.wait(timeout=1.0)

    def advance_time(self, timestamp) -> None:
        # Simulate source callbacks racing exactly with caller-side session
        # shutdown. Once session_end is observed, neither callback may mutate
        # paper strategy/execution state.
        self.on_candle(object())

        if self.on_market_update is not None:
            self.on_market_update(
                object(),
                True,
            )

    def close(self) -> None:
        self.closed.set()


def test_session_end_rejects_racing_provider_callbacks() -> None:
    feed = SessionEndRaceFeed()
    completed = []
    updates = []

    session_end = datetime(
        2026,
        1,
        2,
        15,
        30,
        tzinfo=timezone.utc,
    )

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=completed.append,
        on_market_update=(
            lambda update, opens_new_bar: updates.append(
                (update, opens_new_bar)
            )
        ),
    )

    def now():
        assert feed.subscribed.wait(timeout=1.0)
        return session_end

    runtime.run_until(
        session_end=session_end,
        now=now,
        clock_interval_seconds=0.0,
    )

    assert completed == []
    assert updates == []
    assert feed.closed.is_set()
    assert not runtime.provider_thread.is_alive()


class SessionEndSourceBoundaryFeed:
    def __init__(self, session_end) -> None:
        self.session_end = session_end
        self.boundary_sent = threading.Event()
        self.closed = threading.Event()

    def subscribe(
        self,
        on_candle,
        on_market_update=None,
    ) -> None:
        # Model the provider boundary observation arriving just before the
        # caller observes wall-clock session end. The final completed candle
        # is valid, but there is no tradable next bar after session close.
        on_candle(object())

        if on_market_update is not None:
            class BoundaryUpdate:
                timestamp = self.session_end

            on_market_update(
                BoundaryUpdate(),
                True,
            )

        self.boundary_sent.set()
        self.closed.wait(timeout=1.0)

    def reconnect(self) -> None:
        self.closed.wait(timeout=1.0)

    def advance_time(self, timestamp) -> None:
        pass

    def close(self) -> None:
        self.closed.set()


def test_session_end_source_boundary_cannot_open_next_bar_execution() -> None:
    session_end = datetime(
        2026,
        1,
        2,
        15,
        30,
        tzinfo=timezone.utc,
    )
    feed = SessionEndSourceBoundaryFeed(session_end)

    completed = []
    opens_new_bar_values = []

    runtime = LivePaperRuntime(
        feed=feed,
        on_candle=completed.append,
        on_market_update=(
            lambda _update, opens_new_bar: (
                opens_new_bar_values.append(
                    opens_new_bar
                )
            )
        ),
    )

    def now():
        assert feed.boundary_sent.wait(timeout=1.0)
        return session_end

    runtime.run_until(
        session_end=session_end,
        now=now,
        clock_interval_seconds=0.0,
    )

    assert len(completed) == 1
    assert opens_new_bar_values == [False]
    assert feed.closed.is_set()
    assert not runtime.provider_thread.is_alive()

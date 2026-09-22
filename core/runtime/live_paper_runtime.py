import threading
from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from core.market_data.live_candle_feed import (
    CompletedCandleHandler,
    LiveMarketUpdateHandler,
)


class ManagedLiveCandleFeed(Protocol):
    """Live feed lifecycle required by the M7 supervisor."""

    def subscribe(
        self,
        on_candle: CompletedCandleHandler,
        on_market_update: LiveMarketUpdateHandler | None = None,
    ) -> None:
        ...

    def reconnect(self) -> None:
        ...

    def advance_time(
        self,
        timestamp: datetime,
    ) -> None:
        ...

    def close(self) -> None:
        ...


class LivePaperRuntime:
    """
    Own the blocking live-feed connection thread for paper trading.

    Own provider connection lifecycle, reconnect policy, and the
    caller-thread session clock for paper trading.
    """

    def __init__(
        self,
        *,
        feed: ManagedLiveCandleFeed,
        on_candle: CompletedCandleHandler,
        on_market_update: LiveMarketUpdateHandler | None = None,
        on_reconciliation_required: Callable[[], None] | None = None,
        on_clock: Callable[[], None] | None = None,
        reconnect_attempts: int = 2,
        reconnect_delay_seconds: float = 0.0,
        join_timeout_seconds: float = 5.0,
    ) -> None:
        if (
            isinstance(reconnect_attempts, bool)
            or not isinstance(reconnect_attempts, int)
            or reconnect_attempts < 1
        ):
            raise ValueError(
                "reconnect_attempts must be a positive integer"
            )

        if (
            isinstance(reconnect_delay_seconds, bool)
            or not isinstance(
                reconnect_delay_seconds,
                (int, float),
            )
            or reconnect_delay_seconds < 0
        ):
            raise ValueError(
                "reconnect_delay_seconds must be non-negative"
            )

        self._feed = feed
        self._on_candle = on_candle
        self._on_market_update = on_market_update
        self._on_reconciliation_required = on_reconciliation_required
        self._on_clock = on_clock
        self._reconnect_attempts = reconnect_attempts
        self._reconnect_delay_seconds = float(
            reconnect_delay_seconds
        )
        self._join_timeout_seconds = join_timeout_seconds

        self._stop_event = threading.Event()
        self._completed_state_started = threading.Event()
        self._callback_lock = threading.Lock()
        self._callbacks_open = False
        self._session_end: datetime | None = None
        self._failure_lock = threading.Lock()

        self._provider_thread: threading.Thread | None = None
        self._provider_failure: Exception | None = None

    @property
    def provider_thread(self) -> threading.Thread:
        if self._provider_thread is None:
            raise RuntimeError(
                "Live paper provider thread has not been started"
            )

        return self._provider_thread

    def start(self) -> None:
        if self._provider_thread is not None:
            raise RuntimeError(
                "Live paper runtime has already been started"
            )

        self._stop_event.clear()
        self._completed_state_started.clear()

        with self._callback_lock:
            self._callbacks_open = True

        with self._failure_lock:
            self._provider_failure = None

        thread = threading.Thread(
            target=self._run_provider,
            name="kanasu-live-paper-provider",
            daemon=False,
        )

        self._provider_thread = thread
        thread.start()

    def stop(self) -> None:
        thread = self._provider_thread

        if thread is None:
            return

        self._stop_event.set()
        self._close_callback_admission()
        self._feed.close()

        thread.join(
            timeout=self._join_timeout_seconds,
        )

        if thread.is_alive():
            raise RuntimeError(
                "Live paper provider thread did not stop"
            )

    def advance_time(
        self,
        timestamp: datetime,
    ) -> None:
        self._feed.advance_time(timestamp)

    def run_until(
        self,
        *,
        session_end: datetime,
        now,
        clock_interval_seconds: float = 1.0,
    ) -> None:
        if (
            isinstance(clock_interval_seconds, bool)
            or not isinstance(clock_interval_seconds, (int, float))
            or clock_interval_seconds < 0
        ):
            raise ValueError(
                "clock_interval_seconds must be non-negative"
            )

        with self._callback_lock:
            self._session_end = session_end

        self.start()

        try:
            while not self._stop_event.is_set():
                self.raise_if_failed()

                timestamp = now()

                if timestamp >= session_end:
                    # Session lifecycle owns the admission boundary. Close
                    # callbacks before the final lifecycle observation so a
                    # racing provider event cannot mutate paper state after
                    # the configured session end.
                    self._close_callback_admission()
                    self.advance_time(session_end)
                    self.raise_if_failed()
                    break

                self.advance_time(timestamp)
                self.raise_if_failed()

                if self._on_clock is not None:
                    self._on_clock()
                    self.raise_if_failed()

                if self._stop_event.wait(
                    float(clock_interval_seconds)
                ):
                    break
        finally:
            self.stop()

        self.raise_if_failed()

    def raise_if_failed(self) -> None:
        with self._failure_lock:
            failure = self._provider_failure

        if failure is not None:
            raise RuntimeError(
                "Live paper provider thread failed"
            ) from failure

    def _close_callback_admission(self) -> None:
        with self._callback_lock:
            self._callbacks_open = False

    def _handle_market_update(
        self,
        update,
        opens_new_bar: bool,
    ) -> None:
        with self._callback_lock:
            if not self._callbacks_open:
                return

            if self._on_market_update is None:
                return

            effective_opens_new_bar = opens_new_bar

            if (
                effective_opens_new_bar
                and self._session_end is not None
                and update.timestamp >= self._session_end
            ):
                # A closing-boundary observation may validly complete the
                # final session candle, but it cannot authorize execution
                # in a non-existent next tradable bar.
                effective_opens_new_bar = False

            self._on_market_update(
                update,
                effective_opens_new_bar,
            )

    def _handle_completed_candle(
        self,
        candle,
    ) -> None:
        with self._callback_lock:
            if not self._callbacks_open:
                return

            # Once a completed candle enters strategy/execution state, a
            # later provider gap cannot be resumed causally without
            # authoritative reconciliation/backfill.
            self._completed_state_started.set()
            self._on_candle(candle)

    def _record_reconciliation_failure(self) -> None:
        self._record_provider_failure(
            RuntimeError(
                "Live paper reconnect requires reconciliation after "
                "completed candle state begins"
            )
        )

    def _prepare_reconnect_after_gap(self) -> bool:
        """
        Reconcile persistent paper state before reconnecting after a gap.

        Once completed strategy state has begun, every later provider loss
        remains stateful for the rest of the live-paper session.
        """
        if not self._completed_state_started.is_set():
            return True

        if self._on_reconciliation_required is None:
            self._record_reconciliation_failure()
            return False

        try:
            self._on_reconciliation_required()
        except Exception as exc:
            self._record_provider_failure(exc)
            return False

        return True

    def _record_provider_failure(
        self,
        failure: Exception,
    ) -> None:
        with self._failure_lock:
            self._provider_failure = failure

        self._stop_event.set()

    def _run_provider(self) -> None:
        try:
            if self._on_market_update is None:
                self._feed.subscribe(
                    self._handle_completed_candle
                )
            else:
                self._feed.subscribe(
                    self._handle_completed_candle,
                    self._handle_market_update,
                )
        except ConnectionError:
            if not self._prepare_reconnect_after_gap():
                return

            if self._stop_event.wait(
                self._reconnect_delay_seconds
            ):
                return
        except Exception as exc:
            self._record_provider_failure(exc)
            return
        else:
            if (
                not self._stop_event.is_set()
                and not self._prepare_reconnect_after_gap()
            ):
                return

        while not self._stop_event.is_set():
            last_failure: Exception | None = None

            for attempt in range(self._reconnect_attempts):
                if self._stop_event.is_set():
                    return

                try:
                    self._feed.reconnect()
                except ConnectionError as exc:
                    if not self._prepare_reconnect_after_gap():
                        return

                    last_failure = exc

                    has_retry_remaining = (
                        attempt + 1 < self._reconnect_attempts
                    )

                    if (
                        has_retry_remaining
                        and self._stop_event.wait(
                            self._reconnect_delay_seconds
                        )
                    ):
                        return

                    continue
                except Exception as exc:
                    self._record_provider_failure(exc)
                    return

                if (
                    not self._stop_event.is_set()
                    and not self._prepare_reconnect_after_gap()
                ):
                    return

                last_failure = None
                break

            if last_failure is not None:
                self._record_provider_failure(last_failure)
                return

import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime

import pytz

from api.models.paper_trading_models import (
    PaperTradingSnapshotResponse,
    PaperTradingStartRequest,
    PaperTradingStartResponse,
    PaperTradingStatusResponse,
    PaperTradingStopResponse,
)
from core.broker.angelone import AngelOneBroker
from core.broker.angelone_config import AngelOneConfig
from core.config.app_config import AppConfig
from core.config.backtest_config import (
    BACKTEST_CONFIG,
    BacktestConfig,
)
from core.config.loaders import load_app_config
from core.config.paper_data_source import PaperDataSource
from core.market_data.angelone_live_candle_feed import (
    AngelOneLiveCandleFeed,
)
from core.market_data.historical_source import HistoricalSource
from core.market_data.historical_source_factory import (
    create_historical_source,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.live_paper_session import (
    resolve_live_paper_session_window,
)
from core.runtime.live_paper_warmup import (
    load_live_paper_warmup,
)
from core.runtime.paper_runtime import (
    PreparedLivePaperRun,
    execute_prepared_live_paper_trading,
    prepare_live_paper_trading,
)
from core.runtime.runtime_context import RuntimeContext
from core.strategies.strategy_factory import create_strategy


class PaperLifecycleConflict(RuntimeError):
    """Requested paper lifecycle operation conflicts with current ownership."""


@dataclass
class PaperApplicationHandle:
    prepared: PreparedLivePaperRun
    worker: threading.Thread | None = None
    completed: threading.Event = field(
        default_factory=threading.Event
    )
    stop_in_progress: bool = False
    worker_failure: Exception | None = None


class PaperTradingApplication:
    """Own exactly one process-local authoritative paper runtime."""

    def __init__(
        self,
        prepare_request: Callable[
            [PaperTradingStartRequest],
            PreparedLivePaperRun,
        ],
        *,
        runtime_start_wait_seconds: float = 5.0,
        worker_join_timeout_seconds: float = 10.0,
    ) -> None:
        self._prepare_request = prepare_request
        self._runtime_start_wait_seconds = (
            runtime_start_wait_seconds
        )
        self._worker_join_timeout_seconds = (
            worker_join_timeout_seconds
        )

        self._lifecycle_lock = threading.RLock()
        self._current_handle: (
            PaperApplicationHandle | None
        ) = None
        self._start_in_progress = False

    def start(
        self,
        request: PaperTradingStartRequest,
    ) -> PaperTradingStartResponse:
        with self._lifecycle_lock:
            current = self._current_handle

            if self._start_in_progress:
                raise PaperLifecycleConflict(
                    "paper trading start is already in progress"
                )

            if (
                current is not None
                and not current.completed.is_set()
            ):
                raise PaperLifecycleConflict(
                    "paper trading session is already active"
                )

            previous = current
            self._start_in_progress = True

        try:
            prepared = self._prepare_request(request)

            handle = PaperApplicationHandle(
                prepared=prepared,
            )

            worker = threading.Thread(
                target=self._run_worker,
                args=(handle,),
                name="kanasu-paper-application-worker",
                daemon=False,
            )
            handle.worker = worker

            with self._lifecycle_lock:
                self._current_handle = handle

                try:
                    worker.start()
                except Exception:
                    self._current_handle = previous
                    raise

                self._start_in_progress = False

            return self._project_snapshot(
                handle,
                PaperTradingStartResponse,
            )

        except Exception:
            with self._lifecycle_lock:
                self._start_in_progress = False
            raise

    def status(
        self,
    ) -> PaperTradingStatusResponse:
        with self._lifecycle_lock:
            handle = self._current_handle

        if handle is None:
            return PaperTradingStatusResponse(
                active=False,
                snapshot=None,
            )

        with handle.prepared.state_lock:
            snapshot = (
                handle.prepared.session.snapshot()
            )

            active = (
                not handle.completed.is_set()
                and snapshot.status
                in {
                    "CREATED",
                    "RUNNING",
                }
            )

        return PaperTradingStatusResponse(
            active=active,
            snapshot=PaperTradingSnapshotResponse.model_validate(
                asdict(snapshot)
            ),
        )

    def stop(
        self,
    ) -> PaperTradingStopResponse:
        with self._lifecycle_lock:
            handle = self._current_handle

            if (
                handle is None
                or handle.completed.is_set()
            ):
                raise PaperLifecycleConflict(
                    "no active paper trading session"
                )

            if handle.stop_in_progress:
                raise PaperLifecycleConflict(
                    "paper trading stop is already in progress"
                )

            handle.stop_in_progress = True

        try:
            self._stop_handle(handle)

            return self._project_snapshot(
                handle,
                PaperTradingStopResponse,
            )

        finally:
            with self._lifecycle_lock:
                handle.stop_in_progress = False

    def _stop_handle(
        self,
        handle: PaperApplicationHandle,
    ) -> None:
        runtime = handle.prepared.runtime

        deadline = (
            time.monotonic()
            + self._runtime_start_wait_seconds
        )

        while (
            not handle.completed.is_set()
            and not runtime.wait_until_started(
                timeout_seconds=0.05
            )
        ):
            if time.monotonic() >= deadline:
                raise RuntimeError(
                    "paper runtime did not start before stop timeout"
                )

        if not handle.completed.is_set():
            runtime.stop()

        worker = handle.worker

        if worker is None:
            raise RuntimeError(
                "paper application worker is missing"
            )

        worker.join(
            timeout=self._worker_join_timeout_seconds
        )

        if worker.is_alive():
            raise RuntimeError(
                "paper application worker did not stop"
            )

        if not handle.completed.is_set():
            raise RuntimeError(
                "paper application worker ended without completion"
            )

    def _run_worker(
        self,
        handle: PaperApplicationHandle,
    ) -> None:
        failure = None

        try:
            execute_prepared_live_paper_trading(
                handle.prepared
            )
        except Exception as exc:
            failure = exc
        finally:
            with handle.prepared.state_lock:
                handle.worker_failure = failure
                handle.completed.set()

    @staticmethod
    def _snapshot(
        handle: PaperApplicationHandle,
    ):
        with handle.prepared.state_lock:
            return handle.prepared.session.snapshot()

    def _project_snapshot(
        self,
        handle: PaperApplicationHandle,
        response_type,
    ):
        snapshot = self._snapshot(handle)

        return response_type.model_validate(
            asdict(snapshot)
        )


def prepare_paper_trading_request(
    request: PaperTradingStartRequest,
    *,
    app_config: AppConfig | None = None,
    paper_config: BacktestConfig | None = None,
    historical_source: HistoricalSource | None = None,
    now: Callable[[], datetime] | None = None,
) -> PreparedLivePaperRun:
    """Compose the accepted M7 AngelOne paper runtime for one API request."""

    resolved_app_config = (
        app_config
        if app_config is not None
        else load_app_config()
    )

    if (
        resolved_app_config.paper_data_source
        != PaperDataSource.ANGELONE
    ):
        raise ValueError(
            "authoritative Paper API requires ANGELONE paper data source"
        )

    base_config = (
        paper_config
        if paper_config is not None
        else BACKTEST_CONFIG
    )

    timezone_name = (
        base_config.timezone
        if base_config.timezone is not None
        else "Asia/Kolkata"
    )
    paper_timezone = pytz.timezone(
        timezone_name
    )

    now_fn = (
        now
        if now is not None
        else lambda: datetime.now(
            paper_timezone
        )
    )

    effective_config = BacktestConfig(
        symbol=request.symbol,
        timeframe=base_config.timeframe,
        strategy_name=request.strategy_id,
        start=base_config.start,
        end=base_config.end,
        initial_capital=base_config.initial_capital,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        strategy_params=dict(
            base_config.strategy_params
        ),
        timezone=timezone_name,
    )

    strategy = create_strategy(
        effective_config
    )

    runtime_context = RuntimeContext(
        risk_per_trade_pct=(
            resolved_app_config.risk_per_trade_pct
        ),
    )

    dataset_context = DatasetContext(
        symbol=request.symbol,
        timeframe=effective_config.timeframe,
        timezone=timezone_name,
    )

    current_time = now_fn()

    session_window = (
        resolve_live_paper_session_window(
            current_time=current_time,
            session_start=(
                resolved_app_config.paper_session_start
            ),
            session_end=(
                resolved_app_config.paper_session_end
            ),
        )
    )

    source = (
        historical_source
        if historical_source is not None
        else create_historical_source(
            resolved_app_config
        )
    )

    history_bars = load_live_paper_warmup(
        app_config=resolved_app_config,
        historical_source=source,
        strategy=strategy,
        dataset_context=dataset_context,
        current_time=current_time,
        session_start=session_window.start,
    )

    angelone_config = (
        AngelOneConfig.load_from_env()
    )

    broker = AngelOneBroker(
        config=angelone_config,
        paper_mode=True,
        enable_historical_api=False,
    )
    broker.login()

    auth_token, feed_token = (
        broker.get_live_market_data_session()
    )

    current_time = now_fn()

    session_window = (
        resolve_live_paper_session_window(
            current_time=current_time,
            session_start=(
                resolved_app_config.paper_session_start
            ),
            session_end=(
                resolved_app_config.paper_session_end
            ),
        )
    )

    feed = AngelOneLiveCandleFeed(
        config=angelone_config,
        auth_token=auth_token,
        feed_token=feed_token,
        symbol=request.symbol,
        timeframe=effective_config.timeframe,
        session_start=(
            resolved_app_config.paper_session_start
        ),
    )

    return prepare_live_paper_trading(
        feed=feed,
        strategy=strategy,
        runtime_context=runtime_context,
        dataset_context=dataset_context,
        session_end=session_window.end,
        now=now_fn,
        reconnect_attempts=(
            resolved_app_config.broker_retry_attempts
        ),
        reconnect_delay_seconds=(
            resolved_app_config.broker_retry_delay_sec
        ),
        clock_interval_seconds=(
            resolved_app_config.paper_clock_interval_sec
        ),
        initial_capital=(
            effective_config.initial_capital
        ),
        history_bars=history_bars,
        historical_source=source,
    )


paper_trading_application = (
    PaperTradingApplication(
        prepare_paper_trading_request
    )
)

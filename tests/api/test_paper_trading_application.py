import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

import api.paper_trading_application as application_module
from api.models.paper_trading_models import (
    PaperTradingStartRequest,
)
from api.paper_trading_application import (
    PaperLifecycleConflict,
    PaperTradingApplication,
)
from core.paper_trading.paper_trading_session import (
    PaperTradingSession,
)
from core.runtime.paper_runtime import (
    PreparedLivePaperRun,
)


INDIA = timezone(
    timedelta(hours=5, minutes=30),
    name="Asia/Kolkata",
)
END = datetime(
    2026,
    1,
    5,
    15,
    30,
    tzinfo=INDIA,
)


def request() -> PaperTradingStartRequest:
    return PaperTradingStartRequest(
        symbol="RELIANCE",
        strategy_id="sma_crossover",
    )


class ControlledRuntime:
    def __init__(
        self,
        *,
        failure: Exception | None = None,
    ):
        self.started = threading.Event()
        self.stopped = threading.Event()
        self.failure = failure
        self.stop_calls = 0

    def wait_until_started(
        self,
        timeout_seconds=None,
    ):
        return self.started.wait(
            timeout_seconds
        )

    def run_until(self, **kwargs):
        self.started.set()

        if self.failure is not None:
            raise self.failure

        self.stopped.wait(timeout=5.0)

    def stop(self):
        self.stop_calls += 1
        self.stopped.set()


def prepared(
    session_id: str,
    runtime: ControlledRuntime,
) -> PreparedLivePaperRun:
    session = PaperTradingSession(
        session_id=session_id,
        strategy_name="SMACrossOver",
        symbol="RELIANCE",
        initial_capital=100000,
    )

    return PreparedLivePaperRun(
        session=session,
        runtime=runtime,
        state_lock=threading.RLock(),
        session_end=END,
        now=lambda: END - timedelta(hours=1),
        clock_interval_seconds=0.0,
    )


def wait_for(
    condition,
    *,
    timeout=1.0,
):
    deadline = time.monotonic() + timeout

    while time.monotonic() < deadline:
        if condition():
            return

        time.sleep(0.005)

    raise AssertionError(
        "condition was not reached before timeout"
    )


def test_start_registers_real_handle_before_worker_completion():
    runtime = ControlledRuntime()
    built = []

    def prepare_request(value):
        built.append(value)
        return prepared(
            "paper-live-one",
            runtime,
        )

    application = PaperTradingApplication(
        prepare_request,
    )

    response = application.start(
        request()
    )

    assert built == [request()]
    assert response.session_id == "paper-live-one"
    assert response.status in {
        "CREATED",
        "RUNNING",
    }

    assert runtime.started.wait(timeout=1.0)

    status = application.status()

    assert status.active is True
    assert status.snapshot is not None
    assert (
        status.snapshot.session_id
        == "paper-live-one"
    )
    assert status.snapshot.status == "RUNNING"

    stopped = application.stop()

    assert stopped.status == "STOPPED"


def test_duplicate_start_rejected_before_second_composition():
    runtime = ControlledRuntime()
    calls = 0

    def prepare_request(value):
        nonlocal calls
        calls += 1

        return prepared(
            f"paper-{calls}",
            runtime,
        )

    application = PaperTradingApplication(
        prepare_request,
    )

    application.start(request())

    assert runtime.started.wait(timeout=1.0)

    with pytest.raises(
        PaperLifecycleConflict,
        match="already active",
    ):
        application.start(request())

    assert calls == 1

    application.stop()


def test_stop_controls_runtime_waits_worker_and_retains_terminal_snapshot():
    runtime = ControlledRuntime()

    application = PaperTradingApplication(
        lambda value: prepared(
            "paper-retained",
            runtime,
        )
    )

    application.start(request())

    assert runtime.started.wait(timeout=1.0)

    stopped = application.stop()

    assert runtime.stop_calls == 1
    assert stopped.session_id == "paper-retained"
    assert stopped.status == "STOPPED"

    status = application.status()

    assert status.active is False
    assert status.snapshot is not None
    assert (
        status.snapshot.session_id
        == "paper-retained"
    )
    assert status.snapshot.status == "STOPPED"


def test_stop_without_active_session_is_conflict():
    application = PaperTradingApplication(
        lambda value: pytest.fail(
            "prepare must not run"
        )
    )

    with pytest.raises(
        PaperLifecycleConflict,
        match="no active",
    ):
        application.stop()


def test_worker_failure_is_retained_as_failed_terminal_snapshot():
    runtime = ControlledRuntime(
        failure=ConnectionError(
            "provider disconnected"
        )
    )

    application = PaperTradingApplication(
        lambda value: prepared(
            "paper-failed",
            runtime,
        )
    )

    application.start(request())

    wait_for(
        lambda: (
            application.status().active
            is False
        )
    )

    status = application.status()

    assert status.snapshot is not None
    assert status.snapshot.status == "FAILED"
    assert (
        status.snapshot.failure_type
        == "ConnectionError"
    )
    assert (
        status.snapshot.failure_message
        == "provider disconnected"
    )


def test_later_start_replaces_retained_terminal_session():
    runtimes = [
        ControlledRuntime(),
        ControlledRuntime(),
    ]
    calls = 0

    def prepare_request(value):
        nonlocal calls

        runtime = runtimes[calls]
        calls += 1

        return prepared(
            f"paper-{calls}",
            runtime,
        )

    application = PaperTradingApplication(
        prepare_request,
    )

    first = application.start(request())

    assert first.session_id == "paper-1"
    assert runtimes[0].started.wait(timeout=1.0)

    application.stop()

    first_terminal = application.status()

    assert first_terminal.active is False
    assert (
        first_terminal.snapshot.session_id
        == "paper-1"
    )

    second = application.start(request())

    assert second.session_id == "paper-2"
    assert runtimes[1].started.wait(timeout=1.0)

    second_status = application.status()

    assert second_status.active is True
    assert (
        second_status.snapshot.session_id
        == "paper-2"
    )

    application.stop()


def test_failed_composition_does_not_destroy_retained_terminal_snapshot():
    runtime = ControlledRuntime()
    attempts = 0

    def prepare_request(value):
        nonlocal attempts
        attempts += 1

        if attempts == 1:
            return prepared(
                "paper-good",
                runtime,
            )

        raise RuntimeError(
            "broker login failed"
        )

    application = PaperTradingApplication(
        prepare_request,
    )

    application.start(request())

    assert runtime.started.wait(timeout=1.0)

    application.stop()

    with pytest.raises(
        RuntimeError,
        match="broker login failed",
    ):
        application.start(request())

    status = application.status()

    assert status.active is False
    assert status.snapshot is not None
    assert (
        status.snapshot.session_id
        == "paper-good"
    )
    assert status.snapshot.status == "STOPPED"


def test_backend_composition_builds_authoritative_angelone_graph(
    monkeypatch,
):
    from datetime import time

    from core.config.app_config import AppConfig
    from core.config.backtest_config import BacktestConfig
    from core.config.paper_data_source import (
        PaperDataSource,
    )
    from core.runtime.dataset_context import (
        DatasetContext,
    )

    first_now = datetime(
        2026,
        1,
        5,
        10,
        7,
        tzinfo=INDIA,
    )
    second_now = datetime(
        2026,
        1,
        5,
        10,
        8,
        tzinfo=INDIA,
    )
    times = iter(
        [
            first_now,
            second_now,
        ]
    )

    app_config = AppConfig(
        paper_data_source=(
            PaperDataSource.ANGELONE
        ),
        paper_session_start=time(9, 15),
        paper_session_end=time(15, 30),
        paper_clock_interval_sec=0.25,
        broker_retry_attempts=4,
        broker_retry_delay_sec=0.75,
        risk_per_trade_pct=2.5,
    )

    paper_config = BacktestConfig(
        symbol="IGNORED",
        timeframe="15m",
        strategy_name="sma_crossover",
        start=first_now,
        end=END,
        initial_capital=250000,
        enable_replay=True,
        enable_visualization=True,
        enable_exports=True,
        timezone="Asia/Kolkata",
        strategy_params={
            "fast_period": 2,
            "slow_period": 5,
        },
    )

    strategy = object()
    source = object()
    feed = object()
    prepared_result = object()
    warmup = [
        object(),
        object(),
    ]
    angelone_config = object()
    captured = {}

    def create_strategy(config):
        captured["strategy_config"] = config
        return strategy

    def load_warmup(**kwargs):
        captured["warmup"] = kwargs
        return warmup

    class StubAngelOneConfig:
        @classmethod
        def load_from_env(cls):
            return angelone_config

    class StubBroker:
        def __init__(
            self,
            *,
            config,
            paper_mode,
            enable_historical_api,
        ):
            captured["broker_init"] = {
                "config": config,
                "paper_mode": paper_mode,
                "enable_historical_api": (
                    enable_historical_api
                ),
            }

        def login(self):
            captured["broker_login"] = True
            return True

        def get_live_market_data_session(self):
            return (
                "auth-token",
                "feed-token",
            )

    def create_feed(**kwargs):
        captured["feed"] = kwargs
        return feed

    def prepare_live(**kwargs):
        captured["prepare"] = kwargs
        return prepared_result

    monkeypatch.setattr(
        application_module,
        "create_strategy",
        create_strategy,
    )
    monkeypatch.setattr(
        application_module,
        "load_live_paper_warmup",
        load_warmup,
    )
    monkeypatch.setattr(
        application_module,
        "AngelOneConfig",
        StubAngelOneConfig,
    )
    monkeypatch.setattr(
        application_module,
        "AngelOneBroker",
        StubBroker,
    )
    monkeypatch.setattr(
        application_module,
        "AngelOneLiveCandleFeed",
        create_feed,
    )
    monkeypatch.setattr(
        application_module,
        "prepare_live_paper_trading",
        prepare_live,
    )

    now = lambda: next(times)

    result = (
        application_module.prepare_paper_trading_request(
            request(),
            app_config=app_config,
            paper_config=paper_config,
            historical_source=source,
            now=now,
        )
    )

    assert result is prepared_result

    strategy_config = captured[
        "strategy_config"
    ]

    assert strategy_config.symbol == "RELIANCE"
    assert (
        strategy_config.strategy_name
        == "sma_crossover"
    )
    assert strategy_config.timeframe == "15m"
    assert (
        strategy_config.initial_capital
        == 250000
    )
    assert strategy_config.strategy_params == {
        "fast_period": 2,
        "slow_period": 5,
    }
    assert strategy_config.enable_replay is False
    assert (
        strategy_config.enable_visualization
        is False
    )
    assert (
        strategy_config.enable_exports
        is False
    )

    warmup_call = captured["warmup"]

    assert (
        warmup_call["historical_source"]
        is source
    )
    assert warmup_call["strategy"] is strategy
    assert (
        warmup_call["dataset_context"]
        == DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
            timezone="Asia/Kolkata",
        )
    )
    assert (
        warmup_call["current_time"]
        == first_now
    )
    assert (
        warmup_call["session_start"].hour
        == 9
    )
    assert (
        warmup_call["session_start"].minute
        == 15
    )

    assert captured["broker_init"] == {
        "config": angelone_config,
        "paper_mode": True,
        "enable_historical_api": False,
    }
    assert captured["broker_login"] is True

    assert captured["feed"] == {
        "config": angelone_config,
        "auth_token": "auth-token",
        "feed_token": "feed-token",
        "symbol": "RELIANCE",
        "timeframe": "15m",
        "session_start": time(9, 15),
    }

    prepared_call = captured["prepare"]

    assert prepared_call["feed"] is feed
    assert prepared_call["strategy"] is strategy
    assert (
        prepared_call[
            "runtime_context"
        ].risk_per_trade_pct
        == 2.5
    )
    assert (
        prepared_call["dataset_context"]
        == DatasetContext(
            symbol="RELIANCE",
            timeframe="15m",
            timezone="Asia/Kolkata",
        )
    )
    assert (
        prepared_call["session_end"].hour
        == 15
    )
    assert (
        prepared_call["session_end"].minute
        == 30
    )
    assert (
        prepared_call["reconnect_attempts"]
        == 4
    )
    assert (
        prepared_call[
            "reconnect_delay_seconds"
        ]
        == 0.75
    )
    assert (
        prepared_call[
            "clock_interval_seconds"
        ]
        == 0.25
    )
    assert (
        prepared_call["initial_capital"]
        == 250000
    )
    assert (
        prepared_call["history_bars"]
        is warmup
    )
    assert (
        prepared_call["historical_source"]
        is source
    )


def test_backend_composition_rejects_non_angelone_source():
    from core.config.app_config import AppConfig
    from core.config.paper_data_source import (
        PaperDataSource,
    )

    with pytest.raises(
        ValueError,
        match="requires ANGELONE",
    ):
        application_module.prepare_paper_trading_request(
            request(),
            app_config=AppConfig(
                paper_data_source=(
                    PaperDataSource.MOCK
                ),
            ),
        )


def test_backend_composition_revalidates_session_after_provider_setup(
    monkeypatch,
):
    from datetime import time

    from core.config.app_config import AppConfig
    from core.config.backtest_config import BacktestConfig
    from core.config.paper_data_source import (
        PaperDataSource,
    )

    before_close = datetime(
        2026,
        1,
        5,
        15,
        29,
        59,
        tzinfo=INDIA,
    )
    at_close = datetime(
        2026,
        1,
        5,
        15,
        30,
        tzinfo=INDIA,
    )
    times = iter(
        [
            before_close,
            at_close,
        ]
    )

    app_config = AppConfig(
        paper_data_source=(
            PaperDataSource.ANGELONE
        ),
        paper_session_start=time(9, 15),
        paper_session_end=time(15, 30),
    )

    paper_config = BacktestConfig(
        symbol="RELIANCE",
        timeframe="15m",
        strategy_name="sma_crossover",
        start=before_close,
        end=at_close,
        initial_capital=100000,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        timezone="Asia/Kolkata",
        strategy_params={
            "fast_period": 1,
            "slow_period": 2,
        },
    )

    class StubAngelOneConfig:
        @classmethod
        def load_from_env(cls):
            return object()

    class StubBroker:
        def __init__(self, **kwargs):
            pass

        def login(self):
            return True

        def get_live_market_data_session(self):
            return (
                "auth-token",
                "feed-token",
            )

    monkeypatch.setattr(
        application_module,
        "load_live_paper_warmup",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        application_module,
        "AngelOneConfig",
        StubAngelOneConfig,
    )
    monkeypatch.setattr(
        application_module,
        "AngelOneBroker",
        StubBroker,
    )
    monkeypatch.setattr(
        application_module,
        "prepare_live_paper_trading",
        lambda **kwargs: pytest.fail(
            "runtime prepared after session close"
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="already ended",
    ):
        application_module.prepare_paper_trading_request(
            request(),
            app_config=app_config,
            paper_config=paper_config,
            historical_source=object(),
            now=lambda: next(times),
        )


def test_concurrent_start_allows_only_one_composition():
    runtime = ControlledRuntime()
    prepare_entered = threading.Event()
    allow_prepare = threading.Event()
    calls = 0
    result = {}

    def prepare_request(value):
        nonlocal calls
        calls += 1
        prepare_entered.set()

        if not allow_prepare.wait(
            timeout=1.0
        ):
            raise RuntimeError(
                "test prepare release timed out"
            )

        return prepared(
            "paper-concurrent",
            runtime,
        )

    application = PaperTradingApplication(
        prepare_request,
    )

    def first_start():
        result["response"] = (
            application.start(
                request()
            )
        )

    thread = threading.Thread(
        target=first_start,
    )
    thread.start()

    assert prepare_entered.wait(
        timeout=1.0
    )

    with pytest.raises(
        PaperLifecycleConflict,
        match="start is already in progress",
    ):
        application.start(
            request()
        )

    assert calls == 1

    allow_prepare.set()

    thread.join(timeout=1.0)

    assert not thread.is_alive()
    assert (
        result["response"].session_id
        == "paper-concurrent"
    )

    assert runtime.started.wait(
        timeout=1.0
    )

    application.stop()


def test_immediate_stop_waits_for_runtime_start_and_worker_exit():
    runtime = ControlledRuntime()

    application = PaperTradingApplication(
        lambda value: prepared(
            "paper-immediate-stop",
            runtime,
        )
    )

    started = application.start(
        request()
    )

    assert (
        started.session_id
        == "paper-immediate-stop"
    )

    stopped = application.stop()

    assert runtime.stop_calls == 1
    assert stopped.status == "STOPPED"

    status = application.status()

    assert status.active is False
    assert status.snapshot is not None
    assert (
        status.snapshot.session_id
        == "paper-immediate-stop"
    )
    assert (
        status.snapshot.status
        == "STOPPED"
    )


def test_status_before_any_session_is_empty():
    application = PaperTradingApplication(
        lambda value: pytest.fail(
            "prepare must not run"
        )
    )

    status = application.status()

    assert status.active is False
    assert status.snapshot is None


def test_natural_worker_completion_retains_stopped_snapshot():
    class NaturalRuntime(ControlledRuntime):
        def run_until(self, **kwargs):
            self.started.set()
            return None

    runtime = NaturalRuntime()

    application = PaperTradingApplication(
        lambda value: prepared(
            "paper-natural-completion",
            runtime,
        )
    )

    application.start(request())

    wait_for(
        lambda: (
            application.status().active
            is False
        )
    )

    status = application.status()

    assert status.active is False
    assert status.snapshot is not None
    assert (
        status.snapshot.session_id
        == "paper-natural-completion"
    )
    assert status.snapshot.status == "STOPPED"

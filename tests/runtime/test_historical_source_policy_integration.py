from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.broker.broker_factory as broker_factory_module
import core.market_data.historical_source_factory as source_factory_module
import core.runtime.backtest_runtime as backtest_runtime_module
import core.runtime.walk_forward_runtime as walk_forward_runtime_module
import main as main_module
from core.broker.angelone_config import AngelOneConfig
from core.config.app_config import AppConfig
from core.config.backtest_config import BacktestConfig
from core.config.historical_source_policy import HistoricalSourcePolicy
from core.config.runtime_mode import RuntimeMode
from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange, find_missing_ranges
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.runtime.dataset_context import DatasetContext


BASE = datetime(2026, 1, 2, 9, 0)
CONTEXT = DatasetContext(
    symbol="RELIANCE",
    timeframe="15m",
    timezone="Asia/Kolkata",
)


def at(minutes: int, *, tzinfo=None) -> datetime:
    return (BASE + timedelta(minutes=minutes)).replace(tzinfo=tzinfo)


def time_range(start: int, end: int, *, tzinfo=None) -> TimeRange:
    return TimeRange(at(start, tzinfo=tzinfo), at(end, tzinfo=tzinfo))


def candle_at(
    minutes: int,
    *,
    tzinfo=None,
    close: float = 100.5,
) -> Candle:
    return Candle(
        timestamp=at(minutes, tzinfo=tzinfo),
        open=100.0,
        high=101.0,
        low=99.0,
        close=close,
        volume=1000.0,
    )


def backtest_config(request: TimeRange) -> BacktestConfig:
    return BacktestConfig(
        symbol=CONTEXT.symbol,
        timeframe=CONTEXT.timeframe,
        strategy_name="sma_crossover",
        start=request.start,
        end=request.end,
        initial_capital=100000,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        timezone=CONTEXT.timezone,
    )


def app_config(
    tmp_path,
    runtime_mode: RuntimeMode,
    policy: HistoricalSourcePolicy,
) -> AppConfig:
    return AppConfig(
        runtime_mode=runtime_mode,
        historical_source_policy=policy,
        historical_database_path=str(tmp_path / "history" / "candles.sqlite3"),
        historical_request_delay_sec=0,
    )


def sqlite_store(config: AppConfig) -> SQLiteCandleStore:
    database_path = Path(config.historical_database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    return SQLiteCandleStore(database_path)


class FakeHistoricalBroker:
    def __init__(self, outcomes=()):
        self.outcomes = list(outcomes)
        self.requests = []

    def get_historical_limits(self) -> dict:
        return {CONTEXT.timeframe: 3650}

    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        self.requests.append((symbol, timeframe, start, end))
        if not self.outcomes:
            raise AssertionError("historical provider was called unexpectedly")
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return list(outcome)


def install_broker_factory(monkeypatch, broker):
    calls = []

    def create_broker(**kwargs):
        calls.append(kwargs)
        return broker

    monkeypatch.setattr(
        source_factory_module,
        "create_angelone_broker",
        create_broker,
    )
    return calls


def run_research_main(
    monkeypatch,
    config: AppConfig,
    request: TimeRange,
) -> list[Candle]:
    captured = []

    if config.runtime_mode is RuntimeMode.BACKTEST:
        class CapturingBacktestEngine:
            def __init__(self, **kwargs):
                pass

            def run_stream(self, candles):
                captured.extend(candles)
                return object()

        monkeypatch.setattr(
            backtest_runtime_module,
            "BacktestEngine",
            CapturingBacktestEngine,
        )
        monkeypatch.setattr(
            backtest_runtime_module,
            "print_performance_summary",
            lambda result: None,
        )
        monkeypatch.setattr(
            main_module,
            "create_strategy",
            lambda value: object(),
        )
    else:
        class CapturingWalkForwardRunner:
            def __init__(self, **kwargs):
                pass

            def run(self, **kwargs):
                captured.extend(kwargs["candles"])
                return SimpleNamespace(
                    windows=[],
                    verdict="PASS",
                    stitched_equity_curve=[],
                )

        class StubReporter:
            def log_summary(self, result):
                pass

        monkeypatch.setattr(
            walk_forward_runtime_module,
            "WalkForwardRunner",
            CapturingWalkForwardRunner,
        )
        monkeypatch.setattr(
            walk_forward_runtime_module,
            "WalkForwardReporter",
            StubReporter,
        )
        monkeypatch.setattr(
            walk_forward_runtime_module,
            "get_strategy_class",
            lambda value: object,
        )
        monkeypatch.setattr(
            walk_forward_runtime_module.EquityVisualizer,
            "plot",
            staticmethod(lambda **kwargs: None),
        )
        monkeypatch.setattr(
            walk_forward_runtime_module,
            "export_walk_forward_results",
            lambda **kwargs: None,
        )

    main_module.main(config, backtest_config(request))
    return captured


@pytest.mark.parametrize(
    "runtime_mode",
    [RuntimeMode.BACKTEST, RuntimeMode.WALK_FORWARD],
)
@pytest.mark.parametrize(
    "policy",
    [HistoricalSourcePolicy.LOCAL_ONLY, HistoricalSourcePolicy.LOCAL_FIRST],
)
def test_fully_covered_research_runtime_is_offline(
    tmp_path,
    monkeypatch,
    runtime_mode,
    policy,
):
    request = time_range(0, 60)
    candles = [candle_at(0), candle_at(30)]
    config = app_config(tmp_path, runtime_mode, policy)
    sqlite_store(config).save_retrieval(
        CONTEXT,
        candles,
        [request],
    )
    credential_calls = []
    broker_calls = []

    def load_credentials(cls):
        credential_calls.append(1)
        raise AssertionError("credentials were loaded for local retrieval")

    def create_broker(**kwargs):
        broker_calls.append(kwargs)
        raise AssertionError("broker was constructed for local retrieval")

    monkeypatch.setattr(
        AngelOneConfig,
        "load_from_env",
        classmethod(load_credentials),
    )
    monkeypatch.setattr(
        source_factory_module,
        "create_angelone_broker",
        create_broker,
    )

    assert run_research_main(monkeypatch, config, request) == candles
    assert credential_calls == []
    assert broker_calls == []


@pytest.mark.parametrize(
    "runtime_mode",
    [RuntimeMode.BACKTEST, RuntimeMode.WALK_FORWARD],
)
def test_missing_local_first_fetches_only_gaps_then_is_durably_warm(
    tmp_path,
    monkeypatch,
    runtime_mode,
):
    request = time_range(0, 60)
    middle = time_range(20, 40)
    gaps = [time_range(0, 20), time_range(40, 60)]
    local = candle_at(30)
    fetched = [candle_at(10), candle_at(50)]
    config = app_config(
        tmp_path,
        runtime_mode,
        HistoricalSourcePolicy.LOCAL_FIRST,
    )
    store = sqlite_store(config)
    store.save_retrieval(CONTEXT, [local], [middle])
    broker = FakeHistoricalBroker([[fetched[0]], [fetched[1]]])
    broker_calls = install_broker_factory(monkeypatch, broker)

    assert run_research_main(monkeypatch, config, request) == [
        fetched[0],
        local,
        fetched[1],
    ]
    assert broker_calls == [
        {"paper_mode": True, "enable_historical_api": True}
    ]
    assert broker.requests == [
        (CONTEXT.symbol, CONTEXT.timeframe, gap.start, gap.end)
        for gap in gaps
    ]
    assert find_missing_ranges(request, store.load_coverage(CONTEXT)) == []

    monkeypatch.setattr(
        source_factory_module,
        "create_angelone_broker",
        lambda **kwargs: pytest.fail("warm retrieval constructed a provider"),
    )
    assert run_research_main(monkeypatch, config, request) == [
        fetched[0],
        local,
        fetched[1],
    ]


@pytest.mark.parametrize(
    "runtime_mode",
    [RuntimeMode.BACKTEST, RuntimeMode.WALK_FORWARD],
)
def test_provider_backed_requires_fresh_provider_evidence(
    tmp_path,
    monkeypatch,
    runtime_mode,
):
    request = time_range(0, 60)
    existing = candle_at(30)
    config = app_config(
        tmp_path,
        runtime_mode,
        HistoricalSourcePolicy.PROVIDER_BACKED,
    )
    store = sqlite_store(config)
    store.save_retrieval(CONTEXT, [existing], [request])
    broker = FakeHistoricalBroker([RuntimeError("fresh provider failed")])
    broker_calls = install_broker_factory(monkeypatch, broker)

    with pytest.raises(RuntimeError, match="fresh provider failed"):
        run_research_main(monkeypatch, config, request)

    assert broker_calls == [
        {"paper_mode": True, "enable_historical_api": True}
    ]
    assert broker.requests == [
        (CONTEXT.symbol, CONTEXT.timeframe, request.start, request.end)
    ]
    assert store.load_coverage(CONTEXT) == [request]
    assert store.load(CONTEXT, request.start, request.end) == [existing]


def test_credential_loading_failure_is_explicit_and_state_safe(
    tmp_path,
    monkeypatch,
    caplog,
):
    request = time_range(0, 60)
    config = app_config(
        tmp_path,
        RuntimeMode.BACKTEST,
        HistoricalSourcePolicy.LOCAL_FIRST,
    )
    store = sqlite_store(config)
    existing = candle_at(30)
    store.save(CONTEXT, [existing])
    secret = "never-log-this-secret"
    construction_calls = []

    def fail_config_loading(cls):
        raise RuntimeError("AngelOne credentials are unavailable")

    def construct_broker(**kwargs):
        construction_calls.append(kwargs)
        raise AssertionError("broker construction followed credential failure")

    monkeypatch.setattr(
        broker_factory_module.AngelOneConfig,
        "load_from_env",
        classmethod(fail_config_loading),
    )
    monkeypatch.setattr(
        broker_factory_module,
        "AngelOneBroker",
        construct_broker,
    )

    with pytest.raises(
        RuntimeError,
        match="AngelOne credentials are unavailable",
    ) as error:
        run_research_main(monkeypatch, config, request)

    assert construction_calls == []
    assert secret not in str(error.value)
    assert secret not in caplog.text
    assert store.load_coverage(CONTEXT) == []
    assert store.load(CONTEXT, request.start, request.end) == [existing]


def test_broker_construction_failure_is_explicit_and_state_safe(
    tmp_path,
    monkeypatch,
    caplog,
):
    request = time_range(0, 60)
    config = app_config(
        tmp_path,
        RuntimeMode.BACKTEST,
        HistoricalSourcePolicy.LOCAL_FIRST,
    )
    store = sqlite_store(config)
    existing = candle_at(30)
    store.save(CONTEXT, [existing])
    secret = "never-log-this-secret"
    angelone_config = AngelOneConfig(
        api_key=secret,
        client_id="test-client",
        client_pin="test-pin",
        totp_secret="test-totp",
    )
    config_load_calls = []
    construction_calls = []
    login_calls = []

    def load_config(cls):
        config_load_calls.append(1)
        return angelone_config

    class FailingBrokerConstructor:
        def __init__(self, **kwargs):
            construction_calls.append(kwargs)
            raise RuntimeError("AngelOne broker construction failed")

        def login(self):
            login_calls.append(1)

    monkeypatch.setattr(
        broker_factory_module.AngelOneConfig,
        "load_from_env",
        classmethod(load_config),
    )
    monkeypatch.setattr(
        broker_factory_module,
        "AngelOneBroker",
        FailingBrokerConstructor,
    )

    with pytest.raises(
        RuntimeError,
        match="AngelOne broker construction failed",
    ) as error:
        run_research_main(monkeypatch, config, request)

    assert config_load_calls == [1]
    assert construction_calls == [
        {
            "config": angelone_config,
            "paper_mode": True,
            "enable_historical_api": True,
        }
    ]
    assert login_calls == []
    assert secret not in str(error.value)
    assert secret not in caplog.text
    assert store.load_coverage(CONTEXT) == []
    assert store.load(CONTEXT, request.start, request.end) == [existing]


def test_broker_login_failure_is_explicit_and_state_safe(
    tmp_path,
    monkeypatch,
    caplog,
):
    request = time_range(0, 60)
    config = app_config(
        tmp_path,
        RuntimeMode.BACKTEST,
        HistoricalSourcePolicy.LOCAL_FIRST,
    )
    store = sqlite_store(config)
    existing = candle_at(30)
    store.save(CONTEXT, [existing])
    secret = "never-log-this-secret"
    angelone_config = AngelOneConfig(
        api_key=secret,
        client_id="test-client",
        client_pin="test-pin",
        totp_secret="test-totp",
    )
    config_load_calls = []
    construction_calls = []
    login_calls = []
    historical_calls = []

    def load_config(cls):
        config_load_calls.append(1)
        return angelone_config

    class LoginFailingBroker:
        def __init__(self, **kwargs):
            construction_calls.append(kwargs)

        def login(self):
            login_calls.append(1)
            raise RuntimeError("AngelOne login failed")

        def get_historical_limits(self):
            historical_calls.append("limits")
            return {CONTEXT.timeframe: 3650}

        def get_historical_candles(self, *args, **kwargs):
            historical_calls.append("candles")
            return []

    monkeypatch.setattr(
        broker_factory_module.AngelOneConfig,
        "load_from_env",
        classmethod(load_config),
    )
    monkeypatch.setattr(
        broker_factory_module,
        "AngelOneBroker",
        LoginFailingBroker,
    )

    with pytest.raises(RuntimeError, match="AngelOne login failed") as error:
        run_research_main(monkeypatch, config, request)

    assert config_load_calls == [1]
    assert construction_calls == [
        {
            "config": angelone_config,
            "paper_mode": True,
            "enable_historical_api": True,
        }
    ]
    assert login_calls == [1]
    assert historical_calls == []
    assert secret not in str(error.value)
    assert secret not in caplog.text
    assert store.load_coverage(CONTEXT) == []
    assert store.load(CONTEXT, request.start, request.end) == [existing]


def test_later_retrieval_failure_preserves_earlier_gap_and_retry_plan(
    tmp_path,
    monkeypatch,
):
    request = time_range(0, 100)
    islands = [time_range(20, 40), time_range(60, 80)]
    gaps = [time_range(0, 20), time_range(40, 60), time_range(80, 100)]
    config = app_config(
        tmp_path,
        RuntimeMode.BACKTEST,
        HistoricalSourcePolicy.LOCAL_FIRST,
    )
    source = source_factory_module.create_historical_source(config)
    source.store.save_retrieval(CONTEXT, [], islands)
    first = candle_at(10)
    broker = FakeHistoricalBroker(
        [[first], RuntimeError("later retrieval failed")]
    )
    install_broker_factory(monkeypatch, broker)
    source = source_factory_module.create_historical_source(config)

    with pytest.raises(RuntimeError, match="later retrieval failed"):
        source.retrieve(CONTEXT, request)

    assert broker.requests == [
        (CONTEXT.symbol, CONTEXT.timeframe, gaps[0].start, gaps[0].end),
        (CONTEXT.symbol, CONTEXT.timeframe, gaps[1].start, gaps[1].end),
    ]
    assert find_missing_ranges(
        request,
        source.store.load_coverage(CONTEXT),
    ) == gaps[1:]
    assert source.store.load(CONTEXT, request.start, request.end) == [first]

    remaining = [candle_at(50), candle_at(90)]
    retry_broker = FakeHistoricalBroker([[remaining[0]], [remaining[1]]])
    install_broker_factory(monkeypatch, retry_broker)
    retry_source = source_factory_module.create_historical_source(config)

    assert retry_source.retrieve(CONTEXT, request) == [first, *remaining]
    assert retry_broker.requests == [
        (CONTEXT.symbol, CONTEXT.timeframe, gap.start, gap.end)
        for gap in gaps[1:]
    ]


def test_confirmed_empty_evidence_is_durable_across_policies(
    tmp_path,
    monkeypatch,
):
    request = time_range(0, 60)
    local_first = app_config(
        tmp_path,
        RuntimeMode.BACKTEST,
        HistoricalSourcePolicy.LOCAL_FIRST,
    )
    initial_broker = FakeHistoricalBroker([[]])
    initial_calls = install_broker_factory(monkeypatch, initial_broker)

    assert source_factory_module.create_historical_source(
        local_first
    ).retrieve(CONTEXT, request) == []
    assert initial_calls == [
        {"paper_mode": True, "enable_historical_api": True}
    ]

    monkeypatch.setattr(
        source_factory_module,
        "create_angelone_broker",
        lambda **kwargs: pytest.fail("durable empty coverage was ignored"),
    )
    assert source_factory_module.create_historical_source(
        local_first
    ).retrieve(CONTEXT, request) == []

    local_only = app_config(
        tmp_path,
        RuntimeMode.BACKTEST,
        HistoricalSourcePolicy.LOCAL_ONLY,
    )
    assert source_factory_module.create_historical_source(
        local_only
    ).retrieve(CONTEXT, request) == []

    provider_backed = app_config(
        tmp_path,
        RuntimeMode.BACKTEST,
        HistoricalSourcePolicy.PROVIDER_BACKED,
    )
    fresh_broker = FakeHistoricalBroker([[]])
    fresh_calls = install_broker_factory(monkeypatch, fresh_broker)
    assert source_factory_module.create_historical_source(
        provider_backed
    ).retrieve(CONTEXT, request) == []
    assert fresh_calls == [
        {"paper_mode": True, "enable_historical_api": True}
    ]
    assert fresh_broker.requests == [
        (CONTEXT.symbol, CONTEXT.timeframe, request.start, request.end)
    ]


@pytest.mark.parametrize(
    ("persisted_tz", "request_tz"),
    [
        (None, timezone.utc),
        (timezone.utc, None),
    ],
)
def test_persisted_request_awareness_fails_before_provider(
    tmp_path,
    monkeypatch,
    persisted_tz,
    request_tz,
):
    persisted = time_range(0, 60, tzinfo=persisted_tz)
    request = time_range(0, 60, tzinfo=request_tz)
    config = app_config(
        tmp_path,
        RuntimeMode.BACKTEST,
        HistoricalSourcePolicy.LOCAL_FIRST,
    )
    store = sqlite_store(config)
    store.save_retrieval(CONTEXT, [], [persisted])
    calls = []
    monkeypatch.setattr(
        source_factory_module,
        "create_angelone_broker",
        lambda **kwargs: calls.append(kwargs),
    )
    source = source_factory_module.create_historical_source(config)

    with pytest.raises(ValueError, match="timezone awareness"):
        source.retrieve(CONTEXT, request)

    assert calls == []
    assert store.load_coverage(CONTEXT) == [persisted]


def test_provider_awareness_failure_persists_no_evidence(
    tmp_path,
    monkeypatch,
):
    request = time_range(0, 60)
    config = app_config(
        tmp_path,
        RuntimeMode.BACKTEST,
        HistoricalSourcePolicy.LOCAL_FIRST,
    )
    aware_candle = candle_at(30, tzinfo=timezone.utc)
    broker = FakeHistoricalBroker([[aware_candle]])
    install_broker_factory(monkeypatch, broker)
    source = source_factory_module.create_historical_source(config)

    with pytest.raises(ValueError, match="timezone awareness"):
        source.retrieve(CONTEXT, request)

    assert source.store.load_coverage(CONTEXT) == []
    assert source.store.load(CONTEXT, request.start, request.end) == []


def test_provider_timestamp_representation_is_not_normalized(
    tmp_path,
    monkeypatch,
):
    india = timezone(timedelta(hours=5, minutes=30))
    request = time_range(0, 60, tzinfo=india)
    original = candle_at(30, tzinfo=india)
    metadata_only_context = DatasetContext(
        symbol=CONTEXT.symbol,
        timeframe=CONTEXT.timeframe,
        timezone="UTC",
    )
    config = app_config(
        tmp_path,
        RuntimeMode.BACKTEST,
        HistoricalSourcePolicy.LOCAL_FIRST,
    )
    broker = FakeHistoricalBroker([[original]])
    install_broker_factory(monkeypatch, broker)
    source = source_factory_module.create_historical_source(config)

    result = source.retrieve(metadata_only_context, request)

    assert len(result) == 1
    assert result[0].timestamp.isoformat() == original.timestamp.isoformat()
    assert result[0].timestamp.utcoffset() == timedelta(hours=5, minutes=30)
    assert source.store.load_coverage(metadata_only_context)[0].start.isoformat() == (
        request.start.isoformat()
    )

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import core.runtime.backtest_runtime as backtest_runtime_module
import core.runtime.walk_forward_runtime as walk_forward_runtime_module
import main as main_module
from core.config.app_config import AppConfig
from core.config.backtest_config import BacktestConfig
from core.config.paper_data_source import PaperDataSource
from core.config.runtime_mode import RuntimeMode
from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext


START = datetime(2026, 1, 2, 9, 15)


def config() -> BacktestConfig:
    return BacktestConfig(
        symbol="RELIANCE",
        timeframe="15m",
        strategy_name="sma_crossover",
        start=START,
        end=START + timedelta(hours=1),
        initial_capital=100000,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        timezone="Asia/Kolkata",
    )


def candle() -> Candle:
    return Candle(
        timestamp=START,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000.0,
    )


class SpyHistoricalSource:
    def __init__(self, candles=()):
        self.candles = list(candles)
        self.requests = []

    def retrieve(self, dataset_context, request):
        self.requests.append((dataset_context, request))
        return list(self.candles)


def test_backtest_runtime_retrieves_through_historical_source(monkeypatch):
    source = SpyHistoricalSource([candle()])
    dataset_context = DatasetContext(
        symbol="RELIANCE",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )
    captured = {}

    class SpyBacktestEngine:
        def __init__(self, **kwargs):
            captured["engine_kwargs"] = kwargs

        def run_stream(self, candles):
            captured["candles"] = list(candles)
            return object()

    monkeypatch.setattr(
        backtest_runtime_module,
        "BacktestEngine",
        SpyBacktestEngine,
    )
    monkeypatch.setattr(
        backtest_runtime_module,
        "print_performance_summary",
        lambda result: None,
    )

    backtest_runtime_module.run_backtest(
        historical_source=source,
        strategy=object(),
        config=config(),
        runtime_context=RuntimeContext(),
        dataset_context=dataset_context,
    )

    assert source.requests == [
        (dataset_context, TimeRange(config().start, config().end))
    ]
    assert captured["candles"] == [candle()]
    assert captured["engine_kwargs"]["dataset_context"] is dataset_context


def test_walk_forward_runtime_retrieves_through_same_historical_source(
    monkeypatch,
):
    source = SpyHistoricalSource([candle()])
    captured = {}

    class SpyWalkForwardRunner:
        def __init__(self, **kwargs):
            pass

        def run(self, **kwargs):
            captured.update(kwargs)
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
        SpyWalkForwardRunner,
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

    runtime_context = RuntimeContext(
        risk_per_trade_pct=2.5,
    )
    walk_forward_runtime_module.run_walk_forward(
        historical_source=source,
        config=config(),
        runtime_context=runtime_context,
    )

    expected_context = DatasetContext(
        symbol="RELIANCE",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )
    assert source.requests == [
        (expected_context, TimeRange(config().start, config().end))
    ]
    assert captured["candles"] == [candle()]
    assert captured["dataset_context"] == expected_context
    assert captured["initial_capital"] == 100000
    assert captured["runtime_context"] is runtime_context




def test_walk_forward_runtime_rejects_unvalidated_strategy_before_retrieval(
    monkeypatch,
):
    source = SpyHistoricalSource([candle()])

    unsupported = BacktestConfig(
        symbol="RELIANCE",
        timeframe="15m",
        strategy_name="pivotboss",
        start=START,
        end=START + timedelta(hours=1),
        initial_capital=100000,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        timezone="Asia/Kolkata",
    )

    monkeypatch.setattr(
        walk_forward_runtime_module,
        "get_strategy_class",
        lambda value: pytest.fail(
            "unsupported WFA strategy reached strategy factory"
        ),
    )

    with pytest.raises(
        ValueError,
        match="only the validated sma_crossover strategy",
    ):
        walk_forward_runtime_module.run_walk_forward(
            historical_source=source,
            config=unsupported,
            runtime_context=RuntimeContext(),
        )

    assert source.requests == []


def test_main_backtest_composes_and_passes_historical_source(monkeypatch):
    source = object()
    captured = {}
    app_config = AppConfig(
        runtime_mode=RuntimeMode.BACKTEST,
        risk_per_trade_pct=2.5,
    )

    def create_source(value):
        captured["factory_config"] = value
        return source

    monkeypatch.setattr(
        main_module,
        "create_historical_source",
        create_source,
    )
    monkeypatch.setattr(main_module, "create_strategy", lambda value: object())
    monkeypatch.setattr(
        main_module,
        "run_backtest",
        lambda **kwargs: captured.update(runtime_kwargs=kwargs),
    )

    main_module.main(app_config, config())

    assert captured["factory_config"] is app_config
    assert captured["runtime_kwargs"]["historical_source"] is source
    assert "broker" not in captured["runtime_kwargs"]
    assert (
        captured["runtime_kwargs"]["runtime_context"].risk_per_trade_pct
        == 2.5
    )


def test_main_walk_forward_composes_and_passes_historical_source(monkeypatch):
    source = object()
    captured = {}
    app_config = AppConfig(
        runtime_mode=RuntimeMode.WALK_FORWARD,
        risk_per_trade_pct=2.5,
    )

    def create_source(value):
        captured["factory_config"] = value
        return source

    monkeypatch.setattr(
        main_module,
        "create_historical_source",
        create_source,
    )
    monkeypatch.setattr(
        main_module,
        "run_walk_forward",
        lambda **kwargs: captured.update(runtime_kwargs=kwargs),
    )

    main_module.main(app_config, config())

    assert captured["factory_config"] is app_config
    runtime_kwargs = captured["runtime_kwargs"]

    assert runtime_kwargs["historical_source"] is source
    assert runtime_kwargs["config"] == config()
    assert (
        runtime_kwargs["runtime_context"].risk_per_trade_pct
        == 2.5
    )


def test_main_paper_does_not_compose_historical_source(monkeypatch):
    feed = object()
    monkeypatch.setattr(
        main_module,
        "create_historical_source",
        lambda value: pytest.fail("historical source was composed for PAPER"),
    )
    monkeypatch.setattr(main_module, "load_candles_from_csv", lambda **kwargs: [])
    monkeypatch.setattr(main_module, "MockLiveFeed", lambda **kwargs: feed)
    monkeypatch.setattr(main_module, "create_strategy", lambda value: object())
    monkeypatch.setattr(main_module, "run_paper_trading", lambda **kwargs: None)

    main_module.main(AppConfig(runtime_mode=RuntimeMode.PAPER), config())


def test_main_live_does_not_compose_historical_source(monkeypatch):
    calls = []
    monkeypatch.setattr(
        main_module,
        "create_historical_source",
        lambda value: pytest.fail("historical source was composed for LIVE"),
    )
    monkeypatch.setattr(main_module, "run_live_trading", lambda: calls.append(1))

    main_module.main(AppConfig(runtime_mode=RuntimeMode.LIVE), config())

    assert calls == [1]



def test_main_paper_angelone_composes_live_feed_and_supervisor(
    monkeypatch,
):
    import pytz

    captured = {}
    angelone_config = object()
    feed = object()
    strategy = object()
    ist = pytz.timezone("Asia/Kolkata")
    fixed_now = ist.localize(
        datetime(2026, 1, 2, 10, 0)
    )
    real_datetime = datetime

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

        @classmethod
        def combine(cls, date_value, time_value):
            return real_datetime.combine(
                date_value,
                time_value,
            )

    class StubAngelOneConfig:
        @classmethod
        def load_from_env(cls):
            captured["config_loaded"] = True
            return angelone_config

    class StubBroker:
        def __init__(
            self,
            *,
            config,
            paper_mode,
            enable_historical_api,
        ):
            captured["broker_config"] = config
            captured["paper_mode"] = paper_mode
            captured["enable_historical_api"] = (
                enable_historical_api
            )

        def login(self):
            captured["login"] = True
            return True

        def get_live_market_data_session(self):
            return (
                "Bearer jwt-token",
                "feed-token",
            )

    def create_feed(**kwargs):
        captured["feed_kwargs"] = kwargs
        return feed

    monkeypatch.setattr(
        main_module,
        "datetime",
        FixedDateTime,
    )
    monkeypatch.setattr(
        main_module,
        "AngelOneConfig",
        StubAngelOneConfig,
    )
    monkeypatch.setattr(
        main_module,
        "AngelOneBroker",
        StubBroker,
    )
    monkeypatch.setattr(
        main_module,
        "AngelOneLiveCandleFeed",
        create_feed,
    )
    monkeypatch.setattr(
        main_module,
        "create_strategy",
        lambda value: strategy,
    )
    monkeypatch.setattr(
        main_module,
        "load_candles_from_csv",
        lambda **kwargs: pytest.fail(
            "mock candles loaded for ANGELONE PAPER"
        ),
    )
    monkeypatch.setattr(
        main_module,
        "run_paper_trading",
        lambda **kwargs: pytest.fail(
            "mock PAPER runtime used for ANGELONE"
        ),
    )
    monkeypatch.setattr(
        main_module,
        "run_live_paper_trading",
        lambda **kwargs: captured.update(
            live_runtime_kwargs=kwargs
        ),
    )

    app_config = AppConfig(
        runtime_mode=RuntimeMode.PAPER,
        paper_data_source=PaperDataSource.ANGELONE,
        risk_per_trade_pct=2.5,
        broker_retry_attempts=3,
        broker_retry_delay_sec=1.5,
        paper_clock_interval_sec=0.5,
    )

    main_module.main(
        app_config,
        config(),
    )

    assert captured["config_loaded"] is True
    assert captured["broker_config"] is angelone_config
    assert captured["paper_mode"] is True
    assert captured["enable_historical_api"] is False
    assert captured["login"] is True

    assert captured["feed_kwargs"] == {
        "config": angelone_config,
        "auth_token": "Bearer jwt-token",
        "feed_token": "feed-token",
        "symbol": "RELIANCE",
        "timeframe": "15m",
        "session_start": app_config.paper_session_start,
    }

    runtime_kwargs = captured["live_runtime_kwargs"]

    assert runtime_kwargs["feed"] is feed
    assert runtime_kwargs["strategy"] is strategy
    assert (
        runtime_kwargs["runtime_context"].risk_per_trade_pct
        == 2.5
    )
    assert runtime_kwargs["dataset_context"] == DatasetContext(
        symbol="RELIANCE",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )
    assert runtime_kwargs["session_end"] == ist.localize(
        real_datetime(
            2026,
            1,
            2,
            15,
            30,
        )
    )
    assert runtime_kwargs["now"]() == fixed_now
    assert runtime_kwargs["reconnect_attempts"] == 3
    assert runtime_kwargs["reconnect_delay_seconds"] == 1.5
    assert runtime_kwargs["clock_interval_seconds"] == 0.5
    assert runtime_kwargs["initial_capital"] == 100000



@pytest.mark.parametrize(
    ("hour", "minute", "match"),
    [
        (9, 14, "has not started"),
        (15, 30, "already ended"),
    ],
)
def test_main_paper_angelone_rejects_outside_session_before_provider_setup(
    monkeypatch,
    hour,
    minute,
    match,
):
    import pytz

    ist = pytz.timezone("Asia/Kolkata")
    fixed_now = ist.localize(
        datetime(
            2026,
            1,
            2,
            hour,
            minute,
        )
    )

    class FixedDateTime:
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    class ForbiddenAngelOneConfig:
        @classmethod
        def load_from_env(cls):
            pytest.fail(
                "AngelOne provider setup reached outside session"
            )

    monkeypatch.setattr(
        main_module,
        "datetime",
        FixedDateTime,
    )
    monkeypatch.setattr(
        main_module,
        "AngelOneConfig",
        ForbiddenAngelOneConfig,
    )
    monkeypatch.setattr(
        main_module,
        "create_strategy",
        lambda value: object(),
    )

    with pytest.raises(
        RuntimeError,
        match=match,
    ):
        main_module.main(
            AppConfig(
                runtime_mode=RuntimeMode.PAPER,
                paper_data_source=PaperDataSource.ANGELONE,
            ),
            config(),
        )



def test_configured_application_uses_loaded_app_config(
    monkeypatch,
):
    app_config = AppConfig(
        runtime_mode=RuntimeMode.PAPER,
        paper_data_source=PaperDataSource.ANGELONE,
    )
    backtest_config = object()
    captured = {}

    monkeypatch.setattr(
        main_module,
        "load_app_config",
        lambda: app_config,
    )
    monkeypatch.setattr(
        main_module,
        "BACKTEST_CONFIG",
        backtest_config,
    )
    monkeypatch.setattr(
        main_module,
        "main",
        lambda app_config, backtest_config: captured.update(
            app_config=app_config,
            backtest_config=backtest_config,
        ),
    )

    main_module.run_configured_application()

    assert captured == {
        "app_config": app_config,
        "backtest_config": backtest_config,
    }

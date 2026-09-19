from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

import core.runtime.backtest_runtime as backtest_runtime_module
import core.runtime.walk_forward_runtime as walk_forward_runtime_module
import main as main_module
from core.config.app_config import AppConfig
from core.config.backtest_config import BacktestConfig
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

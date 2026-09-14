from datetime import datetime
from types import SimpleNamespace

import core.runtime.walk_forward_runtime as walk_forward_runtime_module
import main as main_module
from core.config.app_config import AppConfig
from core.config.backtest_config import BacktestConfig
from core.config.runtime_mode import RuntimeMode
from core.runtime.dataset_context import DatasetContext


def backtest_config_values() -> dict:
    return {
        "symbol": "RELIANCE",
        "timeframe": "15m",
        "strategy_name": "sma_crossover",
        "start": datetime(2026, 1, 2, 9, 15),
        "end": datetime(2026, 1, 2, 15, 30),
        "initial_capital": 100000,
        "enable_replay": False,
        "enable_visualization": False,
        "enable_exports": False,
    }


def assert_nse_dataset_identity(dataset_context: DatasetContext) -> None:
    assert dataset_context.symbol == "RELIANCE"
    assert dataset_context.timeframe == "15m"
    assert dataset_context.timezone == "Asia/Kolkata"


def test_dataset_context_represents_optional_timezone():
    dataset_context = DatasetContext(
        symbol="RELIANCE",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )

    assert_nse_dataset_identity(dataset_context)

    symbol_only_context = DatasetContext(symbol="TEST")

    assert symbol_only_context.timeframe is None
    assert symbol_only_context.timezone is None


def test_backtest_config_represents_optional_timezone():
    config = BacktestConfig(
        **backtest_config_values(),
        timezone="Asia/Kolkata",
    )

    assert config.timezone == "Asia/Kolkata"


def test_main_backtest_propagates_dataset_timezone(monkeypatch):
    captured = {}
    config = BacktestConfig(
        **backtest_config_values(),
        timezone="Asia/Kolkata",
    )

    monkeypatch.setattr(
        main_module,
        "create_historical_source",
        lambda app_config: object(),
    )
    monkeypatch.setattr(main_module, "create_strategy", lambda config: object())
    monkeypatch.setattr(
        main_module,
        "run_backtest",
        lambda **kwargs: captured.update(
            dataset_context=kwargs["dataset_context"]
        ),
    )

    main_module.main(
        app_config=AppConfig(runtime_mode=RuntimeMode.BACKTEST),
        backtest_config=config,
    )

    assert_nse_dataset_identity(captured["dataset_context"])


def test_main_paper_propagates_dataset_timezone(monkeypatch):
    captured = {}
    config = BacktestConfig(
        **backtest_config_values(),
        timezone="Asia/Kolkata",
    )
    feed = object()

    def unexpected_historical_source(app_config):
        raise AssertionError("historical source was composed for PAPER")

    monkeypatch.setattr(
        main_module,
        "create_historical_source",
        unexpected_historical_source,
    )
    monkeypatch.setattr(main_module, "load_candles_from_csv", lambda **kwargs: [])
    monkeypatch.setattr(main_module, "MockLiveFeed", lambda **kwargs: feed)
    monkeypatch.setattr(main_module, "create_strategy", lambda config: object())
    monkeypatch.setattr(
        main_module,
        "run_paper_trading",
        lambda **kwargs: captured.update(
            dataset_context=kwargs["dataset_context"]
        ),
    )

    main_module.main(
        app_config=AppConfig(runtime_mode=RuntimeMode.PAPER),
        backtest_config=config,
    )

    assert_nse_dataset_identity(captured["dataset_context"])


def test_walk_forward_runtime_propagates_dataset_timezone(monkeypatch):
    captured = {}
    config = BacktestConfig(
        **backtest_config_values(),
        timezone="Asia/Kolkata",
    )

    class StubHistoricalSource:
        def retrieve(self, dataset_context, request):
            return []

    class SpyWalkForwardRunner:
        def __init__(self, **kwargs):
            pass

        def run(self, **kwargs):
            captured["dataset_context"] = kwargs["dataset_context"]
            return SimpleNamespace(windows=[], verdict="PASS")

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
        lambda config: object,
    )
    monkeypatch.setattr(
        walk_forward_runtime_module.EquityStitcher,
        "stitch",
        staticmethod(lambda windows: []),
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

    walk_forward_runtime_module.run_walk_forward(
        historical_source=StubHistoricalSource(),
        config=config,
    )

    assert_nse_dataset_identity(captured["dataset_context"])

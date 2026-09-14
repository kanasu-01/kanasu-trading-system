from datetime import datetime, timedelta, timezone

import pytest

import core.market_data.historical_source_factory as factory_module
from core.broker.angelone_config import AngelOneConfig
from core.config.app_config import AppConfig
from core.config.backtest_config import BACKTEST_CONFIG
from core.config.historical_source_policy import HistoricalSourcePolicy
from core.config.loaders import load_app_config
from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.runtime.dataset_context import DatasetContext


CONTEXT = DatasetContext(
    symbol="RELIANCE",
    timeframe="15m",
    timezone="Asia/Kolkata",
)
START = datetime(2026, 1, 2, 9, 15)
REQUEST = TimeRange(START, START + timedelta(hours=1))


def candle_at(timestamp: datetime) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=1000.0,
    )


class FakeHistoricalBroker:
    def __init__(self, candles=()):
        self.candles = list(candles)
        self.requests = []

    def get_historical_limits(self) -> dict:
        return {"15m": 1}

    def get_historical_candles(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        self.requests.append((symbol, timeframe, start, end))
        return list(self.candles)


def app_config(tmp_path, policy: HistoricalSourcePolicy) -> AppConfig:
    return AppConfig(
        historical_source_policy=policy,
        historical_database_path=str(tmp_path / "store" / "candles.sqlite3"),
        historical_request_delay_sec=0,
    )


def test_app_config_exposes_historical_defaults():
    config = AppConfig()

    assert config.historical_source_policy is HistoricalSourcePolicy.LOCAL_FIRST
    assert config.historical_database_path == "data/historical.sqlite3"
    assert config.historical_request_delay_sec == 0.5


def test_config_loader_reads_historical_environment(monkeypatch):
    monkeypatch.setenv("TRADING_MODE", "BACKTEST")
    monkeypatch.setenv("HISTORICAL_SOURCE_POLICY", "LOCAL_ONLY")
    monkeypatch.setenv("HISTORICAL_DATABASE_PATH", "custom/history.sqlite3")
    monkeypatch.setenv("HISTORICAL_REQUEST_DELAY_SEC", "1.25")

    config = load_app_config()

    assert config.historical_source_policy is HistoricalSourcePolicy.LOCAL_ONLY
    assert config.historical_database_path == "custom/history.sqlite3"
    assert config.historical_request_delay_sec == 1.25


def test_config_loader_preserves_historical_defaults(monkeypatch):
    monkeypatch.setenv("TRADING_MODE", "BACKTEST")
    monkeypatch.delenv("HISTORICAL_SOURCE_POLICY", raising=False)
    monkeypatch.delenv("HISTORICAL_DATABASE_PATH", raising=False)
    monkeypatch.delenv("HISTORICAL_REQUEST_DELAY_SEC", raising=False)

    config = load_app_config()

    assert config.historical_source_policy is HistoricalSourcePolicy.LOCAL_FIRST
    assert config.historical_database_path == "data/historical.sqlite3"
    assert config.historical_request_delay_sec == 0.5


def test_composition_creates_database_parent_without_external_side_effects(
    tmp_path,
    monkeypatch,
):
    config = app_config(tmp_path, HistoricalSourcePolicy.LOCAL_ONLY)
    calls = {"credentials": 0, "broker": 0}

    def unexpected_credentials(cls):
        calls["credentials"] += 1
        raise AssertionError("credentials were loaded during composition")

    def unexpected_broker(**kwargs):
        calls["broker"] += 1
        raise AssertionError("broker was constructed during composition")

    monkeypatch.setattr(
        AngelOneConfig,
        "load_from_env",
        classmethod(unexpected_credentials),
    )
    monkeypatch.setattr(
        factory_module,
        "create_angelone_broker",
        unexpected_broker,
    )

    source = factory_module.create_historical_source(config)

    assert source.policy is HistoricalSourcePolicy.LOCAL_ONLY
    assert calls == {"credentials": 0, "broker": 0}
    assert (tmp_path / "store").is_dir()
    assert (tmp_path / "store" / "candles.sqlite3").is_file()


@pytest.mark.parametrize(
    "policy",
    [
        pytest.param(HistoricalSourcePolicy.LOCAL_ONLY, id="local-only"),
        pytest.param(HistoricalSourcePolicy.LOCAL_FIRST, id="local-first"),
    ],
)
def test_complete_local_coverage_never_constructs_external_provider(
    tmp_path,
    monkeypatch,
    policy,
):
    config = app_config(tmp_path, policy)
    broker_calls = []
    monkeypatch.setattr(
        factory_module,
        "create_angelone_broker",
        lambda **kwargs: broker_calls.append(kwargs),
    )
    source = factory_module.create_historical_source(config)
    candle = candle_at(START)
    source.store.save_retrieval(CONTEXT, [candle], [REQUEST])

    assert source.retrieve(CONTEXT, REQUEST) == [candle]
    assert broker_calls == []


def test_missing_local_first_constructs_provider_after_coverage_check(
    tmp_path,
    monkeypatch,
):
    config = app_config(tmp_path, HistoricalSourcePolicy.LOCAL_FIRST)
    events = []
    broker = FakeHistoricalBroker()

    def create_broker(**kwargs):
        events.append(("provider", kwargs))
        return broker

    monkeypatch.setattr(
        factory_module,
        "create_angelone_broker",
        create_broker,
    )
    source = factory_module.create_historical_source(config)
    original_load_coverage = source.store.load_coverage

    def load_coverage(context):
        events.append(("coverage", context))
        return original_load_coverage(context)

    source.store.load_coverage = load_coverage

    assert source.retrieve(CONTEXT, REQUEST) == []
    assert events[0] == ("coverage", CONTEXT)
    assert events[1] == (
        "provider",
        {"paper_mode": True, "enable_historical_api": True},
    )
    assert broker.requests == [
        (CONTEXT.symbol, CONTEXT.timeframe, REQUEST.start, REQUEST.end)
    ]


def test_provider_backed_constructs_provider_despite_local_coverage(
    tmp_path,
    monkeypatch,
):
    config = app_config(tmp_path, HistoricalSourcePolicy.PROVIDER_BACKED)
    broker = FakeHistoricalBroker()
    broker_calls = []

    def create_broker(**kwargs):
        broker_calls.append(kwargs)
        return broker

    monkeypatch.setattr(
        factory_module,
        "create_angelone_broker",
        create_broker,
    )
    source = factory_module.create_historical_source(config)
    source.store.save_retrieval(CONTEXT, [], [REQUEST])

    assert source.retrieve(CONTEXT, REQUEST) == []
    assert broker_calls == [
        {"paper_mode": True, "enable_historical_api": True}
    ]
    assert broker.requests == [
        (CONTEXT.symbol, CONTEXT.timeframe, REQUEST.start, REQUEST.end)
    ]


def test_configured_request_delay_reaches_historical_feed(
    tmp_path,
    monkeypatch,
):
    config = app_config(tmp_path, HistoricalSourcePolicy.PROVIDER_BACKED)
    config.historical_request_delay_sec = 1.25
    broker = FakeHistoricalBroker()
    monkeypatch.setattr(
        factory_module,
        "create_angelone_broker",
        lambda **kwargs: broker,
    )
    source = factory_module.create_historical_source(config)

    provider = source.provider_factory()

    assert provider.feed.broker is broker
    assert provider.feed.request_delay_sec == 1.25


def test_default_backtest_config_uses_explicit_asia_kolkata_bounds():
    expected_offset = timedelta(hours=5, minutes=30)

    assert BACKTEST_CONFIG.timezone == "Asia/Kolkata"
    assert BACKTEST_CONFIG.start.utcoffset() == expected_offset
    assert BACKTEST_CONFIG.end.utcoffset() == expected_offset
    assert BACKTEST_CONFIG.start.tzname() == "Asia/Kolkata"
    assert BACKTEST_CONFIG.end.tzname() == "Asia/Kolkata"


def test_request_awareness_is_not_derived_from_dataset_timezone(tmp_path):
    config = app_config(tmp_path, HistoricalSourcePolicy.LOCAL_ONLY)
    source = factory_module.create_historical_source(config)
    aware_start = START.replace(tzinfo=timezone.utc)
    aware_request = TimeRange(
        aware_start,
        aware_start + timedelta(hours=1),
    )
    source.store.save_retrieval(CONTEXT, [], [aware_request])

    with pytest.raises(ValueError, match="timezone awareness"):
        source.retrieve(CONTEXT, REQUEST)

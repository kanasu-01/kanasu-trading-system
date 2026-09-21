from datetime import time

from core.config.app_config import AppConfig
from core.config.loaders import load_app_config
from core.config.paper_data_source import PaperDataSource
from core.config.runtime_mode import RuntimeMode


def test_paper_runtime_defaults_to_mock_nse_session() -> None:
    config = AppConfig(
        runtime_mode=RuntimeMode.PAPER,
    )

    assert config.paper_data_source is PaperDataSource.MOCK
    assert config.paper_session_start == time(9, 15)
    assert config.paper_session_end == time(15, 30)
    assert config.paper_clock_interval_sec == 1.0
    assert config.enable_live_trading is False


def test_load_app_config_reads_paper_runtime_settings(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRADING_MODE", "PAPER")
    monkeypatch.setenv("PAPER_DATA_SOURCE", "ANGELONE")
    monkeypatch.setenv("PAPER_SESSION_START", "09:20")
    monkeypatch.setenv("PAPER_SESSION_END", "15:25")
    monkeypatch.setenv("PAPER_CLOCK_INTERVAL_SEC", "0.5")

    config = load_app_config()

    assert config.runtime_mode is RuntimeMode.PAPER
    assert config.paper_data_source is PaperDataSource.ANGELONE
    assert config.paper_session_start == time(9, 20)
    assert config.paper_session_end == time(15, 25)
    assert config.paper_clock_interval_sec == 0.5
    assert config.enable_live_trading is False

from core.config.loaders import load_app_config


def test_load_app_config_uses_broker_retry_defaults(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRADING_MODE", "BACKTEST")
    monkeypatch.setenv("PAPER_DATA_SOURCE", "MOCK")
    monkeypatch.setenv(
        "HISTORICAL_SOURCE_POLICY",
        "LOCAL_FIRST",
    )
    monkeypatch.delenv(
        "BROKER_RETRY_ATTEMPTS",
        raising=False,
    )
    monkeypatch.delenv(
        "BROKER_RETRY_DELAY_SEC",
        raising=False,
    )

    config = load_app_config()

    assert config.broker_retry_attempts == 2
    assert config.broker_retry_delay_sec == 2.0


def test_load_app_config_reads_broker_retry_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TRADING_MODE", "BACKTEST")
    monkeypatch.setenv("PAPER_DATA_SOURCE", "MOCK")
    monkeypatch.setenv(
        "HISTORICAL_SOURCE_POLICY",
        "LOCAL_FIRST",
    )
    monkeypatch.setenv(
        "BROKER_RETRY_ATTEMPTS",
        "5",
    )
    monkeypatch.setenv(
        "BROKER_RETRY_DELAY_SEC",
        "0.75",
    )

    config = load_app_config()

    assert config.broker_retry_attempts == 5
    assert config.broker_retry_delay_sec == 0.75
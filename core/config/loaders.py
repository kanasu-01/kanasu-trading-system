import os
from datetime import time

from core.config.app_config import AppConfig
from core.config.historical_source_policy import HistoricalSourcePolicy
from core.config.paper_data_source import PaperDataSource
from core.config.runtime_mode import RuntimeMode


def load_app_config() -> AppConfig:
    """
    Load application config from environment variables.
    """

    mode = os.getenv("TRADING_MODE", "DEV").upper()

    return AppConfig(
        runtime_mode=RuntimeMode(mode),
        initial_capital=float(os.getenv("INITIAL_CAPITAL", 1_000_000)),
        risk_per_trade_pct=float(os.getenv("RISK_PER_TRADE_PCT", 1.0)),
        enable_live_trading=os.getenv("ENABLE_LIVE_TRADING", "false").lower() == "true",
        paper_data_source=PaperDataSource(
            os.getenv("PAPER_DATA_SOURCE", "MOCK").upper()
        ),
        paper_session_start=time.fromisoformat(
            os.getenv("PAPER_SESSION_START", "09:15")
        ),
        paper_session_end=time.fromisoformat(
            os.getenv("PAPER_SESSION_END", "15:30")
        ),
        paper_clock_interval_sec=float(
            os.getenv("PAPER_CLOCK_INTERVAL_SEC", 1.0)
        ),
        slippage_pct=float(os.getenv("SLIPPAGE_PCT", 0.05)),
        brokerage_pct=float(os.getenv("BROKERAGE_PCT", 0.01)),
        journal_dir=os.getenv("JOURNAL_DIR", "journals"),
        historical_source_policy=HistoricalSourcePolicy(
            os.getenv("HISTORICAL_SOURCE_POLICY", "LOCAL_FIRST").upper()
        ),
        historical_database_path=os.getenv(
            "HISTORICAL_DATABASE_PATH",
            "data/historical.sqlite3",
        ),
        historical_request_delay_sec=float(
            os.getenv("HISTORICAL_REQUEST_DELAY_SEC", 0.5)
        ),
    )

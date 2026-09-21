from dataclasses import dataclass
from datetime import time

from core.config.historical_source_policy import HistoricalSourcePolicy
from core.config.paper_data_source import PaperDataSource
from core.config.runtime_mode import RuntimeMode


@dataclass
class AppConfig:
    """
    Central application configuration.
    """

    runtime_mode: RuntimeMode = RuntimeMode.BACKTEST

    # Capital & risk
    initial_capital: float = 1_000_000
    risk_per_trade_pct: float = 1.0

    # Safety
    enable_live_trading: bool = False

    # Paper trading
    paper_data_source: PaperDataSource = PaperDataSource.MOCK
    paper_session_start: time = time(9, 15)
    paper_session_end: time = time(15, 30)
    paper_clock_interval_sec: float = 1.0

    # Costs
    slippage_pct: float = 0.05
    brokerage_pct: float = 0.01

    # Journaling
    journal_dir: str = "journals"

    # Runtime operations

    broker_retry_attempts: int = 2

    broker_retry_delay_sec: float = 2.0

    historical_source_policy: HistoricalSourcePolicy = (
        HistoricalSourcePolicy.LOCAL_FIRST
    )

    historical_database_path: str = "data/historical.sqlite3"

    historical_request_delay_sec: float = 0.5

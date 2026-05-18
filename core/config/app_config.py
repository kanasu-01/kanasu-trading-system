from dataclasses import dataclass
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

    # Costs
    slippage_pct: float = 0.05
    brokerage_pct: float = 0.01

    # Journaling
    journal_dir: str = "journals"

    # Runtime operations

    broker_retry_attempts: int = 2

    broker_retry_delay_sec: float = 2.0

    historical_request_delay_sec: float = 0.5

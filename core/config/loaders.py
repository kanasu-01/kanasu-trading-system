import os
from core.config.app_config import AppConfig
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
        slippage_pct=float(os.getenv("SLIPPAGE_PCT", 0.05)),
        brokerage_pct=float(os.getenv("BROKERAGE_PCT", 0.01)),
        journal_dir=os.getenv("JOURNAL_DIR", "journals"),
    )

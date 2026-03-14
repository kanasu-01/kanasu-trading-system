from datetime import datetime

from core.app.session_manager import SessionManager
from core.broker.angelone_config import AngelOneConfig
from core.utils.historical_to_csv import export_historical_to_csv


# -------------------------------------------------
# BROKER SESSION
# -------------------------------------------------

config = AngelOneConfig.load_from_env()

session = SessionManager(
    broker_name="ANGELONE",
    config=config,
    paper_mode=True,
    enable_historical=True,
)

broker = session.get_broker()

# -------------------------------------------------
# EXPORT
# -------------------------------------------------

export_historical_to_csv(
    broker=broker,
    symbol="RELIANCE",
    timeframe="15m",
    start=datetime(2020, 1, 1, 9, 15),
    end=datetime(2025, 1, 1, 15, 30),
    output_path="data/nse/RELIANCE_15m.csv",
)

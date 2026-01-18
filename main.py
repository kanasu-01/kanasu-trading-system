# main.py (root)

from enum import Enum
from datetime import datetime

from core.broker.angelone import AngelOneBroker
from core.broker.angelone_config import AngelOneConfig
from core.market_data.historical_feed import HistoricalFeed
from core.strategies.pivotboss_swing_strategy import PivotBossSwingStrategy
from core.backtest.backtest_engine import BacktestEngine
from core.backtest.bar_replay import BarByBarReplay
from core.backtest.simple_visualization import SimpleChartVisualizer
from core.backtest.exporters.csv_exporter import CSVExporter
from core.backtest.exporters.bar_record_adapter import bar_records_to_dicts



from dotenv import load_dotenv
load_dotenv()



class RunMode(Enum):
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


def main():
    # -------- MODE --------
    MODE = RunMode.BACKTEST  # change later

    # -------- CONFIG --------
    config = AngelOneConfig.load_from_env()

    # -------- BROKER --------
    broker = AngelOneBroker(
        config=config,
        paper_mode=(MODE != RunMode.LIVE),
        enable_historical_api=(MODE == RunMode.BACKTEST),
    )
    broker.login()

    # -------- STRATEGY --------
    strategy = PivotBossSwingStrategy()

    # -------- BACKTEST FLOW --------
    if MODE == RunMode.BACKTEST:
        run_backtest(broker, strategy)


def run_backtest(broker, strategy):
    feed = HistoricalFeed(broker)

    candles = feed.load(
        symbol="RELIANCE",
        timeframe="1d",
        start=datetime(2024, 10, 2),
        end=datetime(2026, 1, 1),
    )

    engine = BacktestEngine(strategy)
    trades = engine.run(candles)

    print("\n=== TRADES ===")
    for t in trades:
        print(t)

    replay = BarByBarReplay(strategy)
    replay.run(candles)

    CSVExporter.export(
        records=bar_records_to_dicts(engine.bar_recorder.records),
        filepath="outputs/backtests/RELIANCE_15m_bars.csv",
    )
    # Visualization
    if trades:
        print("\n=== NO TRADES, PLOTTING PRICE ONLY CHARTS ===")
    SimpleChartVisualizer.plot_price_with_signals(
        candles = candles,
        trades = trades
    )

if __name__ == "__main__":
    main()

# main.py (root)

from enum import Enum
from datetime import datetime
from dataclasses import asdict

from core.broker.angelone import AngelOneBroker
from core.broker.angelone_config import AngelOneConfig
from core.market_data.historical_feed import HistoricalFeed
from core.strategies.pivotboss_swing_strategy import PivotBossSwingStrategy
from core.strategies.sma_crossover_strategy import SMACrossOverStrategy
from core.backtest.backtest_engine import BacktestEngine
from core.backtest.bar_replay import BarByBarReplay
from core.backtest.simple_visualization import SimpleChartVisualizer
from core.backtest.exporters.csv_exporter import CSVExporter
from core.backtest.exporters.json_exporter import JSONExporter
from core.backtest.exporters.bar_record_adapter import bar_records_to_dicts
from core.entities.candle import Candle



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
    #strategy = PivotBossSwingStrategy()
    strategy = SMACrossOverStrategy(
        params={
            "fast_period": 100,
            "slow_period": 200,
        }
        
    )

    # -------- BACKTEST FLOW --------
    if MODE == RunMode.BACKTEST:
        run_backtest(broker, strategy)


def run_backtest(broker, strategy):
    feed = HistoricalFeed(broker)

    candle_stream = feed.stream(
        symbol="RELIANCE",  # RELIANCE
        timeframe="15m",
        start=datetime(2020, 4, 1),
        end=datetime(2020, 12, 1),
    )

    engine = BacktestEngine(strategy)
    trades = engine.run_stream(candle_stream)

    print("\n=== TRADES ===")
    for t in trades:
        print(t)

    replay = BarByBarReplay(strategy)
    replay.run_from_records(engine.bar_recorder.records)

    CSVExporter.export(
        records=bar_records_to_dicts(engine.bar_recorder.records),
        filepath="outputs/backtests/RELIANCE_15m_bars.csv",
    )
    
    JSONExporter.export(
        records=[asdict(r) for r in engine.bar_recorder.records],
        filepath="frontend/public/replay/RELIANCE_15m_bars.json",
    )
    # Visualization
    
    # Reconstruct candles from recorded bars (single source of truth)
    candles = [
        Candle(
            timestamp=r.timestamp,
            open=r.open,
            high=r.high,
            low=r.low,
            close=r.close,
            volume=r.volume,
        )
        for r in engine.bar_recorder.records
    ]

    if trades:
        print("\n=== NO TRADES, PLOTTING PRICE ONLY CHARTS ===")
    SimpleChartVisualizer.plot_price_with_signals(
        candles = candles,
        trades = trades
    )

if __name__ == "__main__":
    main()

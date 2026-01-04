from core.strategies.pivotboss_swing_strategy import PivotBossSwingStrategy
from core.backtest.backtest_engine import BacktestEngine
from core.backtest.bar_replay import BarByBarReplay
from core.backtest.simple_visualization import SimpleChartVisualizer
from core.data_loaders.csv_candle_loader import load_candles_from_csv

# -------------------------------------------------
# LOAD HISTORICAL DATA (CSV)
# -------------------------------------------------

CSV_PATH = "data/nse/RELIANCE_15m.csv"

candles = load_candles_from_csv(CSV_PATH)

print(f"Loaded {len(candles)} candles")
print("First candle:", candles[0])

# -------------------------------------------------
# STRATEGY CONFIGURATION
# -------------------------------------------------

strategy = PivotBossSwingStrategy(
    params={
        "min_acc_score": 65,
        "rejection_close_pct": 0.20,
        "rejection_volume_multiplier": 1.2,
        "absorption_lookback": 4,
        "markup_lookback": 20,
        "markup_volume_multiplier": 1.3,
        "distribution_exit_threshold": 10
    }
)

# -------------------------------------------------
# BACKTEST RUN
# -------------------------------------------------

engine = BacktestEngine(strategy)
trades = engine.run(candles)

print("\nBACKTEST TRADES:")
for t in trades:
    print(t)

# -------------------------------------------------
# BAR-BY-BAR REPLAY (DEBUG MODE)
# -------------------------------------------------

replay = BarByBarReplay(strategy)
replay.run(candles)

# -------------------------------------------------
# SIMPLE VISUALIZATION
# -------------------------------------------------

SimpleChartVisualizer.plot_price_with_signals(
    candles=candles,
    trades=trades
)

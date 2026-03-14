from core.data_loaders.csv_candle_loader import load_candles_from_csv
from core.strategies.sma_crossover_strategy import SMACrossOverStrategy

from core.walk_forward.window_generator import WalkForwardWindowGenerator
from core.walk_forward.optimizer import GridSearchOptimizer
from core.walk_forward.metrics import WalkForwardMetrics
from core.walk_forward.runner import WalkForwardRunner


# ==========================================================
# LOAD HISTORICAL DATA
# ==========================================================

CSV_PATH = "data/nse/RELIANCE_15m.csv"

candles = load_candles_from_csv(CSV_PATH)
print(f"Loaded {len(candles)} candles")


# ==========================================================
# WALK-FORWARD CONFIG
# ==========================================================

window_generator = WalkForwardWindowGenerator(
    in_sample_bars=300,
    out_sample_bars=150,
    step_bars=150,
    mode="rolling",
)

optimizer = GridSearchOptimizer()
metrics = WalkForwardMetrics()

runner = WalkForwardRunner(
    window_generator=window_generator,
    optimizer=optimizer,
    metrics=metrics,
)


# ==========================================================
# PARAMETER SPACE (SMA)
# ==========================================================

param_space = [
    {"fast_period": 10, "slow_period": 30},
    {"fast_period": 10, "slow_period": 50},
    {"fast_period": 20, "slow_period": 50},
    {"fast_period": 20, "slow_period": 100},
    {"fast_period": 30, "slow_period": 100},
]


# ==========================================================
# RUN WALK-FORWARD ANALYSIS
# ==========================================================

wf_result = runner.run(
    strategy_cls=SMACrossOverStrategy,
    param_space=param_space,
    candles=candles,
)


# ==========================================================
# RESULTS
# ==========================================================

print("\n=== WALK-FORWARD RESULT (SMA) ===")
print("VERDICT:", wf_result.verdict)

print("\n--- Aggregated Metrics ---")
for k, v in wf_result.aggregated_metrics.items():
    print(f"{k}: {v}")

print("\n--- Per Window Summary ---")
for w in wf_result.windows:
    print(
        f"Window {w.window_index:02d} | "
        f"Trades={w.trade_count} | "
        f"Expectancy={w.test_metrics.get('expectancy_pct')} | "
        f"DD={w.test_metrics.get('max_drawdown_pct')} | "
        f"Params={w.best_params}"
    )

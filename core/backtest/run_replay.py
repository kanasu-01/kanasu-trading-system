import matplotlib.pyplot as plt

from core.backtest.replay.replay_controller import ReplayController
from core.backtest.simple_visualization import SimpleChartVisualizer
from core.backtest.backtest_engine import BacktestEngine
from core.strategies.pivotboss_swing_strategy import PivotBossSwingStrategy
from core.data_loaders.csv_candle_loader import load_candles_from_csv


# -------------------------------------------------
# LOAD DATA
# -------------------------------------------------

candles = load_candles_from_csv("data/nse/RELIANCE_15m.csv")


# -------------------------------------------------
# RUN BACKTEST ONCE (OFFLINE)
# -------------------------------------------------

strategy = PivotBossSwingStrategy()
engine = BacktestEngine(strategy)

engine.run(candles)

records = engine.bar_recorder.records


# -------------------------------------------------
# REPLAY (VISUAL)
# -------------------------------------------------

plt.ion()  # interactive plotting


def on_replay_step(record, index):
    SimpleChartVisualizer.plot_replay_step(
        records=records,
        upto_index=index,
    )


controller = ReplayController(
    records=records,
    on_step=on_replay_step,
)

# ---- Controls ----
controller.play(delay_sec=0.3)
# controller.pause()
# controller.step()

plt.ioff()
plt.show()

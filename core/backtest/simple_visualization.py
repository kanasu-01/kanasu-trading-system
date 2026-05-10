import matplotlib.pyplot as plt
from typing import List

from core.entities.candle import Candle
from core.backtest.bar_record import BarRecord
from core.entities.trade import Trade
import matplotlib.dates as mdates


class SimpleChartVisualizer:
    """
    Simple matplotlib-based visualization for backtest validation.
    """

    @staticmethod
    def plot_price_with_signals(
        candles: List[Candle],
        trades: List[Trade],
        strategy_name: str,
    ) -> None:

        times = [c.timestamp for c in candles]
        closes = [c.close for c in candles]

        plt.figure(figsize=(14, 6))
        plt.plot(times, closes, label="Close Price", linewidth=1.5)

        # Plot BUY and SELL signals
        for trade in trades:
            plt.scatter(
                trade.entry_time,
                trade.entry_price,
                color="green",
                marker="^",
                s=100,
                label="BUY"
            )

            plt.scatter(
                trade.exit_time,
                trade.exit_price,
                color="red",
                marker="v",
                s=100,
                label="SELL"
            )

        plt.title(f"{strategy_name} — Simple Backtest Visualization")
        plt.xlabel("Time")
        plt.ylabel("Price")

        # Avoid duplicate legend entries
        handles, labels = plt.gca().get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        plt.legend(by_label.values(), by_label.keys())

        plt.grid(True)
        plt.show()
        
        # ---------------- NEW METHOD (REPLAY MODE) ----------------
    @staticmethod
    def plot_replay_step(
        records: List[BarRecord],
        upto_index: int,
    ) -> None:
        """
        Plot chart state up to a given replay index.
        """

        # Clear previous frame
        plt.clf()

        visible = records[: upto_index + 1]

        times = [r.timestamp for r in visible]
        closes = [r.close for r in visible]

        plt.plot(times, closes, label="Close Price", linewidth=1.5)

        # Plot signals from BarRecords
        for r in visible:
            if r.signal == "BUY":
                plt.scatter(
                    r.timestamp,
                    r.close,
                    color="green",
                    marker="^",
                    s=80,
                )
            elif r.signal == "SELL":
                plt.scatter(
                    r.timestamp,
                    r.close,
                    color="red",
                    marker="v",
                    s=80,
                )

        plt.title(
            f"Replay Mode | Bars: {upto_index + 1} / {len(records)}"
        )
        plt.xlabel("Time")
        plt.ylabel("Price")
        plt.grid(True)

        plt.pause(0.001)  # REQUIRED for live replay

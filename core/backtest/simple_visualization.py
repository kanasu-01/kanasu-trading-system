import matplotlib.pyplot as plt
from typing import List, Dict

from core.entities.candle import Candle


class SimpleChartVisualizer:
    """
    Simple matplotlib-based visualization for backtest validation.
    """

    @staticmethod
    def plot_price_with_signals(
        candles: List[Candle],
        trades: List[Dict]
    ) -> None:

        times = [c.timestamp for c in candles]
        closes = [c.close for c in candles]

        plt.figure(figsize=(14, 6))
        plt.plot(times, closes, label="Close Price", linewidth=1.5)

        # Plot BUY and SELL signals
        for trade in trades:
            plt.scatter(
                trade["entry_time"],
                trade["entry_price"],
                color="green",
                marker="^",
                s=100,
                label="BUY"
            )

            plt.scatter(
                trade["exit_time"],
                trade["exit_price"],
                color="red",
                marker="v",
                s=100,
                label="SELL"
            )

        plt.title("PivotBoss Strategy — Simple Backtest Visualization")
        plt.xlabel("Time")
        plt.ylabel("Price")

        # Avoid duplicate legend entries
        handles, labels = plt.gca().get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        plt.legend(by_label.values(), by_label.keys())

        plt.grid(True)
        plt.show()

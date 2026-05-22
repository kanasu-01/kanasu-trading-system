import matplotlib.pyplot as plt
from typing import List, Tuple
from datetime import datetime
import numpy as np


class EquityVisualizer:
    """
    Visualizes stitched walk-forward equity curves.
    """

    @staticmethod
    def plot(
        curve: List[Tuple[datetime, float]],
        title: str = "Walk-Forward Equity Curve",
    ) -> None:

        if not curve:
            print("No stitched equity curve to visualize")
            return

        timestamps = np.array([point[0] for point in curve])

        equity_values = np.array([point[1] for point in curve])

        plt.figure(figsize=(14, 6))

        plt.plot_date(
            timestamps,
            equity_values,
            linestyle="-",
            marker=None,
        )

        plt.title(title)

        plt.xlabel("Time")

        plt.ylabel("Equity")

        plt.grid(True)

        plt.tight_layout()

        plt.show()

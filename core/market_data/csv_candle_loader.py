import csv
from datetime import datetime
from pathlib import Path

from core.entities.candle import Candle


def load_candles_from_csv(
    filepath: str,
) -> list[Candle]:
    """
    Load candles from exported CSV format.
    """

    candles: list[Candle] = []

    path = Path(filepath)

    with open(path, "r", encoding="utf-8") as f:

        reader = csv.DictReader(f)

        for row in reader:

            candles.append(
                Candle(
                    timestamp=datetime.fromisoformat(row["timestamp"]),
                    open=float(row["open"]),
                    high=float(row["high"]),
                    low=float(row["low"]),
                    close=float(row["close"]),
                    volume=float(row["volume"]),
                )
            )

    return candles

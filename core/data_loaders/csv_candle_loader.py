import csv
from datetime import datetime
from typing import List

from core.entities.candle import Candle


def load_candles_from_csv(file_path: str) -> List[Candle]:
    """
    Load OHLCV candles from a CSV file.

    Expected CSV format:
    timestamp,open,high,low,close,volume
    2023-01-02 09:15:00,2570.0,2582.5,2568.0,2579.8,182345
    """

    candles: List[Candle] = []

    with open(file_path, "r", newline="") as f:
        reader = csv.DictReader(f)

        for row in reader:
            candle = Candle(
                timestamp=datetime.strptime(row["timestamp"], "%Y-%m-%d %H:%M:%S"),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            candles.append(candle)

    return candles

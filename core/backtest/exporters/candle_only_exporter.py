# core/backtest/exporters/candle_only_exporter.py

import csv
from pathlib import Path
from typing import List, Dict


def export_candles_only(
    records: List[Dict],
    filepath: str,
) -> None:
    """
    Export ONLY candle fields from bar / record dictionaries.

    Expected keys in record:
    timestamp, open, high, low, close, volume
    """

    candle_fields = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
    ]

    path = Path(filepath)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=candle_fields)
        writer.writeheader()

        for r in records:
            writer.writerow({k: r.get(k) for k in candle_fields})

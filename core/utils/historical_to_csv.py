# core/utils/historical_to_csv.py

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterable

from core.entities.candle import Candle
from core.market_data.historical_feed import HistoricalFeed
from core.broker.base_broker import BaseBroker


def export_historical_to_csv(
    broker: BaseBroker,
    *,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    output_path: str,
) -> None:
    """
    Download historical candles via broker and save to CSV.

    CSV format (COMPATIBLE with csv_candle_loader):
    timestamp,open,high,low,close,volume
    """

    feed = HistoricalFeed(broker)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[HIST→CSV] Exporting {symbol} {timeframe}")
    print(f"[HIST→CSV] From {start} → {end}")
    print(f"[HIST→CSV] Output: {path}")

    candle_stream: Iterable[Candle] = feed.stream(
        symbol=symbol,
        timeframe=timeframe,
        start=start,
        end=end,
    )

    written = 0

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["timestamp", "open", "high", "low", "close", "volume"]
        )

        for candle in candle_stream:
            writer.writerow([
                candle.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume,
            ])
            written += 1

            if written % 1000 == 0:
                print(f"[HIST→CSV] Written {written} candles...")

    print(f"[HIST→CSV] DONE. Total candles written: {written}")

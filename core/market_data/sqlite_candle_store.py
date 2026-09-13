from contextlib import closing
from datetime import datetime
import json
import sqlite3

from core.entities.candle import Candle
from core.runtime.dataset_context import DatasetContext


_CREATE_CANDLES_TABLE = """
CREATE TABLE IF NOT EXISTS candles (
    dataset_key TEXT NOT NULL,
    timestamp_iso TEXT NOT NULL,
    open_price REAL NOT NULL,
    high_price REAL NOT NULL,
    low_price REAL NOT NULL,
    close_price REAL NOT NULL,
    volume REAL NOT NULL,
    PRIMARY KEY (dataset_key, timestamp_iso)
)
"""


class SQLiteCandleStore:
    def __init__(self, database_path):
        self.database_path = database_path

        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(_CREATE_CANDLES_TABLE)
            connection.commit()

    def save(
        self,
        context: DatasetContext,
        candles: list[Candle],
    ) -> None:
        dataset_key = self._dataset_key(context)

        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                for candle in candles:
                    timestamp_iso = self._timestamp_iso(candle.timestamp)
                    values = (
                        candle.open,
                        candle.high,
                        candle.low,
                        candle.close,
                        candle.volume,
                    )
                    stored_values = connection.execute(
                        """
                        SELECT
                            open_price,
                            high_price,
                            low_price,
                            close_price,
                            volume
                        FROM candles
                        WHERE dataset_key = ? AND timestamp_iso = ?
                        """,
                        (dataset_key, timestamp_iso),
                    ).fetchone()

                    if stored_values is not None:
                        if stored_values != values:
                            raise ValueError(
                                "conflicting candle for dataset and timestamp"
                            )
                        continue

                    connection.execute(
                        """
                        INSERT INTO candles (
                            dataset_key,
                            timestamp_iso,
                            open_price,
                            high_price,
                            low_price,
                            close_price,
                            volume
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (dataset_key, timestamp_iso, *values),
                    )

    def load(
        self,
        context: DatasetContext,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        dataset_key = self._dataset_key(context)

        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                """
                SELECT
                    timestamp_iso,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume
                FROM candles
                WHERE dataset_key = ?
                  AND timestamp_iso >= ?
                  AND timestamp_iso <= ?
                ORDER BY timestamp_iso ASC
                """,
                (
                    dataset_key,
                    self._timestamp_iso(start),
                    self._timestamp_iso(end),
                ),
            ).fetchall()

        return [
            Candle(
                timestamp=datetime.fromisoformat(row[0]),
                open=row[1],
                high=row[2],
                low=row[3],
                close=row[4],
                volume=row[5],
            )
            for row in rows
        ]

    @staticmethod
    def _dataset_key(context: DatasetContext) -> str:
        return json.dumps(
            {
                "symbol": context.symbol,
                "timeframe": context.timeframe,
                "timezone": context.timezone,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )

    @staticmethod
    def _timestamp_iso(timestamp: datetime) -> str:
        return timestamp.isoformat(timespec="microseconds")

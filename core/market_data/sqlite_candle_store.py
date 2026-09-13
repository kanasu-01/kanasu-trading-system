from contextlib import closing
from datetime import datetime
import json
import sqlite3

from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
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

_CREATE_COVERAGE_TABLE = """
CREATE TABLE IF NOT EXISTS retrieval_coverage (
    dataset_key TEXT NOT NULL,
    start_iso TEXT NOT NULL,
    end_iso TEXT NOT NULL,
    PRIMARY KEY (dataset_key, start_iso, end_iso)
)
"""


def _is_timezone_aware(timestamp: datetime) -> bool:
    return timestamp.utcoffset() is not None


class SQLiteCandleStore:
    def __init__(self, database_path):
        self.database_path = database_path

        with closing(sqlite3.connect(self.database_path)) as connection:
            connection.execute(_CREATE_CANDLES_TABLE)
            connection.execute(_CREATE_COVERAGE_TABLE)
            connection.commit()

    def save(
        self,
        context: DatasetContext,
        candles: list[Candle],
    ) -> None:
        dataset_key = self._dataset_key(context)

        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                self._validate_write_awareness(
                    connection,
                    dataset_key,
                    candles,
                    [],
                )
                self._save_candles(connection, dataset_key, candles)

    def save_retrieval(
        self,
        context: DatasetContext,
        candles: list[Candle],
        coverage: list[TimeRange],
    ) -> None:
        dataset_key = self._dataset_key(context)

        with closing(sqlite3.connect(self.database_path)) as connection:
            with connection:
                self._validate_write_awareness(
                    connection,
                    dataset_key,
                    candles,
                    coverage,
                )
                self._save_candles(connection, dataset_key, candles)

                for interval in coverage:
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO retrieval_coverage (
                            dataset_key,
                            start_iso,
                            end_iso
                        ) VALUES (?, ?, ?)
                        """,
                        (
                            dataset_key,
                            self._timestamp_iso(interval.start),
                            self._timestamp_iso(interval.end),
                        ),
                    )

    def load(
        self,
        context: DatasetContext,
        start: datetime,
        end: datetime,
    ) -> list[Candle]:
        dataset_key = self._dataset_key(context)

        if _is_timezone_aware(start) != _is_timezone_aware(end):
            raise ValueError(
                "candle load range timezone awareness must match"
            )

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
                """,
                (dataset_key,),
            ).fetchall()

        range_is_aware = _is_timezone_aware(start)
        candles: list[Candle] = []

        for row in rows:
            timestamp = datetime.fromisoformat(row[0])
            if _is_timezone_aware(timestamp) != range_is_aware:
                raise ValueError(
                    "stored candle and load range timezone awareness "
                    "must match"
                )

            if start <= timestamp <= end:
                candles.append(
                    Candle(
                        timestamp=timestamp,
                        open=row[1],
                        high=row[2],
                        low=row[3],
                        close=row[4],
                        volume=row[5],
                    )
                )

        candles.sort(key=lambda candle: candle.timestamp)
        return candles

    def load_coverage(
        self,
        context: DatasetContext,
    ) -> list[TimeRange]:
        dataset_key = self._dataset_key(context)

        with closing(sqlite3.connect(self.database_path)) as connection:
            rows = connection.execute(
                """
                SELECT start_iso, end_iso
                FROM retrieval_coverage
                WHERE dataset_key = ?
                """,
                (dataset_key,),
            ).fetchall()

        coverage = [
            TimeRange(
                start=datetime.fromisoformat(row[0]),
                end=datetime.fromisoformat(row[1]),
            )
            for row in rows
        ]

        if coverage:
            first_is_aware = _is_timezone_aware(coverage[0].start)
            if any(
                _is_timezone_aware(interval.start) != first_is_aware
                for interval in coverage[1:]
            ):
                raise ValueError(
                    "stored coverage timezone awareness must match"
                )

        coverage.sort(key=lambda interval: interval.start)
        return coverage

    @classmethod
    def _validate_write_awareness(
        cls,
        connection: sqlite3.Connection,
        dataset_key: str,
        candles: list[Candle],
        coverage: list[TimeRange],
    ) -> None:
        stored_timestamp_rows = connection.execute(
            """
            SELECT timestamp_iso
            FROM candles
            WHERE dataset_key = ?
            """,
            (dataset_key,),
        ).fetchall()
        stored_coverage_rows = connection.execute(
            """
            SELECT start_iso, end_iso
            FROM retrieval_coverage
            WHERE dataset_key = ?
            """,
            (dataset_key,),
        ).fetchall()
        stored_timestamps = [
            datetime.fromisoformat(row[0])
            for row in stored_timestamp_rows
        ]
        stored_timestamps.extend(
            datetime.fromisoformat(value)
            for row in stored_coverage_rows
            for value in row
        )
        incoming_timestamps = [
            candle.timestamp
            for candle in candles
        ]
        incoming_timestamps.extend(
            timestamp
            for interval in coverage
            for timestamp in (interval.start, interval.end)
        )

        stored_awareness = cls._single_awareness(
            stored_timestamps,
            "persisted dataset",
        )
        incoming_awareness = cls._single_awareness(
            incoming_timestamps,
            "incoming",
        )

        if (
            stored_awareness is not None
            and incoming_awareness is not None
            and stored_awareness != incoming_awareness
        ):
            raise ValueError(
                "incoming timestamp timezone awareness must match "
                "the persisted dataset"
            )

    @staticmethod
    def _single_awareness(
        timestamps: list[datetime],
        source: str,
    ) -> bool | None:
        if not timestamps:
            return None

        awareness = _is_timezone_aware(timestamps[0])
        if any(
            _is_timezone_aware(timestamp) != awareness
            for timestamp in timestamps[1:]
        ):
            raise ValueError(
                f"{source} timestamp timezone awareness must be consistent"
            )
        return awareness

    @classmethod
    def _save_candles(
        cls,
        connection: sqlite3.Connection,
        dataset_key: str,
        candles: list[Candle],
    ) -> None:
        stored_by_timestamp = {
            datetime.fromisoformat(row[0]): row[1:]
            for row in connection.execute(
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
                """,
                (dataset_key,),
            ).fetchall()
        }

        for candle in candles:
            timestamp_iso = cls._timestamp_iso(candle.timestamp)
            values = (
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume,
            )
            stored_values = stored_by_timestamp.get(candle.timestamp)

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
            stored_by_timestamp[candle.timestamp] = values

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

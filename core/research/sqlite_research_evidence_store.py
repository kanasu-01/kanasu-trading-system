"""Dedicated SQLite persistence for immutable research evidence records."""

from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3

from core.market_data.historical_coverage import TimeRange
from core.research.models.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStatus,
)
from core.runtime.dataset_context import DatasetContext


class SQLiteResearchEvidenceStore:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _initialize_schema(self) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS research_evidence (
                        evidence_id TEXT PRIMARY KEY,
                        created_at TEXT NOT NULL,
                        status TEXT NOT NULL,
                        symbol TEXT NOT NULL,
                        timeframe TEXT,
                        timezone TEXT,
                        request_start TEXT NOT NULL,
                        request_end TEXT NOT NULL,
                        dataset_fingerprint TEXT,
                        configuration_fingerprint TEXT,
                        result_fingerprint TEXT,
                        provenance TEXT NOT NULL,
                        repository_revision TEXT,
                        summary TEXT NOT NULL,
                        artifact_references TEXT NOT NULL
                    )
                    """
                )

    def save(self, record: ResearchEvidence) -> None:
        """Persist one record atomically; existing evidence is immutable."""

        if not isinstance(record, ResearchEvidence):
            raise TypeError("record must be ResearchEvidence")

        values = (
            record.evidence_id,
            record.created_at.isoformat(timespec="microseconds"),
            record.status.value,
            record.dataset_context.symbol,
            record.dataset_context.timeframe,
            record.dataset_context.timezone,
            record.requested_range.start.isoformat(timespec="microseconds"),
            record.requested_range.end.isoformat(timespec="microseconds"),
            record.dataset_fingerprint,
            record.configuration_fingerprint,
            record.result_fingerprint,
            self._encode_sequence(record.provenance),
            record.repository_revision,
            record.summary,
            self._encode_sequence(record.artifact_references),
        )

        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO research_evidence (
                            evidence_id,
                            created_at,
                            status,
                            symbol,
                            timeframe,
                            timezone,
                            request_start,
                            request_end,
                            dataset_fingerprint,
                            configuration_fingerprint,
                            result_fingerprint,
                            provenance,
                            repository_revision,
                            summary,
                            artifact_references
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        values,
                    )
        except sqlite3.IntegrityError as error:
            raise ValueError(
                f"research evidence already exists: {record.evidence_id}"
            ) from error

    def load(self, evidence_id: str) -> ResearchEvidence | None:
        """Load an immutable evidence record by ID, or None when absent."""

        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    evidence_id,
                    created_at,
                    status,
                    symbol,
                    timeframe,
                    timezone,
                    request_start,
                    request_end,
                    dataset_fingerprint,
                    configuration_fingerprint,
                    result_fingerprint,
                    provenance,
                    repository_revision,
                    summary,
                    artifact_references
                FROM research_evidence
                WHERE evidence_id = ?
                """,
                (evidence_id,),
            ).fetchone()

        if row is None:
            return None

        return ResearchEvidence(
            evidence_id=row[0],
            created_at=datetime.fromisoformat(row[1]),
            status=ResearchEvidenceStatus(row[2]),
            dataset_context=DatasetContext(
                symbol=row[3],
                timeframe=row[4],
                timezone=row[5],
            ),
            requested_range=TimeRange(
                start=datetime.fromisoformat(row[6]),
                end=datetime.fromisoformat(row[7]),
            ),
            dataset_fingerprint=row[8],
            configuration_fingerprint=row[9],
            result_fingerprint=row[10],
            provenance=tuple(
                (item[0], item[1])
                for item in self._decode_sequence(row[11])
            ),
            repository_revision=row[12],
            summary=row[13],
            artifact_references=tuple(self._decode_sequence(row[14])),
        )

    @staticmethod
    def _encode_sequence(values) -> str:
        return json.dumps(
            values,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    @staticmethod
    def _decode_sequence(value: str):
        return json.loads(value)

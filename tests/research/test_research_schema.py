from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.research.models.research_evidence import ResearchEvidenceStatus
from core.research.research_schema import RESEARCH_SCHEMA_VERSION
from core.research.sqlite_research_evidence_store import (
    SQLiteResearchEvidenceStore,
)
from core.runtime.dataset_context import DatasetContext


INDIA = timezone(timedelta(hours=5, minutes=30))


LEGACY_RESEARCH_EVIDENCE_TABLE = """
CREATE TABLE research_evidence (
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


def _user_version(path) -> int:
    with sqlite3.connect(path) as connection:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])


def _table_names(path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }


def test_new_research_database_initializes_explicit_schema_version(tmp_path):
    path = tmp_path / "research.sqlite3"

    SQLiteResearchEvidenceStore(path)

    assert _user_version(path) == RESEARCH_SCHEMA_VERSION
    assert {
        "research_evidence",
        "research_artifacts",
        "experiment_specs",
        "run_attempts",
    }.issubset(_table_names(path))


def test_legacy_evidence_database_upgrades_without_rewriting_evidence(tmp_path):
    path = tmp_path / "legacy-research.sqlite3"

    created_at = datetime(
        2026,
        3,
        4,
        11,
        22,
        33,
        456789,
        tzinfo=INDIA,
    )
    request_end = created_at + timedelta(hours=1)

    values = (
        "legacy-evidence-001",
        created_at.isoformat(timespec="microseconds"),
        ResearchEvidenceStatus.ACCEPTED.value,
        "RELIANCE",
        "15m",
        "Asia/Kolkata",
        created_at.isoformat(timespec="microseconds"),
        request_end.isoformat(timespec="microseconds"),
        "sha256:" + "a" * 64,
        "sha256:" + "b" * 64,
        "sha256:" + "c" * 64,
        json.dumps(
            [["provider", "legacy-fixture"]],
            separators=(",", ":"),
        ),
        "legacy-revision",
        "Legacy evidence row",
        json.dumps(
            ["legacy/trades.json"],
            separators=(",", ":"),
        ),
    )

    with sqlite3.connect(path) as connection:
        connection.execute(LEGACY_RESEARCH_EVIDENCE_TABLE)
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
        before = connection.execute(
            "SELECT * FROM research_evidence WHERE evidence_id = ?",
            ("legacy-evidence-001",),
        ).fetchone()
        assert int(
            connection.execute("PRAGMA user_version").fetchone()[0]
        ) == 0

    store = SQLiteResearchEvidenceStore(path)

    with sqlite3.connect(path) as connection:
        after = connection.execute(
            "SELECT * FROM research_evidence WHERE evidence_id = ?",
            ("legacy-evidence-001",),
        ).fetchone()

    assert _user_version(path) == RESEARCH_SCHEMA_VERSION
    assert {
        "research_evidence",
        "research_artifacts",
        "experiment_specs",
        "run_attempts",
    }.issubset(_table_names(path))
    assert after == before

    loaded = store.load("legacy-evidence-001")

    assert loaded is not None
    assert loaded.evidence_id == "legacy-evidence-001"
    assert loaded.created_at == created_at
    assert loaded.status is ResearchEvidenceStatus.ACCEPTED
    assert loaded.dataset_context.symbol == "RELIANCE"
    assert loaded.dataset_context.timeframe == "15m"
    assert loaded.dataset_context.timezone == "Asia/Kolkata"
    assert loaded.requested_range.start == created_at
    assert loaded.requested_range.end == request_end
    assert loaded.repository_revision == "legacy-revision"
    assert loaded.summary == "Legacy evidence row"
    assert loaded.artifact_references == ("legacy/trades.json",)


def test_unknown_newer_research_schema_fails_closed_without_mutation(tmp_path):
    path = tmp_path / "future-research.sqlite3"
    future_version = RESEARCH_SCHEMA_VERSION + 1

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE future_catalog_marker (
                marker TEXT PRIMARY KEY
            )
            """
        )
        connection.execute(
            "INSERT INTO future_catalog_marker (marker) VALUES (?)",
            ("preserve-me",),
        )
        connection.execute(
            f"PRAGMA user_version = {future_version}"
        )

    with pytest.raises(
        RuntimeError,
        match="newer than supported version",
    ):
        SQLiteResearchEvidenceStore(path)

    assert _user_version(path) == future_version
    assert "research_evidence" not in _table_names(path)

    with sqlite3.connect(path) as connection:
        marker = connection.execute(
            "SELECT marker FROM future_catalog_marker"
        ).fetchone()

    assert marker == ("preserve-me",)

def test_incompatible_legacy_evidence_schema_fails_closed_without_version_bump(
    tmp_path,
):
    path = tmp_path / "incompatible-legacy.sqlite3"

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE research_evidence (
                evidence_id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO research_evidence (
                evidence_id,
                created_at
            ) VALUES (?, ?)
            """,
            ("preserve-me", "2026-03-04T11:22:33+05:30"),
        )
        before_schema = connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'research_evidence'
            """
        ).fetchone()[0]
        before_row = connection.execute(
            "SELECT * FROM research_evidence"
        ).fetchone()

    with pytest.raises(
        RuntimeError,
        match="incompatible research_evidence table",
    ):
        SQLiteResearchEvidenceStore(path)

    assert _user_version(path) == 0

    with sqlite3.connect(path) as connection:
        after_schema = connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'research_evidence'
            """
        ).fetchone()[0]
        after_row = connection.execute(
            "SELECT * FROM research_evidence"
        ).fetchone()

    assert after_schema == before_schema
    assert after_row == before_row


def test_current_schema_version_missing_required_table_fails_closed(
    tmp_path,
):
    path = tmp_path / "corrupt-current.sqlite3"

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE preserved_marker (
                marker TEXT PRIMARY KEY
            )
            """
        )
        connection.execute(
            "INSERT INTO preserved_marker (marker) VALUES (?)",
            ("preserve-me",),
        )
        connection.execute(
            f"PRAGMA user_version = {RESEARCH_SCHEMA_VERSION}"
        )

    with pytest.raises(
        RuntimeError,
        match="missing required research_evidence table",
    ):
        SQLiteResearchEvidenceStore(path)

    assert _user_version(path) == RESEARCH_SCHEMA_VERSION
    assert "research_evidence" not in _table_names(path)

    with sqlite3.connect(path) as connection:
        marker = connection.execute(
            "SELECT marker FROM preserved_marker"
        ).fetchone()

    assert marker == ("preserve-me",)

def test_current_schema_missing_catalog_table_fails_closed(tmp_path):
    path = tmp_path / "missing-catalog-table.sqlite3"

    SQLiteResearchEvidenceStore(path)

    with sqlite3.connect(path) as connection:
        connection.execute("DROP TABLE run_attempts")

    with pytest.raises(
        RuntimeError,
        match="missing required run_attempts table",
    ):
        SQLiteResearchEvidenceStore(path)

    assert _user_version(path) == RESEARCH_SCHEMA_VERSION
    assert "run_attempts" not in _table_names(path)


def test_legacy_migration_rolls_back_when_catalog_table_is_incompatible(
    tmp_path,
):
    path = tmp_path / "bad-catalog-legacy.sqlite3"

    with sqlite3.connect(path) as connection:
        connection.execute(LEGACY_RESEARCH_EVIDENCE_TABLE)
        connection.execute(
            """
            CREATE TABLE research_artifacts (
                artifact_id TEXT PRIMARY KEY
            )
            """
        )
        connection.execute(
            """
            INSERT INTO research_artifacts (artifact_id)
            VALUES (?)
            """,
            ("preserve-me",),
        )

    with pytest.raises(
        RuntimeError,
        match="incompatible research_artifacts table",
    ):
        SQLiteResearchEvidenceStore(path)

    assert _user_version(path) == 0

    tables = _table_names(path)

    assert "research_evidence" in tables
    assert "research_artifacts" in tables
    assert "experiment_specs" not in tables
    assert "run_attempts" not in tables

    with sqlite3.connect(path) as connection:
        artifact_row = connection.execute(
            "SELECT artifact_id FROM research_artifacts"
        ).fetchone()

    assert artifact_row == ("preserve-me",)

def test_historical_database_cannot_be_adopted_as_research_database(
    tmp_path,
):
    path = tmp_path / "historical.sqlite3"
    context = DatasetContext(
        "RELIANCE",
        "15m",
        "Asia/Kolkata",
    )
    start = datetime(
        2026,
        9,
        25,
        9,
        15,
        tzinfo=INDIA,
    )
    end = start + timedelta(minutes=15)
    candle = Candle(
        timestamp=start,
        open=100.0,
        high=103.0,
        low=99.0,
        close=102.0,
        volume=500.0,
    )

    historical = SQLiteCandleStore(path)
    historical.save_retrieval(
        context,
        [candle],
        [TimeRange(start, end)],
    )

    before_tables = _table_names(path)

    assert "candles" in before_tables
    assert "retrieval_coverage" in before_tables
    assert "research_evidence" not in before_tables
    assert _user_version(path) == 0

    with pytest.raises(
        RuntimeError,
        match="unexpected tables in unversioned research database",
    ):
        SQLiteResearchEvidenceStore(path)

    assert _user_version(path) == 0
    assert _table_names(path) == before_tables
    assert "research_evidence" not in _table_names(path)

    assert historical.load(
        context,
        start,
        end,
    ) == [candle]


def test_catalog_ddl_failure_rolls_back_tables_created_in_same_migration(
    tmp_path,
):
    path = tmp_path / "ddl-rollback.sqlite3"

    with sqlite3.connect(path) as connection:
        connection.execute(LEGACY_RESEARCH_EVIDENCE_TABLE)
        connection.execute(
            """
            CREATE VIEW run_attempts AS
            SELECT 'blocked' AS attempt_id
            """
        )

    assert _user_version(path) == 0
    assert _table_names(path) == {"research_evidence"}

    with pytest.raises(
        RuntimeError,
        match="missing required run_attempts table",
    ):
        SQLiteResearchEvidenceStore(path)

    # research_artifacts and experiment_specs are created before the
    # conflicting run_attempts object is reached. Explicit rollback
    # must remove both of those earlier DDL changes.
    assert _user_version(path) == 0
    assert _table_names(path) == {"research_evidence"}

    with sqlite3.connect(path) as connection:
        view = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'view'
              AND name = 'run_attempts'
            """
        ).fetchone()

    assert view == ("run_attempts",)

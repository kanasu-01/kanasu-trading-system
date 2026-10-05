import sqlite3

import pytest

from core.research import research_schema
from core.research.research_schema import (
    RESEARCH_SCHEMA_VERSION,
)
from core.research.sqlite_research_evidence_store import (
    SQLiteResearchEvidenceStore,
)


V2_TABLES = {
    "research_evidence",
    "research_artifacts",
    "experiment_specs",
    "run_attempts",
    "studies",
    "study_revisions",
    "trials",
    "trial_disposition_events",
    "research_jobs",
}


V3_TABLES = V2_TABLES | {
    "research_job_reuse_dataset_lineage",
}


V4_TABLES = V3_TABLES | {
    "research_dataset_reference_identities",
}


V5_TABLES = V4_TABLES | {
    "study_revision_population_registrations",
}


def user_version(path) -> int:
    with sqlite3.connect(path) as connection:
        return int(
            connection.execute(
                "PRAGMA user_version"
            ).fetchone()[0]
        )


def table_names(path) -> set[str]:
    with sqlite3.connect(path) as connection:
        return {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                """
            )
        }


def create_v1_database(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            research_schema._CREATE_RESEARCH_EVIDENCE_TABLE
        )

        for statement in (
            research_schema._CREATE_V1_CATALOG_TABLES
        ):
            connection.execute(statement)

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
            ) VALUES (
                'evidence-v1',
                '2026-09-01T10:00:00+05:30',
                'INCOMPLETE',
                'RELIANCE',
                '15m',
                'Asia/Kolkata',
                '2026-09-01T10:00:00+05:30',
                '2026-09-01T11:00:00+05:30',
                NULL,
                NULL,
                NULL,
                '[]',
                NULL,
                'preserve-v1-row',
                '[]'
            )
            """
        )

        connection.execute("PRAGMA user_version = 1")


def test_new_database_initializes_additive_schema_v5(
    tmp_path,
):
    path = tmp_path / "research.sqlite3"

    SQLiteResearchEvidenceStore(path)

    assert RESEARCH_SCHEMA_VERSION == 5
    assert user_version(path) == 5
    assert table_names(path) == V5_TABLES


def test_v1_migration_preserves_existing_rows_and_adds_tables(
    tmp_path,
):
    path = tmp_path / "research.sqlite3"
    create_v1_database(path)

    with sqlite3.connect(path) as connection:
        before = connection.execute(
            """
            SELECT *
            FROM research_evidence
            WHERE evidence_id = 'evidence-v1'
            """
        ).fetchone()

    SQLiteResearchEvidenceStore(path)

    with sqlite3.connect(path) as connection:
        after = connection.execute(
            """
            SELECT *
            FROM research_evidence
            WHERE evidence_id = 'evidence-v1'
            """
        ).fetchone()

    assert before == after
    assert user_version(path) == 5
    assert table_names(path) == V5_TABLES




def create_v2_database(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            research_schema._CREATE_RESEARCH_EVIDENCE_TABLE
        )

        for statement in (
            research_schema._CREATE_V1_CATALOG_TABLES
        ):
            connection.execute(statement)

        for statement in (
            research_schema._CREATE_V2_TABLES
        ):
            connection.execute(statement)

        for statement in (
            research_schema._CREATE_V2_INDEXES
        ):
            connection.execute(statement)

        connection.execute(
            "PRAGMA user_version = 2"
        )


def test_v2_migration_adds_reuse_dataset_lineage_table(
    tmp_path,
):
    path = tmp_path / "research-v2.sqlite3"
    create_v2_database(path)

    assert user_version(path) == 2
    assert table_names(path) == V2_TABLES

    SQLiteResearchEvidenceStore(path)

    assert user_version(path) == 5
    assert table_names(path) == V5_TABLES

    with sqlite3.connect(path) as connection:
        columns = tuple(
            row[1]
            for row in connection.execute(
                """
                PRAGMA table_info(
                    research_job_reuse_dataset_lineage
                )
                """
            )
        )

    assert columns == (
        "job_id",
        "requested_dataset_reference_artifact_id",
        "source_dataset_reference_artifact_id",
    )


def create_v3_database(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            research_schema._CREATE_RESEARCH_EVIDENCE_TABLE
        )

        for statement in (
            research_schema._CREATE_V1_CATALOG_TABLES
        ):
            connection.execute(statement)

        for statement in (
            research_schema._CREATE_V2_TABLES
        ):
            connection.execute(statement)

        for statement in (
            research_schema._CREATE_V3_TABLES
        ):
            connection.execute(statement)

        for statement in (
            research_schema._CREATE_V2_INDEXES
        ):
            connection.execute(statement)

        connection.execute(
            "PRAGMA user_version = 3"
        )


def test_v3_migration_adds_dataset_reference_identity_table(
    tmp_path,
):
    path = tmp_path / "research-v3.sqlite3"
    create_v3_database(path)

    assert user_version(path) == 3
    assert table_names(path) == V3_TABLES

    SQLiteResearchEvidenceStore(path)

    assert user_version(path) == 5
    assert table_names(path) == V5_TABLES

    with sqlite3.connect(path) as connection:
        columns = tuple(
            row[1]
            for row in connection.execute(
                """
                PRAGMA table_info(
                    research_dataset_reference_identities
                )
                """
            )
        )

        foreign_keys = connection.execute(
            """
            PRAGMA foreign_key_list(
                research_dataset_reference_identities
            )
            """
        ).fetchall()

    assert columns == (
        "artifact_id",
        "dataset_id",
    )

    assert any(
        row[2] == "research_artifacts"
        and row[3] == "artifact_id"
        and row[4] == "artifact_id"
        for row in foreign_keys
    )


def create_v4_database(path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            research_schema._CREATE_RESEARCH_EVIDENCE_TABLE
        )

        for statements in (
            research_schema._CREATE_V1_CATALOG_TABLES,
            research_schema._CREATE_V2_TABLES,
            research_schema._CREATE_V3_TABLES,
            research_schema._CREATE_V4_TABLES,
        ):
            for statement in statements:
                connection.execute(
                    statement
                )

        for statement in (
            research_schema._CREATE_V2_INDEXES
        ):
            connection.execute(
                statement
            )

        connection.execute(
            "PRAGMA user_version = 4"
        )


def test_v4_migration_adds_population_proof_table_fail_closed(
    tmp_path,
):
    path = tmp_path / "research-v4.sqlite3"

    create_v4_database(
        path
    )

    assert user_version(path) == 4
    assert table_names(path) == V4_TABLES

    SQLiteResearchEvidenceStore(
        path
    )

    assert user_version(path) == 5
    assert table_names(path) == V5_TABLES

    with sqlite3.connect(path) as connection:
        columns = tuple(
            row[1]
            for row in connection.execute(
                """
                PRAGMA table_info(
                    study_revision_population_registrations
                )
                """
            )
        )

        count = connection.execute(
            """
            SELECT COUNT(*)
            FROM study_revision_population_registrations
            """
        ).fetchone()[0]

    assert columns == (
        "study_revision_id",
        "trial_count",
        "population_fingerprint",
    )

    # Old schema cannot prove which revisions came through the
    # authoritative population transaction. Migration therefore
    # fails closed rather than guessing historical authority.
    assert count == 0


def test_v1_migration_failure_rolls_back_new_tables(
    tmp_path,
):
    path = tmp_path / "research.sqlite3"
    create_v1_database(path)

    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE studies (
                wrong_column TEXT PRIMARY KEY
            )
            """
        )

    with pytest.raises(
        RuntimeError,
        match="incompatible studies table",
    ):
        SQLiteResearchEvidenceStore(path)

    assert user_version(path) == 1

    tables = table_names(path)

    assert "studies" in tables
    assert "study_revisions" not in tables
    assert "trials" not in tables
    assert "research_jobs" not in tables
    assert "trial_disposition_events" not in tables


def test_schema_v2_has_trial_local_event_uniqueness(
    tmp_path,
):
    path = tmp_path / "research.sqlite3"
    SQLiteResearchEvidenceStore(path)

    with sqlite3.connect(path) as connection:
        sql = connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'trial_disposition_events'
            """
        ).fetchone()[0]

    compact = " ".join(sql.split())

    assert (
        "UNIQUE (trial_id, sequence_number)"
        in compact
    )


def test_trial_schema_persists_membership_evidence_artifact_reference(
    tmp_path,
):
    import sqlite3

    from core.research.sqlite_research_catalog_store import (
        SQLiteResearchCatalogStore,
    )

    path = tmp_path / "research.sqlite3"
    SQLiteResearchCatalogStore(path)

    with sqlite3.connect(path) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(trials)"
            )
        }

        foreign_keys = connection.execute(
            "PRAGMA foreign_key_list(trials)"
        ).fetchall()

        create_sql = connection.execute(
            """
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'trials'
            """
        ).fetchone()[0]

    assert "membership_evidence_fingerprint" in columns
    assert "membership_evidence_artifact_id" in columns

    assert any(
        row[2] == "research_artifacts"
        and row[3] == "membership_evidence_artifact_id"
        and row[4] == "artifact_id"
        for row in foreign_keys
    )

    assert (
        "membership_evidence_artifact_id"
        in create_sql
        and "membership_evidence_fingerprint"
        in create_sql
        and "CHECK" in create_sql
    )

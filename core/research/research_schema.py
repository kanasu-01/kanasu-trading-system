"""Versioned SQLite schema ownership for durable research metadata."""

import sqlite3


RESEARCH_SCHEMA_VERSION = 4


_CREATE_RESEARCH_EVIDENCE_TABLE = """
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


_CREATE_RESEARCH_ARTIFACTS_TABLE = """
CREATE TABLE IF NOT EXISTS research_artifacts (
    artifact_id TEXT PRIMARY KEY,
    artifact_kind TEXT NOT NULL,
    schema_id TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    byte_count INTEGER NOT NULL CHECK (byte_count >= 0),
    created_at TEXT NOT NULL
)
"""


_CREATE_EXPERIMENT_SPECS_TABLE = """
CREATE TABLE IF NOT EXISTS experiment_specs (
    experiment_spec_id TEXT PRIMARY KEY,
    identity_schema TEXT NOT NULL,
    computation_kind TEXT NOT NULL,
    manifest_artifact_id TEXT NOT NULL,
    dataset_fingerprint TEXT NOT NULL,
    configuration_fingerprint TEXT NOT NULL,
    repository_revision TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (manifest_artifact_id)
        REFERENCES research_artifacts (artifact_id),
    UNIQUE (
        identity_schema,
        computation_kind,
        manifest_artifact_id,
        dataset_fingerprint,
        configuration_fingerprint,
        repository_revision
    )
)
"""


_CREATE_RUN_ATTEMPTS_TABLE = """
CREATE TABLE IF NOT EXISTS run_attempts (
    attempt_id TEXT PRIMARY KEY,
    experiment_spec_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN (
            'QUEUED',
            'RUNNING',
            'SUCCEEDED',
            'FAILED',
            'CANCELLED',
            'INTERRUPTED'
        )
    ),
    created_at TEXT NOT NULL,
    terminal_at TEXT,
    runtime_session_id TEXT,
    result_artifact_id TEXT,
    evidence_id TEXT,
    failure_classification TEXT,
    failure_message TEXT,
    FOREIGN KEY (experiment_spec_id)
        REFERENCES experiment_specs (experiment_spec_id),
    FOREIGN KEY (result_artifact_id)
        REFERENCES research_artifacts (artifact_id),
    FOREIGN KEY (evidence_id)
        REFERENCES research_evidence (evidence_id)
)
"""


_CREATE_STUDIES_TABLE = """
CREATE TABLE IF NOT EXISTS studies (
    study_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    display_title TEXT NOT NULL,
    archived INTEGER NOT NULL CHECK (archived IN (0, 1))
)
"""


_CREATE_STUDY_REVISIONS_TABLE = """
CREATE TABLE IF NOT EXISTS study_revisions (
    study_revision_id TEXT PRIMARY KEY,
    identity_schema TEXT NOT NULL,
    study_id TEXT NOT NULL,
    revision_number INTEGER NOT NULL
        CHECK (revision_number > 0),
    plan_artifact_id TEXT NOT NULL,
    repository_revision TEXT NOT NULL,
    evidence_reuse_policy TEXT NOT NULL CHECK (
        evidence_reuse_policy IN (
            'ALLOW_EXACT_ACCEPTED',
            'FORCE_NEW_EXECUTION'
        )
    ),
    registered_at TEXT NOT NULL,
    initial_batch_started_at TEXT,
    FOREIGN KEY (study_id)
        REFERENCES studies (study_id),
    FOREIGN KEY (plan_artifact_id)
        REFERENCES research_artifacts (artifact_id),
    UNIQUE (study_id, revision_number),
    UNIQUE (study_id, plan_artifact_id)
)
"""


_CREATE_TRIALS_TABLE = """
CREATE TABLE IF NOT EXISTS trials (
    trial_id TEXT PRIMARY KEY,
    identity_schema TEXT NOT NULL,
    study_revision_id TEXT NOT NULL,
    instrument_id TEXT NOT NULL,
    membership_episode_start TEXT NOT NULL,
    membership_episode_end TEXT NOT NULL,
    membership_evidence_fingerprint TEXT NOT NULL,
    membership_evidence_artifact_id TEXT NOT NULL,
    parameter_configuration_fingerprint TEXT NOT NULL,
    registered_at TEXT NOT NULL,
    experiment_spec_id TEXT,
    disposition TEXT NOT NULL CHECK (
        disposition IN (
            'PENDING',
            'EXECUTED',
            'REUSED',
            'INVALID',
            'INSUFFICIENT',
            'FAILED',
            'CANCELLED',
            'INTERRUPTED'
        )
    ),
    disposition_at TEXT NOT NULL,
    reused_attempt_id TEXT,
    failure_classification TEXT,
    failure_message TEXT,
    CHECK (
        membership_evidence_artifact_id
        = membership_evidence_fingerprint
    ),
    FOREIGN KEY (study_revision_id)
        REFERENCES study_revisions (study_revision_id),
    FOREIGN KEY (membership_evidence_artifact_id)
        REFERENCES research_artifacts (artifact_id),
    FOREIGN KEY (experiment_spec_id)
        REFERENCES experiment_specs (experiment_spec_id),
    FOREIGN KEY (reused_attempt_id)
        REFERENCES run_attempts (attempt_id),
    UNIQUE (
        study_revision_id,
        instrument_id,
        membership_episode_start,
        membership_episode_end,
        membership_evidence_fingerprint,
        parameter_configuration_fingerprint
    )
)
"""


_CREATE_RESEARCH_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS research_jobs (
    job_id TEXT PRIMARY KEY,
    trial_id TEXT NOT NULL,
    state TEXT NOT NULL CHECK (
        state IN (
            'QUEUED',
            'RUNNING',
            'SUCCEEDED',
            'FAILED',
            'CANCELLED',
            'INTERRUPTED'
        )
    ),
    created_at TEXT NOT NULL,
    claimed_at TEXT,
    terminal_at TEXT,
    worker_id TEXT,
    cancel_requested_at TEXT,
    attempt_id TEXT,
    completion_kind TEXT CHECK (
        completion_kind IS NULL
        OR completion_kind IN ('EXECUTED', 'REUSED')
    ),
    reused_attempt_id TEXT,
    reused_evidence_id TEXT,
    reused_result_artifact_id TEXT,
    failure_classification TEXT,
    failure_message TEXT,
    FOREIGN KEY (trial_id)
        REFERENCES trials (trial_id),
    FOREIGN KEY (attempt_id)
        REFERENCES run_attempts (attempt_id),
    FOREIGN KEY (reused_attempt_id)
        REFERENCES run_attempts (attempt_id),
    FOREIGN KEY (reused_evidence_id)
        REFERENCES research_evidence (evidence_id),
    FOREIGN KEY (reused_result_artifact_id)
        REFERENCES research_artifacts (artifact_id)
)
"""


_CREATE_RESEARCH_JOB_REUSE_DATASET_LINEAGE_TABLE = """
CREATE TABLE IF NOT EXISTS research_job_reuse_dataset_lineage (
    job_id TEXT PRIMARY KEY,
    requested_dataset_reference_artifact_id TEXT NOT NULL,
    source_dataset_reference_artifact_id TEXT NOT NULL,
    FOREIGN KEY (job_id)
        REFERENCES research_jobs (job_id),
    FOREIGN KEY (requested_dataset_reference_artifact_id)
        REFERENCES research_artifacts (artifact_id),
    FOREIGN KEY (source_dataset_reference_artifact_id)
        REFERENCES research_artifacts (artifact_id)
)
"""


_CREATE_RESEARCH_DATASET_REFERENCE_IDENTITIES_TABLE = """
CREATE TABLE IF NOT EXISTS research_dataset_reference_identities (
    artifact_id TEXT PRIMARY KEY,
    dataset_id TEXT NOT NULL,
    FOREIGN KEY (artifact_id)
        REFERENCES research_artifacts (artifact_id)
)
"""


_CREATE_RESEARCH_JOBS_STATE_CREATED_JOB_INDEX = """
CREATE INDEX IF NOT EXISTS
ix_research_jobs_state_created_job
ON research_jobs (
    state,
    created_at,
    job_id
)
"""


_CREATE_RESEARCH_JOBS_TRIAL_CREATED_JOB_INDEX = """
CREATE INDEX IF NOT EXISTS
ix_research_jobs_trial_created_job
ON research_jobs (
    trial_id,
    created_at,
    job_id
)
"""


_CREATE_V2_INDEXES = (
    _CREATE_RESEARCH_JOBS_STATE_CREATED_JOB_INDEX,
    _CREATE_RESEARCH_JOBS_TRIAL_CREATED_JOB_INDEX,
)


_EXPECTED_V2_INDEX_COLUMNS = {
    "ix_research_jobs_state_created_job": (
        "state",
        "created_at",
        "job_id",
    ),
    "ix_research_jobs_trial_created_job": (
        "trial_id",
        "created_at",
        "job_id",
    ),
}


_CREATE_TRIAL_DISPOSITION_EVENTS_TABLE = """
CREATE TABLE IF NOT EXISTS trial_disposition_events (
    event_id TEXT PRIMARY KEY,
    trial_id TEXT NOT NULL,
    sequence_number INTEGER NOT NULL
        CHECK (sequence_number > 0),
    previous_disposition TEXT CHECK (
        previous_disposition IS NULL
        OR previous_disposition IN (
            'PENDING',
            'EXECUTED',
            'REUSED',
            'INVALID',
            'INSUFFICIENT',
            'FAILED',
            'CANCELLED',
            'INTERRUPTED'
        )
    ),
    new_disposition TEXT NOT NULL CHECK (
        new_disposition IN (
            'PENDING',
            'EXECUTED',
            'REUSED',
            'INVALID',
            'INSUFFICIENT',
            'FAILED',
            'CANCELLED',
            'INTERRUPTED'
        )
    ),
    occurred_at TEXT NOT NULL,
    causing_job_id TEXT,
    reason_classification TEXT,
    reason_message TEXT,
    FOREIGN KEY (trial_id)
        REFERENCES trials (trial_id),
    FOREIGN KEY (causing_job_id)
        REFERENCES research_jobs (job_id),
    UNIQUE (trial_id, sequence_number)
)
"""


_CREATE_V1_CATALOG_TABLES = (
    _CREATE_RESEARCH_ARTIFACTS_TABLE,
    _CREATE_EXPERIMENT_SPECS_TABLE,
    _CREATE_RUN_ATTEMPTS_TABLE,
)

_CREATE_V2_TABLES = (
    _CREATE_STUDIES_TABLE,
    _CREATE_STUDY_REVISIONS_TABLE,
    _CREATE_TRIALS_TABLE,
    _CREATE_RESEARCH_JOBS_TABLE,
    _CREATE_TRIAL_DISPOSITION_EVENTS_TABLE,
)


_CREATE_V3_TABLES = (
    _CREATE_RESEARCH_JOB_REUSE_DATASET_LINEAGE_TABLE,
)


_CREATE_V4_TABLES = (
    _CREATE_RESEARCH_DATASET_REFERENCE_IDENTITIES_TABLE,
)


_V1_EXPECTED_TABLE_COLUMNS = {
    "research_evidence": (
        ("evidence_id", "TEXT", 0, 1),
        ("created_at", "TEXT", 1, 0),
        ("status", "TEXT", 1, 0),
        ("symbol", "TEXT", 1, 0),
        ("timeframe", "TEXT", 0, 0),
        ("timezone", "TEXT", 0, 0),
        ("request_start", "TEXT", 1, 0),
        ("request_end", "TEXT", 1, 0),
        ("dataset_fingerprint", "TEXT", 0, 0),
        ("configuration_fingerprint", "TEXT", 0, 0),
        ("result_fingerprint", "TEXT", 0, 0),
        ("provenance", "TEXT", 1, 0),
        ("repository_revision", "TEXT", 0, 0),
        ("summary", "TEXT", 1, 0),
        ("artifact_references", "TEXT", 1, 0),
    ),
    "research_artifacts": (
        ("artifact_id", "TEXT", 0, 1),
        ("artifact_kind", "TEXT", 1, 0),
        ("schema_id", "TEXT", 1, 0),
        ("relative_path", "TEXT", 1, 0),
        ("byte_count", "INTEGER", 1, 0),
        ("created_at", "TEXT", 1, 0),
    ),
    "experiment_specs": (
        ("experiment_spec_id", "TEXT", 0, 1),
        ("identity_schema", "TEXT", 1, 0),
        ("computation_kind", "TEXT", 1, 0),
        ("manifest_artifact_id", "TEXT", 1, 0),
        ("dataset_fingerprint", "TEXT", 1, 0),
        ("configuration_fingerprint", "TEXT", 1, 0),
        ("repository_revision", "TEXT", 1, 0),
        ("created_at", "TEXT", 1, 0),
    ),
    "run_attempts": (
        ("attempt_id", "TEXT", 0, 1),
        ("experiment_spec_id", "TEXT", 1, 0),
        ("state", "TEXT", 1, 0),
        ("created_at", "TEXT", 1, 0),
        ("terminal_at", "TEXT", 0, 0),
        ("runtime_session_id", "TEXT", 0, 0),
        ("result_artifact_id", "TEXT", 0, 0),
        ("evidence_id", "TEXT", 0, 0),
        ("failure_classification", "TEXT", 0, 0),
        ("failure_message", "TEXT", 0, 0),
    ),
}


_EXPECTED_TABLE_COLUMNS = {
    **_V1_EXPECTED_TABLE_COLUMNS,
    "studies": (
        ("study_id", "TEXT", 0, 1),
        ("created_at", "TEXT", 1, 0),
        ("display_title", "TEXT", 1, 0),
        ("archived", "INTEGER", 1, 0),
    ),
    "study_revisions": (
        ("study_revision_id", "TEXT", 0, 1),
        ("identity_schema", "TEXT", 1, 0),
        ("study_id", "TEXT", 1, 0),
        ("revision_number", "INTEGER", 1, 0),
        ("plan_artifact_id", "TEXT", 1, 0),
        ("repository_revision", "TEXT", 1, 0),
        ("evidence_reuse_policy", "TEXT", 1, 0),
        ("registered_at", "TEXT", 1, 0),
        ("initial_batch_started_at", "TEXT", 0, 0),
    ),
    "trials": (
        ("trial_id", "TEXT", 0, 1),
        ("identity_schema", "TEXT", 1, 0),
        ("study_revision_id", "TEXT", 1, 0),
        ("instrument_id", "TEXT", 1, 0),
        ("membership_episode_start", "TEXT", 1, 0),
        ("membership_episode_end", "TEXT", 1, 0),
        ("membership_evidence_fingerprint", "TEXT", 1, 0),
        ("membership_evidence_artifact_id", "TEXT", 1, 0),
        ("parameter_configuration_fingerprint", "TEXT", 1, 0),
        ("registered_at", "TEXT", 1, 0),
        ("experiment_spec_id", "TEXT", 0, 0),
        ("disposition", "TEXT", 1, 0),
        ("disposition_at", "TEXT", 1, 0),
        ("reused_attempt_id", "TEXT", 0, 0),
        ("failure_classification", "TEXT", 0, 0),
        ("failure_message", "TEXT", 0, 0),
    ),
    "research_jobs": (
        ("job_id", "TEXT", 0, 1),
        ("trial_id", "TEXT", 1, 0),
        ("state", "TEXT", 1, 0),
        ("created_at", "TEXT", 1, 0),
        ("claimed_at", "TEXT", 0, 0),
        ("terminal_at", "TEXT", 0, 0),
        ("worker_id", "TEXT", 0, 0),
        ("cancel_requested_at", "TEXT", 0, 0),
        ("attempt_id", "TEXT", 0, 0),
        ("completion_kind", "TEXT", 0, 0),
        ("reused_attempt_id", "TEXT", 0, 0),
        ("reused_evidence_id", "TEXT", 0, 0),
        ("reused_result_artifact_id", "TEXT", 0, 0),
        ("failure_classification", "TEXT", 0, 0),
        ("failure_message", "TEXT", 0, 0),
    ),
    "trial_disposition_events": (
        ("event_id", "TEXT", 0, 1),
        ("trial_id", "TEXT", 1, 0),
        ("sequence_number", "INTEGER", 1, 0),
        ("previous_disposition", "TEXT", 0, 0),
        ("new_disposition", "TEXT", 1, 0),
        ("occurred_at", "TEXT", 1, 0),
        ("causing_job_id", "TEXT", 0, 0),
        ("reason_classification", "TEXT", 0, 0),
        ("reason_message", "TEXT", 0, 0),
    ),
}

_V2_EXPECTED_TABLE_COLUMNS = _EXPECTED_TABLE_COLUMNS

_V3_EXPECTED_TABLE_COLUMNS = {
    **_V2_EXPECTED_TABLE_COLUMNS,
    "research_job_reuse_dataset_lineage": (
        ("job_id", "TEXT", 0, 1),
        (
            "requested_dataset_reference_artifact_id",
            "TEXT",
            1,
            0,
        ),
        (
            "source_dataset_reference_artifact_id",
            "TEXT",
            1,
            0,
        ),
    ),
}


_EXPECTED_TABLE_COLUMNS = {
    **_V3_EXPECTED_TABLE_COLUMNS,
    "research_dataset_reference_identities": (
        ("artifact_id", "TEXT", 0, 1),
        ("dataset_id", "TEXT", 1, 0),
    ),
}


def _table_exists(
    connection: sqlite3.Connection,
    table_name: str,
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (table_name,),
    ).fetchone()
    return row is not None


def _user_table_names(
    connection: sqlite3.Connection,
) -> set[str]:
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


def _validate_table(
    connection: sqlite3.Connection,
    table_name: str,
    expected_columns: dict[str, tuple] | None = None,
) -> None:
    columns = (
        _EXPECTED_TABLE_COLUMNS
        if expected_columns is None
        else expected_columns
    )

    rows = connection.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    actual = tuple(
        (
            row[1],
            str(row[2]).upper(),
            int(row[3]),
            int(row[5]),
        )
        for row in rows
    )
    expected = columns[table_name]

    if actual != expected:
        raise RuntimeError(
            f"incompatible {table_name} table for supported "
            "research schema"
        )


def _validate_required_schema(
    connection: sqlite3.Connection,
    expected_columns: dict[str, tuple],
    version: int,
) -> None:
    for table_name in expected_columns:
        if not _table_exists(connection, table_name):
            raise RuntimeError(
                "research schema version "
                f"{version} is missing required "
                f"{table_name} table"
            )

        _validate_table(
            connection,
            table_name,
            expected_columns,
        )


def _validate_current_schema(
    connection: sqlite3.Connection,
) -> None:
    _validate_required_schema(
        connection,
        _EXPECTED_TABLE_COLUMNS,
        RESEARCH_SCHEMA_VERSION,
    )


def _index_columns(
    connection: sqlite3.Connection,
    index_name: str,
) -> tuple[str, ...]:
    rows = connection.execute(
        f"PRAGMA index_info({index_name})"
    ).fetchall()

    return tuple(
        row[2]
        for row in rows
    )


def _validate_current_indexes(
    connection: sqlite3.Connection,
) -> None:
    for (
        index_name,
        expected_columns,
    ) in _EXPECTED_V2_INDEX_COLUMNS.items():
        actual = _index_columns(
            connection,
            index_name,
        )

        if actual != expected_columns:
            raise RuntimeError(
                f"incompatible or missing {index_name} "
                "for supported research schema"
            )


def _create_and_validate_v2_indexes(
    connection: sqlite3.Connection,
) -> None:
    for statement in _CREATE_V2_INDEXES:
        connection.execute(statement)

    _validate_current_indexes(
        connection
    )


def _migrate_v1_to_v4(
    connection: sqlite3.Connection,
) -> None:
    _validate_required_schema(
        connection,
        _V1_EXPECTED_TABLE_COLUMNS,
        1,
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

        for statement in _CREATE_V2_TABLES:
            connection.execute(statement)

        for statement in _CREATE_V3_TABLES:
            connection.execute(statement)

        for statement in _CREATE_V4_TABLES:
            connection.execute(statement)

        _create_and_validate_v2_indexes(
            connection
        )

        _validate_current_schema(connection)

        connection.execute(
            f"PRAGMA user_version = {RESEARCH_SCHEMA_VERSION}"
        )
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def _migrate_v2_to_v4(
    connection: sqlite3.Connection,
) -> None:
    _validate_required_schema(
        connection,
        _V2_EXPECTED_TABLE_COLUMNS,
        2,
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

        for statement in _CREATE_V3_TABLES:
            connection.execute(statement)

        for statement in _CREATE_V4_TABLES:
            connection.execute(statement)

        _create_and_validate_v2_indexes(
            connection
        )

        _validate_current_schema(connection)

        connection.execute(
            f"PRAGMA user_version = {RESEARCH_SCHEMA_VERSION}"
        )
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def _migrate_v3_to_v4(
    connection: sqlite3.Connection,
) -> None:
    _validate_required_schema(
        connection,
        _V3_EXPECTED_TABLE_COLUMNS,
        3,
    )

    try:
        connection.execute("BEGIN IMMEDIATE")

        for statement in _CREATE_V4_TABLES:
            connection.execute(statement)

        _create_and_validate_v2_indexes(
            connection
        )

        _validate_current_schema(
            connection
        )

        connection.execute(
            f"PRAGMA user_version = {RESEARCH_SCHEMA_VERSION}"
        )
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()


def initialize_research_schema(
    connection: sqlite3.Connection,
) -> None:
    """Create or migrate the supported research schema transactionally."""

    if not isinstance(connection, sqlite3.Connection):
        raise TypeError(
            "connection must be a sqlite3.Connection"
        )

    current_version = int(
        connection.execute(
            "PRAGMA user_version"
        ).fetchone()[0]
    )

    if current_version > RESEARCH_SCHEMA_VERSION:
        raise RuntimeError(
            "research schema version "
            f"{current_version} is newer than supported version "
            f"{RESEARCH_SCHEMA_VERSION}"
        )

    if current_version == RESEARCH_SCHEMA_VERSION:
        _validate_current_schema(connection)

        try:
            connection.execute("BEGIN IMMEDIATE")

            _create_and_validate_v2_indexes(
                connection
            )

        except Exception:
            connection.rollback()
            raise

        else:
            connection.commit()

        return

    if current_version == 3:
        _migrate_v3_to_v4(connection)
        return

    if current_version == 2:
        _migrate_v2_to_v4(connection)
        return

    if current_version == 1:
        _migrate_v1_to_v4(connection)
        return

    if current_version != 0:
        raise RuntimeError(
            "research schema version "
            f"{current_version} has no supported migration path"
        )

    existing_tables = _user_table_names(connection)
    unexpected_tables = (
        existing_tables - set(_EXPECTED_TABLE_COLUMNS)
    )

    if unexpected_tables:
        names = ", ".join(sorted(unexpected_tables))
        raise RuntimeError(
            "unexpected tables in unversioned research database: "
            f"{names}"
        )

    for table_name in _EXPECTED_TABLE_COLUMNS:
        if _table_exists(connection, table_name):
            _validate_table(connection, table_name)

    try:
        connection.execute("BEGIN IMMEDIATE")

        if not _table_exists(
            connection,
            "research_evidence",
        ):
            connection.execute(
                _CREATE_RESEARCH_EVIDENCE_TABLE
            )

        for statement in _CREATE_V1_CATALOG_TABLES:
            connection.execute(statement)

        for statement in _CREATE_V2_TABLES:
            connection.execute(statement)

        for statement in _CREATE_V3_TABLES:
            connection.execute(statement)

        for statement in _CREATE_V4_TABLES:
            connection.execute(statement)

        _create_and_validate_v2_indexes(
            connection
        )

        _validate_current_schema(connection)

        connection.execute(
            f"PRAGMA user_version = {RESEARCH_SCHEMA_VERSION}"
        )
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()

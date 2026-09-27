"""Versioned SQLite schema ownership for durable research metadata."""

import sqlite3


RESEARCH_SCHEMA_VERSION = 1


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


_CREATE_CATALOG_TABLES = (
    _CREATE_RESEARCH_ARTIFACTS_TABLE,
    _CREATE_EXPERIMENT_SPECS_TABLE,
    _CREATE_RUN_ATTEMPTS_TABLE,
)


_EXPECTED_TABLE_COLUMNS = {
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
) -> None:
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
    expected = _EXPECTED_TABLE_COLUMNS[table_name]

    if actual != expected:
        raise RuntimeError(
            f"incompatible {table_name} table for supported "
            "research schema"
        )


def _validate_current_schema(
    connection: sqlite3.Connection,
) -> None:
    for table_name in _EXPECTED_TABLE_COLUMNS:
        if not _table_exists(connection, table_name):
            raise RuntimeError(
                "research schema version "
                f"{RESEARCH_SCHEMA_VERSION} is missing required "
                f"{table_name} table"
            )
        _validate_table(connection, table_name)


def initialize_research_schema(connection: sqlite3.Connection) -> None:
    """Create or migrate the supported research schema transactionally."""

    if not isinstance(connection, sqlite3.Connection):
        raise TypeError("connection must be a sqlite3.Connection")

    row = connection.execute("PRAGMA user_version").fetchone()
    current_version = int(row[0])

    if current_version > RESEARCH_SCHEMA_VERSION:
        raise RuntimeError(
            "research schema version "
            f"{current_version} is newer than supported version "
            f"{RESEARCH_SCHEMA_VERSION}"
        )

    if current_version not in (0, RESEARCH_SCHEMA_VERSION):
        raise RuntimeError(
            "research schema version "
            f"{current_version} has no supported migration path"
        )

    if current_version == RESEARCH_SCHEMA_VERSION:
        _validate_current_schema(connection)
        return

    # An unversioned database may be new, the accepted evidence-only
    # legacy database, or a compatible partial research-catalog setup.
    # Unrelated tables mean this is not safely identifiable as the
    # research database and must not be adopted or modified.
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

    # Validate every recognized version-0 table before mutation.
    for table_name in _EXPECTED_TABLE_COLUMNS:
        if _table_exists(connection, table_name):
            _validate_table(connection, table_name)

    try:
        # SQLite DDL must be placed inside an explicit transaction.
        # Relying only on the connection context manager does not
        # guarantee CREATE TABLE has started a transaction.
        connection.execute("BEGIN IMMEDIATE")

        if not _table_exists(connection, "research_evidence"):
            connection.execute(_CREATE_RESEARCH_EVIDENCE_TABLE)

        for statement in _CREATE_CATALOG_TABLES:
            connection.execute(statement)

        _validate_current_schema(connection)

        connection.execute(
            f"PRAGMA user_version = {RESEARCH_SCHEMA_VERSION}"
        )
    except Exception:
        connection.rollback()
        raise
    else:
        connection.commit()

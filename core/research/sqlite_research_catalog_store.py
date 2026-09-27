"""Durable SQLite persistence for M9.2 research catalog lifecycle."""

from collections.abc import Callable
from contextlib import closing
from datetime import datetime
from pathlib import Path
import sqlite3
from uuid import uuid4

from core.research.models.research_catalog import (
    ComputationKind,
    ExperimentSpec,
    ResearchArtifact,
    ResearchArtifactKind,
    RunAttempt,
    RunAttemptState,
)
from core.research.reproducibility import experiment_spec_fingerprint
from core.research.research_schema import initialize_research_schema


_M92C_TERMINAL_STATES = {
    RunAttemptState.SUCCEEDED,
    RunAttemptState.FAILED,
    RunAttemptState.INTERRUPTED,
}


def _default_attempt_id() -> str:
    return f"attempt-{uuid4().hex}"


class SQLiteResearchCatalogStore:
    """Persist immutable Specs and physical execution attempts."""

    def __init__(
        self,
        database_path: str | Path,
        *,
        attempt_id_factory: Callable[[], str] | None = None,
    ):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        self._attempt_id_factory = (
            attempt_id_factory or _default_attempt_id
        )
        self._initialize_schema()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")

        row = connection.execute(
            "PRAGMA foreign_keys"
        ).fetchone()

        if row is None or row[0] != 1:
            connection.close()
            raise RuntimeError(
                "research catalog requires SQLite foreign keys"
            )

        return connection

    def _initialize_schema(self) -> None:
        with closing(self._connect()) as connection:
            initialize_research_schema(connection)

    @staticmethod
    def _artifact_from_row(row) -> ResearchArtifact:
        return ResearchArtifact(
            artifact_id=row[0],
            artifact_kind=ResearchArtifactKind(row[1]),
            schema_id=row[2],
            relative_path=row[3],
            byte_count=row[4],
            created_at=datetime.fromisoformat(row[5]),
        )

    @staticmethod
    def _spec_from_row(row) -> ExperimentSpec:
        return ExperimentSpec(
            experiment_spec_id=row[0],
            identity_schema=row[1],
            computation_kind=ComputationKind(row[2]),
            manifest_artifact_id=row[3],
            dataset_fingerprint=row[4],
            configuration_fingerprint=row[5],
            repository_revision=row[6],
            created_at=datetime.fromisoformat(row[7]),
        )

    @staticmethod
    def _attempt_from_row(row) -> RunAttempt:
        return RunAttempt(
            attempt_id=row[0],
            experiment_spec_id=row[1],
            state=RunAttemptState(row[2]),
            created_at=datetime.fromisoformat(row[3]),
            terminal_at=(
                datetime.fromisoformat(row[4])
                if row[4] is not None
                else None
            ),
            runtime_session_id=row[5],
            result_artifact_id=row[6],
            evidence_id=row[7],
            failure_classification=row[8],
            failure_message=row[9],
        )

    @staticmethod
    def _artifact_semantics(
        artifact: ResearchArtifact,
    ) -> tuple:
        return (
            artifact.artifact_id,
            artifact.artifact_kind,
            artifact.schema_id,
            artifact.relative_path,
            artifact.byte_count,
        )

    @staticmethod
    def _spec_semantics(
        spec: ExperimentSpec,
    ) -> tuple:
        return (
            spec.experiment_spec_id,
            spec.identity_schema,
            spec.computation_kind,
            spec.manifest_artifact_id,
            spec.dataset_fingerprint,
            spec.configuration_fingerprint,
            spec.repository_revision,
        )

    def save_artifact(
        self,
        artifact: ResearchArtifact,
    ) -> ResearchArtifact:
        """Register immutable artifact metadata; identical reuse is idempotent."""

        if not isinstance(artifact, ResearchArtifact):
            raise TypeError(
                "artifact must be a ResearchArtifact"
            )

        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO research_artifacts (
                            artifact_id,
                            artifact_kind,
                            schema_id,
                            relative_path,
                            byte_count,
                            created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            artifact.artifact_id,
                            artifact.artifact_kind.value,
                            artifact.schema_id,
                            artifact.relative_path,
                            artifact.byte_count,
                            artifact.created_at.isoformat(
                                timespec="microseconds"
                            ),
                        ),
                    )
        except sqlite3.IntegrityError as error:
            existing = self.load_artifact(
                artifact.artifact_id
            )

            if existing is None:
                raise ValueError(
                    "research artifact metadata could not be persisted"
                ) from error

            if (
                self._artifact_semantics(existing)
                != self._artifact_semantics(artifact)
            ):
                raise ValueError(
                    "research artifact identity already has "
                    "different immutable metadata"
                ) from error

            return existing

        return artifact

    def load_artifact(
        self,
        artifact_id: str,
    ) -> ResearchArtifact | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    artifact_id,
                    artifact_kind,
                    schema_id,
                    relative_path,
                    byte_count,
                    created_at
                FROM research_artifacts
                WHERE artifact_id = ?
                """,
                (artifact_id,),
            ).fetchone()

        if row is None:
            return None

        return self._artifact_from_row(row)

    def resolve_experiment_spec(
        self,
        *,
        computation_kind: ComputationKind,
        manifest_artifact_id: str,
        dataset_fingerprint: str,
        configuration_fingerprint: str,
        repository_revision: str,
        created_at: datetime,
    ) -> ExperimentSpec:
        """Resolve one immutable deterministic ExperimentSpec."""

        experiment_spec_id = experiment_spec_fingerprint(
            computation_kind=computation_kind,
            manifest_artifact_id=manifest_artifact_id,
            dataset_fingerprint=dataset_fingerprint,
            configuration_fingerprint=configuration_fingerprint,
            repository_revision=repository_revision,
        )

        candidate = ExperimentSpec(
            experiment_spec_id=experiment_spec_id,
            computation_kind=computation_kind,
            manifest_artifact_id=manifest_artifact_id,
            dataset_fingerprint=dataset_fingerprint,
            configuration_fingerprint=configuration_fingerprint,
            repository_revision=repository_revision,
            created_at=created_at,
        )

        existing = self.load_experiment_spec(
            experiment_spec_id
        )

        if existing is not None:
            if (
                self._spec_semantics(existing)
                != self._spec_semantics(candidate)
            ):
                raise ValueError(
                    "ExperimentSpec identity already has "
                    "different immutable inputs"
                )
            return existing

        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO experiment_specs (
                            experiment_spec_id,
                            identity_schema,
                            computation_kind,
                            manifest_artifact_id,
                            dataset_fingerprint,
                            configuration_fingerprint,
                            repository_revision,
                            created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            candidate.experiment_spec_id,
                            candidate.identity_schema,
                            candidate.computation_kind.value,
                            candidate.manifest_artifact_id,
                            candidate.dataset_fingerprint,
                            candidate.configuration_fingerprint,
                            candidate.repository_revision,
                            candidate.created_at.isoformat(
                                timespec="microseconds"
                            ),
                        ),
                    )
        except sqlite3.IntegrityError as error:
            existing = self.load_experiment_spec(
                experiment_spec_id
            )

            if (
                existing is not None
                and self._spec_semantics(existing)
                == self._spec_semantics(candidate)
            ):
                return existing

            raise ValueError(
                "ExperimentSpec requires registered immutable inputs"
            ) from error

        return candidate

    def load_experiment_spec(
        self,
        experiment_spec_id: str,
    ) -> ExperimentSpec | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    experiment_spec_id,
                    identity_schema,
                    computation_kind,
                    manifest_artifact_id,
                    dataset_fingerprint,
                    configuration_fingerprint,
                    repository_revision,
                    created_at
                FROM experiment_specs
                WHERE experiment_spec_id = ?
                """,
                (experiment_spec_id,),
            ).fetchone()

        if row is None:
            return None

        return self._spec_from_row(row)

    def create_running_attempt(
        self,
        *,
        experiment_spec_id: str,
        created_at: datetime,
        runtime_session_id: str | None = None,
    ) -> RunAttempt:
        """Create one distinct physical RUNNING execution attempt."""

        attempt = RunAttempt(
            attempt_id=self._attempt_id_factory(),
            experiment_spec_id=experiment_spec_id,
            state=RunAttemptState.RUNNING,
            created_at=created_at,
            runtime_session_id=runtime_session_id,
        )

        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO run_attempts (
                            attempt_id,
                            experiment_spec_id,
                            state,
                            created_at,
                            terminal_at,
                            runtime_session_id,
                            result_artifact_id,
                            evidence_id,
                            failure_classification,
                            failure_message
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            attempt.attempt_id,
                            attempt.experiment_spec_id,
                            attempt.state.value,
                            attempt.created_at.isoformat(
                                timespec="microseconds"
                            ),
                            None,
                            attempt.runtime_session_id,
                            None,
                            None,
                            None,
                            None,
                        ),
                    )
        except sqlite3.IntegrityError as error:
            raise ValueError(
                "RunAttempt requires an existing ExperimentSpec "
                "and a unique attempt ID"
            ) from error

        return attempt

    def load_run_attempt(
        self,
        attempt_id: str,
    ) -> RunAttempt | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    attempt_id,
                    experiment_spec_id,
                    state,
                    created_at,
                    terminal_at,
                    runtime_session_id,
                    result_artifact_id,
                    evidence_id,
                    failure_classification,
                    failure_message
                FROM run_attempts
                WHERE attempt_id = ?
                """,
                (attempt_id,),
            ).fetchone()

        if row is None:
            return None

        return self._attempt_from_row(row)

    def terminalize_attempt(
        self,
        attempt_id: str,
        *,
        state: RunAttemptState,
        terminal_at: datetime,
        runtime_session_id: str | None = None,
        result_artifact_id: str | None = None,
        evidence_id: str | None = None,
        failure_classification: str | None = None,
        failure_message: str | None = None,
    ) -> RunAttempt:
        """Perform one immutable RUNNING-to-terminal transition."""

        if not isinstance(state, RunAttemptState):
            raise TypeError("state must be a RunAttemptState")

        if state not in _M92C_TERMINAL_STATES:
            raise ValueError(
                "M9.2c terminal state must be "
                "SUCCEEDED, FAILED or INTERRUPTED"
            )

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                row = connection.execute(
                    """
                    SELECT
                        attempt_id,
                        experiment_spec_id,
                        state,
                        created_at,
                        terminal_at,
                        runtime_session_id,
                        result_artifact_id,
                        evidence_id,
                        failure_classification,
                        failure_message
                    FROM run_attempts
                    WHERE attempt_id = ?
                    """,
                    (attempt_id,),
                ).fetchone()

                if row is None:
                    raise ValueError(
                        f"RunAttempt does not exist: {attempt_id}"
                    )

                current = self._attempt_from_row(row)

                if current.state is not RunAttemptState.RUNNING:
                    raise ValueError(
                        "terminal RunAttempt cannot be reopened "
                        "or overwritten"
                    )

                if (
                    current.runtime_session_id is not None
                    and runtime_session_id is not None
                    and current.runtime_session_id
                    != runtime_session_id
                ):
                    raise ValueError(
                        "runtime_session_id cannot be replaced "
                        "after attempt creation"
                    )

                final_runtime_session_id = (
                    current.runtime_session_id
                    if runtime_session_id is None
                    else runtime_session_id
                )

                terminal = RunAttempt(
                    attempt_id=current.attempt_id,
                    experiment_spec_id=current.experiment_spec_id,
                    state=state,
                    created_at=current.created_at,
                    terminal_at=terminal_at,
                    runtime_session_id=final_runtime_session_id,
                    result_artifact_id=result_artifact_id,
                    evidence_id=evidence_id,
                    failure_classification=failure_classification,
                    failure_message=failure_message,
                )

                cursor = connection.execute(
                    """
                    UPDATE run_attempts
                    SET
                        state = ?,
                        terminal_at = ?,
                        runtime_session_id = ?,
                        result_artifact_id = ?,
                        evidence_id = ?,
                        failure_classification = ?,
                        failure_message = ?
                    WHERE
                        attempt_id = ?
                        AND state = 'RUNNING'
                    """,
                    (
                        terminal.state.value,
                        terminal.terminal_at.isoformat(
                            timespec="microseconds"
                        ),
                        terminal.runtime_session_id,
                        terminal.result_artifact_id,
                        terminal.evidence_id,
                        terminal.failure_classification,
                        terminal.failure_message,
                        terminal.attempt_id,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "RunAttempt terminal transition lost "
                        "its RUNNING precondition"
                    )

                connection.commit()

            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise ValueError(
                    "terminal RunAttempt references must already "
                    "exist in the research catalog"
                ) from error
            except Exception:
                connection.rollback()
                raise

        return terminal

"""Durable SQLite persistence for M9.2 research catalog lifecycle."""

from collections.abc import Callable
from contextlib import closing
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from core.research.models.dataset_reference import (
    DATASET_REFERENCE_SCHEMA_ID,
)
from core.research.models.research_catalog import (
    ComputationKind,
    ExperimentSpec,
    ResearchArtifact,
    ResearchArtifactKind,
    RunAttempt,
    RunAttemptState,
)
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    INITIAL_RESEARCH_JOB_SCHEMA_ID,
    RETRY_RESEARCH_JOB_SCHEMA_ID,
    RESEARCH_MAX_WORKERS_SAFETY_CEILING,
    STUDY_REVISION_SCHEMA_ID,
    TRIAL_MEMBERSHIP_EVIDENCE_SCHEMA_ID,
    ResearchJob,
    ResearchJobCompletionKind,
    ResearchJobState,
    ResearchQueueSnapshot,
    Study,
    StudyRevision,
    Trial,
    TrialDisposition,
    TrialDispositionEvent,
)
from core.research.models.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStatus,
)
from core.research.reproducibility import (
    BACKTEST_RESULT_SCHEMA,
    BACKTEST_RUN_MANIFEST_SCHEMA,
    canonical_fingerprint,
    experiment_spec_fingerprint,
)
from core.research.research_artifact_store import (
    research_artifact_reference,
)
from core.research.research_schema import initialize_research_schema
from core.research.sqlite_research_evidence_store import (
    _insert_research_evidence,
)


_TRIAL_DISPOSITION_EVENT_SCHEMA_ID = (
    "kanasu.trial-disposition-event.v1"
)


_M92C_TERMINAL_STATES = {
    RunAttemptState.SUCCEEDED,
    RunAttemptState.FAILED,
    RunAttemptState.INTERRUPTED,
}


def _default_attempt_id() -> str:
    return f"attempt-{uuid4().hex}"


def _initial_research_job_id(
    trial_id: str,
) -> str:
    return canonical_fingerprint(
        {
            "trial_id": trial_id,
            "purpose": "INITIAL",
        },
        schema=INITIAL_RESEARCH_JOB_SCHEMA_ID,
    )


def _retry_research_job_id(
    trial_id: str,
    retry_ordinal: int,
) -> str:
    if (
        type(retry_ordinal) is not int
        or retry_ordinal <= 0
    ):
        raise ValueError(
            "retry_ordinal must be a positive integer"
        )

    return canonical_fingerprint(
        {
            "trial_id": trial_id,
            "purpose": "RETRY",
            "retry_ordinal": retry_ordinal,
        },
        schema=RETRY_RESEARCH_JOB_SCHEMA_ID,
    )


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

    def list_succeeded_attempts_for_experiment_spec(
        self,
        experiment_spec_id: str,
    ) -> tuple[RunAttempt, ...]:
        """Return successful attempts in deterministic historical order."""

        with closing(self._connect()) as connection:
            rows = connection.execute(
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
                WHERE
                    experiment_spec_id = ?
                    AND state = 'SUCCEEDED'
                ORDER BY terminal_at ASC, attempt_id ASC
                """,
                (experiment_spec_id,),
            ).fetchall()

        return tuple(
            self._attempt_from_row(row)
            for row in rows
        )

    def terminalize_attempt_with_evidence(
        self,
        attempt_id: str,
        *,
        state: RunAttemptState,
        terminal_at: datetime,
        evidence: ResearchEvidence,
        runtime_session_id: str | None = None,
        result_artifact: ResearchArtifact | None = None,
        failure_classification: str | None = None,
        failure_message: str | None = None,
    ) -> RunAttempt:
        """Commit evidence, result metadata and terminal attempt atomically."""

        if state not in {
            RunAttemptState.SUCCEEDED,
            RunAttemptState.FAILED,
        }:
            raise ValueError(
                "atomic evidence terminalization requires "
                "SUCCEEDED or FAILED"
            )

        if not isinstance(evidence, ResearchEvidence):
            raise TypeError("evidence must be ResearchEvidence")

        if (
            result_artifact is not None
            and not isinstance(result_artifact, ResearchArtifact)
        ):
            raise TypeError(
                "result_artifact must be a ResearchArtifact or None"
            )

        if state is RunAttemptState.SUCCEEDED:
            if result_artifact is None:
                raise ValueError(
                    "SUCCEEDED terminalization requires result artifact"
                )
            if evidence.status is not ResearchEvidenceStatus.ACCEPTED:
                raise ValueError(
                    "SUCCEEDED terminalization requires ACCEPTED evidence"
                )

        if (
            state is RunAttemptState.FAILED
            and evidence.status is ResearchEvidenceStatus.ACCEPTED
        ):
            raise ValueError(
                "FAILED terminalization cannot use ACCEPTED evidence"
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

                if result_artifact is not None:
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO research_artifacts (
                            artifact_id,
                            artifact_kind,
                            schema_id,
                            relative_path,
                            byte_count,
                            created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            result_artifact.artifact_id,
                            result_artifact.artifact_kind.value,
                            result_artifact.schema_id,
                            result_artifact.relative_path,
                            result_artifact.byte_count,
                            result_artifact.created_at.isoformat(
                                timespec="microseconds"
                            ),
                        ),
                    )

                    artifact_row = connection.execute(
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
                        (result_artifact.artifact_id,),
                    ).fetchone()

                    if artifact_row is None:
                        raise ValueError(
                            "result artifact metadata could not be registered"
                        )

                    registered = self._artifact_from_row(artifact_row)

                    if (
                        self._artifact_semantics(registered)
                        != self._artifact_semantics(result_artifact)
                    ):
                        raise ValueError(
                            "research artifact identity already has "
                            "different immutable metadata"
                        )

                terminal = RunAttempt(
                    attempt_id=current.attempt_id,
                    experiment_spec_id=current.experiment_spec_id,
                    state=state,
                    created_at=current.created_at,
                    terminal_at=terminal_at,
                    runtime_session_id=final_runtime_session_id,
                    result_artifact_id=(
                        result_artifact.artifact_id
                        if result_artifact is not None
                        else None
                    ),
                    evidence_id=evidence.evidence_id,
                    failure_classification=failure_classification,
                    failure_message=failure_message,
                )

                _insert_research_evidence(connection, evidence)

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
                    "terminal research transaction could not be committed"
                ) from error
            except Exception:
                connection.rollback()
                raise

        return terminal

    def recover_running_attempts(
        self,
        *,
        terminal_at: datetime,
    ) -> tuple[RunAttempt, ...]:
        """Recover stale M9.2 RUNNING attempts as INTERRUPTED."""

        recovered = []

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                rows = connection.execute(
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
                    WHERE state = 'RUNNING'
                    ORDER BY created_at, attempt_id
                    """
                ).fetchall()

                for row in rows:
                    current = self._attempt_from_row(row)
                    effective_terminal_at = max(
                        terminal_at,
                        current.created_at,
                    )

                    terminal = RunAttempt(
                        attempt_id=current.attempt_id,
                        experiment_spec_id=current.experiment_spec_id,
                        state=RunAttemptState.INTERRUPTED,
                        created_at=current.created_at,
                        terminal_at=effective_terminal_at,
                        runtime_session_id=current.runtime_session_id,
                        failure_classification="application_restart",
                        failure_message=(
                            "RUNNING attempt recovered as INTERRUPTED "
                            "during application startup"
                        ),
                    )

                    cursor = connection.execute(
                        """
                        UPDATE run_attempts
                        SET
                            state = ?,
                            terminal_at = ?,
                            result_artifact_id = NULL,
                            evidence_id = NULL,
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
                            terminal.failure_classification,
                            terminal.failure_message,
                            terminal.attempt_id,
                        ),
                    )

                    if cursor.rowcount != 1:
                        raise RuntimeError(
                            "RUNNING recovery lost its state precondition"
                        )

                    recovered.append(terminal)

                connection.commit()

            except Exception:
                connection.rollback()
                raise

        return tuple(recovered)

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

    # --------------------------------------------------------------
    # M9.4a registered Study / Trial / ResearchJob persistence.
    #
    # These methods intentionally do not implement whole-revision
    # registration, Start, claim, execution, retry, cancellation,
    # recovery or scheduling. Later M9.4 slices own those atomic
    # lifecycle operations.
    # --------------------------------------------------------------

    @staticmethod
    def _study_from_row(row) -> Study:
        return Study(
            study_id=row[0],
            created_at=datetime.fromisoformat(row[1]),
            display_title=row[2],
            archived=bool(row[3]),
        )

    @staticmethod
    def _study_revision_from_row(row) -> StudyRevision:
        return StudyRevision(
            study_revision_id=row[0],
            identity_schema=row[1],
            study_id=row[2],
            revision_number=row[3],
            plan_artifact_id=row[4],
            repository_revision=row[5],
            evidence_reuse_policy=EvidenceReusePolicy(row[6]),
            registered_at=datetime.fromisoformat(row[7]),
            initial_batch_started_at=(
                datetime.fromisoformat(row[8])
                if row[8] is not None
                else None
            ),
        )

    @staticmethod
    def _trial_from_row(row) -> Trial:
        return Trial(
            trial_id=row[0],
            identity_schema=row[1],
            study_revision_id=row[2],
            instrument_id=row[3],
            membership_episode_start=datetime.fromisoformat(
                row[4]
            ),
            membership_episode_end=datetime.fromisoformat(
                row[5]
            ),
            membership_evidence_fingerprint=row[6],
            membership_evidence_artifact_id=row[7],
            parameter_configuration_fingerprint=row[8],
            registered_at=datetime.fromisoformat(row[9]),
            experiment_spec_id=row[10],
            disposition=TrialDisposition(row[11]),
            disposition_at=datetime.fromisoformat(row[12]),
            reused_attempt_id=row[13],
            failure_classification=row[14],
            failure_message=row[15],
        )

    @staticmethod
    def _trial_event_from_row(row) -> TrialDispositionEvent:
        return TrialDispositionEvent(
            event_id=row[0],
            trial_id=row[1],
            sequence_number=row[2],
            previous_disposition=(
                TrialDisposition(row[3])
                if row[3] is not None
                else None
            ),
            new_disposition=TrialDisposition(row[4]),
            occurred_at=datetime.fromisoformat(row[5]),
            causing_job_id=row[6],
            reason_classification=row[7],
            reason_message=row[8],
        )

    @staticmethod
    def _research_job_from_row(row) -> ResearchJob:
        return ResearchJob(
            job_id=row[0],
            trial_id=row[1],
            state=ResearchJobState(row[2]),
            created_at=datetime.fromisoformat(row[3]),
            claimed_at=(
                datetime.fromisoformat(row[4])
                if row[4] is not None
                else None
            ),
            terminal_at=(
                datetime.fromisoformat(row[5])
                if row[5] is not None
                else None
            ),
            worker_id=row[6],
            cancel_requested_at=(
                datetime.fromisoformat(row[7])
                if row[7] is not None
                else None
            ),
            attempt_id=row[8],
            completion_kind=(
                ResearchJobCompletionKind(row[9])
                if row[9] is not None
                else None
            ),
            reused_attempt_id=row[10],
            reused_evidence_id=row[11],
            reused_result_artifact_id=row[12],
            failure_classification=row[13],
            failure_message=row[14],
        )

    @staticmethod
    def _study_semantics(study: Study) -> tuple:
        return (
            study.study_id,
            study.created_at,
            study.display_title,
            study.archived,
        )

    @staticmethod
    def _study_revision_semantics(
        revision: StudyRevision,
    ) -> tuple:
        return (
            revision.study_revision_id,
            revision.identity_schema,
            revision.study_id,
            revision.revision_number,
            revision.plan_artifact_id,
            revision.repository_revision,
            revision.evidence_reuse_policy,
        )

    @staticmethod
    def _trial_registration_semantics(
        trial: Trial,
    ) -> tuple:
        return (
            trial.trial_id,
            trial.identity_schema,
            trial.study_revision_id,
            trial.instrument_id,
            trial.membership_episode_start,
            trial.membership_episode_end,
            trial.membership_evidence_fingerprint,
            trial.membership_evidence_artifact_id,
            trial.parameter_configuration_fingerprint,
            trial.disposition,
            trial.experiment_spec_id,
            trial.reused_attempt_id,
            trial.failure_classification,
            trial.failure_message,
        )

    @staticmethod
    def _trial_event_semantics(
        event: TrialDispositionEvent,
    ) -> tuple:
        return (
            event.event_id,
            event.trial_id,
            event.sequence_number,
            event.previous_disposition,
            event.new_disposition,
            event.occurred_at,
            event.causing_job_id,
            event.reason_classification,
            event.reason_message,
        )

    @staticmethod
    def _research_job_semantics(
        job: ResearchJob,
    ) -> tuple:
        return (
            job.job_id,
            job.trial_id,
            job.state,
            job.created_at,
            job.claimed_at,
            job.terminal_at,
            job.worker_id,
            job.cancel_requested_at,
            job.attempt_id,
            job.completion_kind,
            job.reused_attempt_id,
            job.reused_evidence_id,
            job.reused_result_artifact_id,
            job.failure_classification,
            job.failure_message,
        )

    def save_study(
        self,
        study: Study,
    ) -> Study:
        """Create one Study; exact duplicate creation is idempotent."""

        if not isinstance(study, Study):
            raise TypeError("study must be a Study")

        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO studies (
                            study_id,
                            created_at,
                            display_title,
                            archived
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            study.study_id,
                            study.created_at.isoformat(
                                timespec="microseconds"
                            ),
                            study.display_title,
                            int(study.archived),
                        ),
                    )
        except sqlite3.IntegrityError as error:
            existing = self.load_study(study.study_id)

            if (
                existing is not None
                and self._study_semantics(existing)
                == self._study_semantics(study)
            ):
                return existing

            raise ValueError(
                "Study identity already exists with different "
                "catalog metadata"
            ) from error

        return study

    def load_study(
        self,
        study_id: str,
    ) -> Study | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    study_id,
                    created_at,
                    display_title,
                    archived
                FROM studies
                WHERE study_id = ?
                """,
                (study_id,),
            ).fetchone()

        if row is None:
            return None

        return self._study_from_row(row)

    def update_study_metadata(
        self,
        study_id: str,
        *,
        display_title: str,
        archived: bool,
    ) -> Study:
        """Update display-only Study metadata without changing identity."""

        current = self.load_study(study_id)

        if current is None:
            raise ValueError(
                f"Study does not exist: {study_id}"
            )

        updated = Study(
            study_id=current.study_id,
            created_at=current.created_at,
            display_title=display_title,
            archived=archived,
        )

        with closing(self._connect()) as connection:
            with connection:
                cursor = connection.execute(
                    """
                    UPDATE studies
                    SET
                        display_title = ?,
                        archived = ?
                    WHERE study_id = ?
                    """,
                    (
                        updated.display_title,
                        int(updated.archived),
                        updated.study_id,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "Study metadata update lost its identity"
                    )

        return updated

    def save_study_revision(
        self,
        revision: StudyRevision,
    ) -> StudyRevision:
        """Persist one immutable registered plan record."""

        if not isinstance(revision, StudyRevision):
            raise TypeError(
                "revision must be a StudyRevision"
            )

        if revision.initial_batch_started_at is not None:
            raise ValueError(
                "new StudyRevision persistence cannot set "
                "initial_batch_started_at; Start owns that metadata"
            )

        plan_artifact = self.load_artifact(
            revision.plan_artifact_id
        )

        if (
            plan_artifact is None
            or plan_artifact.artifact_kind
            is not ResearchArtifactKind.STUDY_REVISION_PLAN
        ):
            raise ValueError(
                "StudyRevision requires a registered "
                "STUDY_REVISION_PLAN artifact"
            )

        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO study_revisions (
                            study_revision_id,
                            identity_schema,
                            study_id,
                            revision_number,
                            plan_artifact_id,
                            repository_revision,
                            evidence_reuse_policy,
                            registered_at,
                            initial_batch_started_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                        """,
                        (
                            revision.study_revision_id,
                            revision.identity_schema,
                            revision.study_id,
                            revision.revision_number,
                            revision.plan_artifact_id,
                            revision.repository_revision,
                            revision.evidence_reuse_policy.value,
                            revision.registered_at.isoformat(
                                timespec="microseconds"
                            ),
                        ),
                    )
        except sqlite3.IntegrityError as error:
            existing = self.load_study_revision(
                revision.study_revision_id
            )

            if (
                existing is not None
                and self._study_revision_semantics(existing)
                == self._study_revision_semantics(revision)
            ):
                return existing

            raise ValueError(
                "StudyRevision requires an existing Study, "
                "registered plan artifact, unique revision number "
                "and non-conflicting immutable identity"
            ) from error

        return revision

    def load_study_revision(
        self,
        study_revision_id: str,
    ) -> StudyRevision | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    study_revision_id,
                    identity_schema,
                    study_id,
                    revision_number,
                    plan_artifact_id,
                    repository_revision,
                    evidence_reuse_policy,
                    registered_at,
                    initial_batch_started_at
                FROM study_revisions
                WHERE study_revision_id = ?
                """,
                (study_revision_id,),
            ).fetchone()

        if row is None:
            return None

        return self._study_revision_from_row(row)

    def list_study_revisions(
        self,
        study_id: str,
    ) -> tuple[StudyRevision, ...]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    study_revision_id,
                    identity_schema,
                    study_id,
                    revision_number,
                    plan_artifact_id,
                    repository_revision,
                    evidence_reuse_policy,
                    registered_at,
                    initial_batch_started_at
                FROM study_revisions
                WHERE study_id = ?
                ORDER BY revision_number, study_revision_id
                """,
                (study_id,),
            ).fetchall()

        return tuple(
            self._study_revision_from_row(row)
            for row in rows
        )

    @staticmethod
    def _trial_identity_semantics(
        trial: Trial,
    ) -> tuple:
        """Return immutable registered Trial identity only."""

        return (
            trial.trial_id,
            trial.identity_schema,
            trial.study_revision_id,
            trial.instrument_id,
            trial.membership_episode_start,
            trial.membership_episode_end,
            trial.membership_evidence_fingerprint,
            trial.membership_evidence_artifact_id,
            trial.parameter_configuration_fingerprint,
        )

    def save_registered_revision_population(
        self,
        *,
        study_id: str,
        study_revision_id: str,
        plan_artifact_id: str,
        repository_revision: str,
        evidence_reuse_policy: EvidenceReusePolicy,
        registered_at: datetime,
        trials: tuple[Trial, ...],
        initial_events: tuple[TrialDispositionEvent, ...],
    ) -> tuple[StudyRevision, tuple[Trial, ...]]:
        """
        Atomically register one immutable StudyRevision population.

        M9.4b registration owns one BEGIN IMMEDIATE transaction covering
        the revision, every Trial and every initial disposition event.
        Artifact bytes/metadata may already exist content-addressably,
        but no partial Trial denominator becomes authoritative.
        """

        if (
            not isinstance(study_id, str)
            or not study_id
        ):
            raise ValueError(
                "study_id must be a non-empty string"
            )

        if (
            not isinstance(study_revision_id, str)
            or study_revision_id != plan_artifact_id
        ):
            raise ValueError(
                "study_revision_id must equal "
                "plan_artifact_id content identity"
            )

        if (
            not isinstance(repository_revision, str)
            or not repository_revision
        ):
            raise ValueError(
                "repository_revision must be a non-empty string"
            )

        if not isinstance(
            evidence_reuse_policy,
            EvidenceReusePolicy,
        ):
            raise TypeError(
                "evidence_reuse_policy must be an "
                "EvidenceReusePolicy"
            )

        if (
            not isinstance(registered_at, datetime)
            or registered_at.utcoffset() is None
        ):
            raise ValueError(
                "registered_at must be a timezone-aware datetime"
            )

        if not isinstance(trials, tuple):
            raise TypeError(
                "trials must be a complete tuple"
            )

        if not isinstance(initial_events, tuple):
            raise TypeError(
                "initial_events must be a complete tuple"
            )

        if len(trials) != len(initial_events):
            raise ValueError(
                "each registered Trial requires exactly one "
                "initial disposition event"
            )

        if len({trial.trial_id for trial in trials}) != len(trials):
            raise ValueError(
                "registered Trial population contains duplicate "
                "trial_id values"
            )

        events_by_trial = {}

        for event in initial_events:
            if not isinstance(
                event,
                TrialDispositionEvent,
            ):
                raise TypeError(
                    "initial_events must contain "
                    "TrialDispositionEvent values"
                )

            if event.trial_id in events_by_trial:
                raise ValueError(
                    "registered Trial population contains duplicate "
                    "initial events for one Trial"
                )

            events_by_trial[event.trial_id] = event

        for trial in trials:
            if not isinstance(trial, Trial):
                raise TypeError(
                    "trials must contain Trial values"
                )

            if trial.study_revision_id != study_revision_id:
                raise ValueError(
                    "every Trial must belong to the registered "
                    "StudyRevision"
                )

            if (
                trial.registered_at != registered_at
                or trial.disposition_at != registered_at
            ):
                raise ValueError(
                    "new Trial population must share the "
                    "StudyRevision registration timestamp"
                )

            if (
                trial.disposition
                is not TrialDisposition.PENDING
                or trial.experiment_spec_id is not None
                or trial.reused_attempt_id is not None
                or trial.failure_classification is not None
                or trial.failure_message is not None
            ):
                raise ValueError(
                    "new registered Trial population must begin "
                    "as unbound PENDING"
                )

            event = events_by_trial.get(
                trial.trial_id
            )

            if event is None:
                raise ValueError(
                    "every Trial requires its matching "
                    "initial disposition event"
                )

            if (
                event.sequence_number != 1
                or event.previous_disposition is not None
                or event.new_disposition
                is not TrialDisposition.PENDING
                or event.causing_job_id is not None
                or event.occurred_at != registered_at
            ):
                raise ValueError(
                    "initial Trial event must be sequence 1, "
                    "None -> PENDING, job-independent and share "
                    "the registration timestamp"
                )

        ordered_trials = tuple(
            sorted(
                trials,
                key=lambda trial: (
                    trial.membership_episode_start,
                    trial.membership_episode_end,
                    trial.instrument_id,
                    trial.membership_evidence_fingerprint,
                    trial.parameter_configuration_fingerprint,
                    trial.trial_id,
                ),
            )
        )

        proposed_identity = tuple(
            self._trial_identity_semantics(trial)
            for trial in ordered_trials
        )

        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                study_row = connection.execute(
                    """
                    SELECT study_id
                    FROM studies
                    WHERE study_id = ?
                    """,
                    (study_id,),
                ).fetchone()

                if study_row is None:
                    raise ValueError(
                        "registered StudyRevision requires "
                        "an existing Study"
                    )

                plan_row = connection.execute(
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
                    (plan_artifact_id,),
                ).fetchone()

                if plan_row is None:
                    raise ValueError(
                        "registered StudyRevision requires "
                        "its plan artifact"
                    )

                plan_artifact = self._artifact_from_row(
                    plan_row
                )

                if (
                    plan_artifact.artifact_kind
                    is not ResearchArtifactKind.STUDY_REVISION_PLAN
                    or plan_artifact.schema_id
                    != STUDY_REVISION_SCHEMA_ID
                ):
                    raise ValueError(
                        "StudyRevision plan artifact kind/schema "
                        "does not match the registered contract"
                    )

                existing_row = connection.execute(
                    """
                    SELECT
                        study_revision_id,
                        identity_schema,
                        study_id,
                        revision_number,
                        plan_artifact_id,
                        repository_revision,
                        evidence_reuse_policy,
                        registered_at,
                        initial_batch_started_at
                    FROM study_revisions
                    WHERE study_revision_id = ?
                    """,
                    (study_revision_id,),
                ).fetchone()

                if existing_row is not None:
                    existing_revision = (
                        self._study_revision_from_row(
                            existing_row
                        )
                    )

                    if (
                        existing_revision.study_id != study_id
                        or existing_revision.plan_artifact_id
                        != plan_artifact_id
                        or existing_revision.repository_revision
                        != repository_revision
                        or existing_revision.evidence_reuse_policy
                        is not evidence_reuse_policy
                    ):
                        raise ValueError(
                            "StudyRevision content identity already "
                            "exists with conflicting immutable semantics"
                        )

                    existing_trial_rows = connection.execute(
                        """
                        SELECT
                            trial_id,
                            identity_schema,
                            study_revision_id,
                            instrument_id,
                            membership_episode_start,
                            membership_episode_end,
                            membership_evidence_fingerprint,
                            membership_evidence_artifact_id,
                            parameter_configuration_fingerprint,
                            registered_at,
                            experiment_spec_id,
                            disposition,
                            disposition_at,
                            reused_attempt_id,
                            failure_classification,
                            failure_message
                        FROM trials
                        WHERE study_revision_id = ?
                        ORDER BY
                            membership_episode_start,
                            membership_episode_end,
                            instrument_id,
                            membership_evidence_fingerprint,
                            parameter_configuration_fingerprint,
                            trial_id
                        """,
                        (study_revision_id,),
                    ).fetchall()

                    existing_trials = tuple(
                        sorted(
                            (
                                self._trial_from_row(row)
                                for row in existing_trial_rows
                            ),
                            key=lambda trial: (
                                trial.membership_episode_start,
                                trial.membership_episode_end,
                                trial.instrument_id,
                                trial.membership_evidence_fingerprint,
                                trial.parameter_configuration_fingerprint,
                                trial.trial_id,
                            ),
                        )
                    )

                    existing_identity = tuple(
                        self._trial_identity_semantics(
                            trial
                        )
                        for trial in existing_trials
                    )

                    if existing_identity != proposed_identity:
                        raise ValueError(
                            "identical StudyRevision registration "
                            "must preserve the exact Trial population"
                        )

                    connection.rollback()

                    return (
                        existing_revision,
                        existing_trials,
                    )

                for trial in ordered_trials:
                    artifact_row = connection.execute(
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
                        (
                            trial.membership_evidence_artifact_id,
                        ),
                    ).fetchone()

                    if artifact_row is None:
                        raise ValueError(
                            "registered Trial population requires "
                            "all membership evidence artifacts"
                        )

                    artifact = self._artifact_from_row(
                        artifact_row
                    )

                    if (
                        artifact.artifact_kind
                        is not
                        ResearchArtifactKind.TRIAL_MEMBERSHIP_EVIDENCE
                        or artifact.schema_id
                        != TRIAL_MEMBERSHIP_EVIDENCE_SCHEMA_ID
                        or artifact.artifact_id
                        != trial.membership_evidence_fingerprint
                    ):
                        raise ValueError(
                            "Trial membership evidence artifact "
                            "kind/schema/identity mismatch"
                        )

                next_revision_number = (
                    connection.execute(
                        """
                        SELECT COALESCE(MAX(revision_number), 0) + 1
                        FROM study_revisions
                        WHERE study_id = ?
                        """,
                        (study_id,),
                    ).fetchone()[0]
                )

                revision = StudyRevision(
                    study_revision_id=study_revision_id,
                    study_id=study_id,
                    revision_number=next_revision_number,
                    plan_artifact_id=plan_artifact_id,
                    repository_revision=repository_revision,
                    evidence_reuse_policy=evidence_reuse_policy,
                    registered_at=registered_at,
                )

                connection.execute(
                    """
                    INSERT INTO study_revisions (
                        study_revision_id,
                        identity_schema,
                        study_id,
                        revision_number,
                        plan_artifact_id,
                        repository_revision,
                        evidence_reuse_policy,
                        registered_at,
                        initial_batch_started_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        revision.study_revision_id,
                        revision.identity_schema,
                        revision.study_id,
                        revision.revision_number,
                        revision.plan_artifact_id,
                        revision.repository_revision,
                        revision.evidence_reuse_policy.value,
                        revision.registered_at.isoformat(
                            timespec="microseconds"
                        ),
                    ),
                )

                for trial in ordered_trials:
                    event = events_by_trial[
                        trial.trial_id
                    ]

                    connection.execute(
                        """
                        INSERT INTO trials (
                            trial_id,
                            identity_schema,
                            study_revision_id,
                            instrument_id,
                            membership_episode_start,
                            membership_episode_end,
                            membership_evidence_fingerprint,
                            membership_evidence_artifact_id,
                            parameter_configuration_fingerprint,
                            registered_at,
                            experiment_spec_id,
                            disposition,
                            disposition_at,
                            reused_attempt_id,
                            failure_classification,
                            failure_message
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                            NULL, ?, ?, NULL, NULL, NULL
                        )
                        """,
                        (
                            trial.trial_id,
                            trial.identity_schema,
                            trial.study_revision_id,
                            trial.instrument_id,
                            trial.membership_episode_start.isoformat(
                                timespec="microseconds"
                            ),
                            trial.membership_episode_end.isoformat(
                                timespec="microseconds"
                            ),
                            trial.membership_evidence_fingerprint,
                            trial.membership_evidence_artifact_id,
                            trial.parameter_configuration_fingerprint,
                            trial.registered_at.isoformat(
                                timespec="microseconds"
                            ),
                            trial.disposition.value,
                            trial.disposition_at.isoformat(
                                timespec="microseconds"
                            ),
                        ),
                    )

                    connection.execute(
                        """
                        INSERT INTO trial_disposition_events (
                            event_id,
                            trial_id,
                            sequence_number,
                            previous_disposition,
                            new_disposition,
                            occurred_at,
                            causing_job_id,
                            reason_classification,
                            reason_message
                        ) VALUES (
                            ?, ?, ?, NULL, ?, ?, NULL, ?, ?
                        )
                        """,
                        (
                            event.event_id,
                            event.trial_id,
                            event.sequence_number,
                            event.new_disposition.value,
                            event.occurred_at.isoformat(
                                timespec="microseconds"
                            ),
                            event.reason_classification,
                            event.reason_message,
                        ),
                    )

                connection.commit()

            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise ValueError(
                    "whole StudyRevision registration failed; "
                    "no partial Trial population was committed"
                ) from error
            except Exception:
                connection.rollback()
                raise

        return revision, ordered_trials

    def save_registered_trial(
        self,
        trial: Trial,
        initial_event: TrialDispositionEvent,
    ) -> Trial:
        """
        Reject supported single-Trial registration bypasses.

        Whole-population registration is the sole authority for the
        immutable initial Trial denominator.
        """
        raise ValueError(
            "single-Trial persistence is unsupported; "
            "use whole-population StudyRevision registration"
        )

    def _save_registered_trial(
        self,
        trial: Trial,
        initial_event: TrialDispositionEvent,
    ) -> Trial:
        """
        Legacy storage primitive retained only for internal/test
        persistence verification. It is not a supported lifecycle API.
        """

        if not isinstance(trial, Trial):
            raise TypeError("trial must be a Trial")

        if not isinstance(
            initial_event,
            TrialDispositionEvent,
        ):
            raise TypeError(
                "initial_event must be a TrialDispositionEvent"
            )

        if (
            trial.disposition is not TrialDisposition.PENDING
            or trial.experiment_spec_id is not None
            or trial.reused_attempt_id is not None
            or trial.failure_classification is not None
            or trial.failure_message is not None
        ):
            raise ValueError(
                "new registered Trial must begin as unbound PENDING"
            )

        if (
            initial_event.trial_id != trial.trial_id
            or initial_event.sequence_number != 1
            or initial_event.previous_disposition is not None
            or initial_event.new_disposition
            is not TrialDisposition.PENDING
            or initial_event.causing_job_id is not None
            or initial_event.occurred_at != trial.disposition_at
        ):
            raise ValueError(
                "initial Trial event must be sequence 1, "
                "None -> PENDING, job-independent and match "
                "the Trial disposition timestamp"
            )

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                artifact_row = connection.execute(
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
                    (
                        trial.membership_evidence_artifact_id,
                    ),
                ).fetchone()

                if artifact_row is None:
                    raise ValueError(
                        "registered Trial requires a registered "
                        "TRIAL_MEMBERSHIP_EVIDENCE artifact"
                    )

                membership_artifact = (
                    self._artifact_from_row(artifact_row)
                )

                if (
                    membership_artifact.artifact_kind
                    is not
                    ResearchArtifactKind.TRIAL_MEMBERSHIP_EVIDENCE
                ):
                    raise ValueError(
                        "registered Trial requires a registered "
                        "TRIAL_MEMBERSHIP_EVIDENCE artifact"
                    )

                if (
                    membership_artifact.artifact_id
                    != trial.membership_evidence_fingerprint
                ):
                    raise ValueError(
                        "Trial membership evidence artifact identity "
                        "must match membership_evidence_fingerprint"
                    )

                connection.execute(
                    """
                    INSERT INTO trials (
                        trial_id,
                        identity_schema,
                        study_revision_id,
                        instrument_id,
                        membership_episode_start,
                        membership_episode_end,
                        membership_evidence_fingerprint,
                        membership_evidence_artifact_id,
                        parameter_configuration_fingerprint,
                        registered_at,
                        experiment_spec_id,
                        disposition,
                        disposition_at,
                        reused_attempt_id,
                        failure_classification,
                        failure_message
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        NULL, ?, ?, NULL, NULL, NULL
                    )
                    """,
                    (
                        trial.trial_id,
                        trial.identity_schema,
                        trial.study_revision_id,
                        trial.instrument_id,
                        trial.membership_episode_start.isoformat(
                            timespec="microseconds"
                        ),
                        trial.membership_episode_end.isoformat(
                            timespec="microseconds"
                        ),
                        trial.membership_evidence_fingerprint,
                        trial.membership_evidence_artifact_id,
                        trial.parameter_configuration_fingerprint,
                        trial.registered_at.isoformat(
                            timespec="microseconds"
                        ),
                        trial.disposition.value,
                        trial.disposition_at.isoformat(
                            timespec="microseconds"
                        ),
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO trial_disposition_events (
                        event_id,
                        trial_id,
                        sequence_number,
                        previous_disposition,
                        new_disposition,
                        occurred_at,
                        causing_job_id,
                        reason_classification,
                        reason_message
                    ) VALUES (?, ?, ?, NULL, ?, ?, NULL, ?, ?)
                    """,
                    (
                        initial_event.event_id,
                        initial_event.trial_id,
                        initial_event.sequence_number,
                        initial_event.new_disposition.value,
                        initial_event.occurred_at.isoformat(
                            timespec="microseconds"
                        ),
                        initial_event.reason_classification,
                        initial_event.reason_message,
                    ),
                )

                connection.commit()

            except sqlite3.IntegrityError as error:
                connection.rollback()

                existing = self.load_trial(
                    trial.trial_id
                )
                events = self.load_trial_disposition_events(
                    trial.trial_id
                )

                if (
                    existing is not None
                    and len(events) == 1
                    and self._trial_registration_semantics(
                        existing
                    )
                    == self._trial_registration_semantics(
                        trial
                    )
                    and self._trial_event_semantics(events[0])
                    == self._trial_event_semantics(
                        initial_event
                    )
                ):
                    return existing

                raise ValueError(
                    "registered Trial persistence requires "
                    "an existing StudyRevision and unique, "
                    "non-conflicting Trial/event identity"
                ) from error

            except Exception:
                connection.rollback()
                raise

        return trial

    def load_trial(
        self,
        trial_id: str,
    ) -> Trial | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    trial_id,
                    identity_schema,
                    study_revision_id,
                    instrument_id,
                    membership_episode_start,
                    membership_episode_end,
                    membership_evidence_fingerprint,
                    membership_evidence_artifact_id,
                    parameter_configuration_fingerprint,
                    registered_at,
                    experiment_spec_id,
                    disposition,
                    disposition_at,
                    reused_attempt_id,
                    failure_classification,
                    failure_message
                FROM trials
                WHERE trial_id = ?
                """,
                (trial_id,),
            ).fetchone()

        if row is None:
            return None

        return self._trial_from_row(row)

    def list_trials_for_revision(
        self,
        study_revision_id: str,
    ) -> tuple[Trial, ...]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    trial_id,
                    identity_schema,
                    study_revision_id,
                    instrument_id,
                    membership_episode_start,
                    membership_episode_end,
                    membership_evidence_fingerprint,
                    membership_evidence_artifact_id,
                    parameter_configuration_fingerprint,
                    registered_at,
                    experiment_spec_id,
                    disposition,
                    disposition_at,
                    reused_attempt_id,
                    failure_classification,
                    failure_message
                FROM trials
                WHERE study_revision_id = ?
                ORDER BY
                    instrument_id,
                    membership_episode_start,
                    membership_episode_end,
                    trial_id
                """,
                (study_revision_id,),
            ).fetchall()

        return tuple(
            self._trial_from_row(row)
            for row in rows
        )

    def load_trial_disposition_events(
        self,
        trial_id: str,
    ) -> tuple[TrialDispositionEvent, ...]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    event_id,
                    trial_id,
                    sequence_number,
                    previous_disposition,
                    new_disposition,
                    occurred_at,
                    causing_job_id,
                    reason_classification,
                    reason_message
                FROM trial_disposition_events
                WHERE trial_id = ?
                ORDER BY sequence_number, event_id
                """,
                (trial_id,),
            ).fetchall()

        return tuple(
            self._trial_event_from_row(row)
            for row in rows
        )

    def start_study_revision_batch(
        self,
        study_revision_id: str,
        started_at: datetime,
    ) -> StudyRevision:
        """Atomically create one deterministic initial job per Trial."""

        if (
            not isinstance(study_revision_id, str)
            or not study_revision_id
        ):
            raise ValueError(
                "study_revision_id must be a non-empty string"
            )

        if (
            not isinstance(started_at, datetime)
            or started_at.utcoffset() is None
        ):
            raise ValueError(
                "started_at must be a timezone-aware datetime"
            )

        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                revision_row = connection.execute(
                    """
                    SELECT
                        study_revision_id,
                        identity_schema,
                        study_id,
                        revision_number,
                        plan_artifact_id,
                        repository_revision,
                        evidence_reuse_policy,
                        registered_at,
                        initial_batch_started_at
                    FROM study_revisions
                    WHERE study_revision_id = ?
                    """,
                    (study_revision_id,),
                ).fetchone()

                if revision_row is None:
                    raise ValueError(
                        "StudyRevision does not exist"
                    )

                revision = (
                    self._study_revision_from_row(
                        revision_row
                    )
                )

                if started_at < revision.registered_at:
                    raise ValueError(
                        "started_at cannot precede registered_at"
                    )

                trial_rows = connection.execute(
                    """
                    SELECT
                        trial_id,
                        disposition
                    FROM trials
                    WHERE study_revision_id = ?
                    ORDER BY trial_id
                    """,
                    (study_revision_id,),
                ).fetchall()

                expected_initial_jobs = tuple(
                    (
                        _initial_research_job_id(
                            trial_id
                        ),
                        trial_id,
                    )
                    for trial_id, _
                    in trial_rows
                )

                existing_job_rows = connection.execute(
                    """
                    SELECT
                        j.job_id,
                        j.trial_id,
                        j.created_at
                    FROM research_jobs j
                    JOIN trials t
                        ON t.trial_id = j.trial_id
                    WHERE t.study_revision_id = ?
                    """,
                    (study_revision_id,),
                ).fetchall()

                if (
                    revision.initial_batch_started_at
                    is not None
                ):
                    existing_by_id = {
                        row[0]: row
                        for row in existing_job_rows
                    }

                    for (
                        job_id,
                        trial_id,
                    ) in expected_initial_jobs:
                        row = existing_by_id.get(
                            job_id
                        )

                        if row is None:
                            raise ValueError(
                                "started StudyRevision is missing "
                                "deterministic initial-job lineage"
                            )

                        if row[1] != trial_id:
                            raise ValueError(
                                "deterministic initial ResearchJob "
                                "points to the wrong Trial"
                            )

                        if (
                            datetime.fromisoformat(
                                row[2]
                            )
                            != revision.initial_batch_started_at
                        ):
                            raise ValueError(
                                "deterministic initial ResearchJob "
                                "creation time does not match "
                                "initial_batch_started_at"
                            )

                    connection.rollback()
                    return revision

                if existing_job_rows:
                    raise ValueError(
                        "unstarted StudyRevision already has "
                        "ResearchJob history"
                    )

                for (
                    _trial_id,
                    disposition,
                ) in trial_rows:
                    if (
                        disposition
                        != TrialDisposition.PENDING.value
                    ):
                        raise ValueError(
                            "first Start requires every "
                            "registered Trial to remain PENDING"
                        )

                created_at = started_at.isoformat(
                    timespec="microseconds"
                )

                for (
                    job_id,
                    trial_id,
                ) in expected_initial_jobs:
                    connection.execute(
                        """
                        INSERT INTO research_jobs (
                            job_id,
                            trial_id,
                            state,
                            created_at,
                            claimed_at,
                            terminal_at,
                            worker_id,
                            cancel_requested_at,
                            attempt_id,
                            completion_kind,
                            reused_attempt_id,
                            reused_evidence_id,
                            reused_result_artifact_id,
                            failure_classification,
                            failure_message
                        ) VALUES (
                            ?, ?, 'QUEUED', ?,
                            NULL, NULL, NULL, NULL, NULL,
                            NULL, NULL, NULL, NULL, NULL, NULL
                        )
                        """,
                        (
                            job_id,
                            trial_id,
                            created_at,
                        ),
                    )

                cursor = connection.execute(
                    """
                    UPDATE study_revisions
                    SET initial_batch_started_at = ?
                    WHERE
                        study_revision_id = ?
                        AND initial_batch_started_at IS NULL
                    """,
                    (
                        created_at,
                        study_revision_id,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "StudyRevision Start lost its "
                        "unstarted precondition"
                    )

                updated_row = connection.execute(
                    """
                    SELECT
                        study_revision_id,
                        identity_schema,
                        study_id,
                        revision_number,
                        plan_artifact_id,
                        repository_revision,
                        evidence_reuse_policy,
                        registered_at,
                        initial_batch_started_at
                    FROM study_revisions
                    WHERE study_revision_id = ?
                    """,
                    (study_revision_id,),
                ).fetchone()

                if updated_row is None:
                    raise RuntimeError(
                        "started StudyRevision disappeared"
                    )

                started_revision = (
                    self._study_revision_from_row(
                        updated_row
                    )
                )

                connection.commit()

            except sqlite3.IntegrityError as error:
                connection.rollback()

                raise ValueError(
                    "initial ResearchJob queue could not be "
                    "persisted atomically"
                ) from error

            except Exception:
                connection.rollback()
                raise

        return started_revision

    def load_research_queue_snapshot(
        self,
        study_revision_id: str,
    ) -> ResearchQueueSnapshot:
        """Read durable Trial and ResearchJob state counts."""

        if (
            not isinstance(study_revision_id, str)
            or not study_revision_id
        ):
            raise ValueError(
                "study_revision_id must be a non-empty string"
            )

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN")

                revision_row = connection.execute(
                    """
                    SELECT initial_batch_started_at
                    FROM study_revisions
                    WHERE study_revision_id = ?
                    """,
                    (study_revision_id,),
                ).fetchone()

                if revision_row is None:
                    raise ValueError(
                        "StudyRevision does not exist"
                    )

                trial_counts = dict(
                    connection.execute(
                        """
                        SELECT
                            disposition,
                            COUNT(*)
                        FROM trials
                        WHERE study_revision_id = ?
                        GROUP BY disposition
                        """,
                        (study_revision_id,),
                    ).fetchall()
                )

                job_counts = dict(
                    connection.execute(
                        """
                        SELECT
                            j.state,
                            COUNT(*)
                        FROM research_jobs j
                        JOIN trials t
                            ON t.trial_id = j.trial_id
                        WHERE t.study_revision_id = ?
                        GROUP BY j.state
                        """,
                        (study_revision_id,),
                    ).fetchall()
                )

                snapshot = ResearchQueueSnapshot(
                    study_revision_id=(
                        study_revision_id
                    ),
                    initial_batch_started_at=(
                        datetime.fromisoformat(
                            revision_row[0]
                        )
                        if revision_row[0] is not None
                        else None
                    ),
                    total_registered_trials=sum(
                        trial_counts.values()
                    ),
                    pending_trials=trial_counts.get(
                        TrialDisposition.PENDING.value,
                        0,
                    ),
                    executed_trials=trial_counts.get(
                        TrialDisposition.EXECUTED.value,
                        0,
                    ),
                    reused_trials=trial_counts.get(
                        TrialDisposition.REUSED.value,
                        0,
                    ),
                    invalid_trials=trial_counts.get(
                        TrialDisposition.INVALID.value,
                        0,
                    ),
                    insufficient_trials=trial_counts.get(
                        TrialDisposition.INSUFFICIENT.value,
                        0,
                    ),
                    failed_trials=trial_counts.get(
                        TrialDisposition.FAILED.value,
                        0,
                    ),
                    cancelled_trials=trial_counts.get(
                        TrialDisposition.CANCELLED.value,
                        0,
                    ),
                    interrupted_trials=trial_counts.get(
                        TrialDisposition.INTERRUPTED.value,
                        0,
                    ),
                    queued_jobs=job_counts.get(
                        ResearchJobState.QUEUED.value,
                        0,
                    ),
                    running_jobs=job_counts.get(
                        ResearchJobState.RUNNING.value,
                        0,
                    ),
                    succeeded_jobs=job_counts.get(
                        ResearchJobState.SUCCEEDED.value,
                        0,
                    ),
                    failed_jobs=job_counts.get(
                        ResearchJobState.FAILED.value,
                        0,
                    ),
                    cancelled_jobs=job_counts.get(
                        ResearchJobState.CANCELLED.value,
                        0,
                    ),
                    interrupted_jobs=job_counts.get(
                        ResearchJobState.INTERRUPTED.value,
                        0,
                    ),
                )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

        return snapshot

    def claim_next_research_job(
        self,
        study_revision_id: str,
        worker_id: str,
        claimed_at: datetime,
        *,
        max_running_jobs: int,
    ) -> ResearchJob | None:
        """Atomically claim the next FIFO job under the global bound."""

        if (
            not isinstance(study_revision_id, str)
            or not study_revision_id
        ):
            raise ValueError(
                "study_revision_id must be a non-empty string"
            )

        if (
            not isinstance(worker_id, str)
            or not worker_id
        ):
            raise ValueError(
                "worker_id must be a non-empty string"
            )

        if (
            not isinstance(claimed_at, datetime)
            or claimed_at.utcoffset() is None
        ):
            raise ValueError(
                "claimed_at must be a timezone-aware datetime"
            )

        if (
            type(max_running_jobs) is not int
            or max_running_jobs <= 0
            or max_running_jobs
            > RESEARCH_MAX_WORKERS_SAFETY_CEILING
        ):
            raise ValueError(
                "max_running_jobs must be between 1 and "
                f"{RESEARCH_MAX_WORKERS_SAFETY_CEILING}"
            )

        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                revision_row = connection.execute(
                    """
                    SELECT initial_batch_started_at
                    FROM study_revisions
                    WHERE study_revision_id = ?
                    """,
                    (study_revision_id,),
                ).fetchone()

                if revision_row is None:
                    raise ValueError(
                        "StudyRevision does not exist"
                    )

                if revision_row[0] is None:
                    raise ValueError(
                        "StudyRevision must be started before "
                        "ResearchJobs can be claimed"
                    )

                running_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM research_jobs
                    WHERE state = ?
                    """,
                    (
                        ResearchJobState.RUNNING.value,
                    ),
                ).fetchone()[0]

                if running_count >= max_running_jobs:
                    connection.rollback()
                    return None

                row = connection.execute(
                    """
                    SELECT
                        j.job_id,
                        j.trial_id,
                        j.state,
                        j.created_at,
                        j.claimed_at,
                        j.terminal_at,
                        j.worker_id,
                        j.cancel_requested_at,
                        j.attempt_id,
                        j.completion_kind,
                        j.reused_attempt_id,
                        j.reused_evidence_id,
                        j.reused_result_artifact_id,
                        j.failure_classification,
                        j.failure_message
                    FROM research_jobs j
                    JOIN trials t
                        ON t.trial_id = j.trial_id
                    WHERE
                        t.study_revision_id = ?
                        AND j.state = ?
                    ORDER BY
                        j.created_at ASC,
                        j.job_id ASC
                    LIMIT 1
                    """,
                    (
                        study_revision_id,
                        ResearchJobState.QUEUED.value,
                    ),
                ).fetchone()

                if row is None:
                    connection.rollback()
                    return None

                created_at = datetime.fromisoformat(
                    row[3]
                )

                if claimed_at < created_at:
                    raise ValueError(
                        "claimed_at cannot precede "
                        "ResearchJob created_at"
                    )

                job_id = row[0]

                cursor = connection.execute(
                    """
                    UPDATE research_jobs
                    SET
                        state = ?,
                        claimed_at = ?,
                        worker_id = ?
                    WHERE
                        job_id = ?
                        AND state = ?
                    """,
                    (
                        ResearchJobState.RUNNING.value,
                        claimed_at.isoformat(
                            timespec="microseconds"
                        ),
                        worker_id,
                        job_id,
                        ResearchJobState.QUEUED.value,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "ResearchJob claim lost its "
                        "QUEUED precondition"
                    )

                claimed_row = connection.execute(
                    """
                    SELECT
                        job_id,
                        trial_id,
                        state,
                        created_at,
                        claimed_at,
                        terminal_at,
                        worker_id,
                        cancel_requested_at,
                        attempt_id,
                        completion_kind,
                        reused_attempt_id,
                        reused_evidence_id,
                        reused_result_artifact_id,
                        failure_classification,
                        failure_message
                    FROM research_jobs
                    WHERE job_id = ?
                    """,
                    (job_id,),
                ).fetchone()

                if claimed_row is None:
                    raise RuntimeError(
                        "claimed ResearchJob disappeared"
                    )

                claimed_job = (
                    self._research_job_from_row(
                        claimed_row
                    )
                )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

        return claimed_job

    # M9.4d2 BEHAVIOR IMPACT: ADDED
    # PRIMARY BEHAVIOR IDS:
    # - RESEARCH-RULE-014
    # - RESEARCH-RULE-015
    #
    # This fresh-execution primitive binds an already-registered Trial
    # to its exact ExperimentSpec, creates one new RUNNING RunAttempt,
    # and links the already-RUNNING ResearchJob to that attempt in one
    # SQLite transaction. It performs no financial execution or
    # terminalization.
    def bind_trial_spec_create_attempt_for_running_job(
        self,
        *,
        job_id: str,
        experiment_spec_id: str,
        attempt_created_at: datetime,
    ) -> tuple[Trial, ResearchJob, RunAttempt]:
        """
        Atomically establish fresh-execution identities for one job.

        A Trial may acquire its ExperimentSpec binding once. A later
        job for the same Trial must preserve that exact binding. One
        ResearchJob may link to at most one newly created RunAttempt.
        """

        if (
            not isinstance(job_id, str)
            or not job_id
        ):
            raise ValueError(
                "job_id must be a non-empty string"
            )

        if (
            not isinstance(experiment_spec_id, str)
            or not experiment_spec_id
        ):
            raise ValueError(
                "experiment_spec_id must be a non-empty string"
            )

        if (
            not isinstance(attempt_created_at, datetime)
            or attempt_created_at.utcoffset() is None
        ):
            raise ValueError(
                "attempt_created_at must be a timezone-aware datetime"
            )

        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                job_row = connection.execute(
                    """
                    SELECT
                        job_id,
                        trial_id,
                        state,
                        created_at,
                        claimed_at,
                        terminal_at,
                        worker_id,
                        cancel_requested_at,
                        attempt_id,
                        completion_kind,
                        reused_attempt_id,
                        reused_evidence_id,
                        reused_result_artifact_id,
                        failure_classification,
                        failure_message
                    FROM research_jobs
                    WHERE job_id = ?
                    """,
                    (job_id,),
                ).fetchone()

                if job_row is None:
                    raise ValueError(
                        f"ResearchJob does not exist: {job_id}"
                    )

                current_job = (
                    self._research_job_from_row(
                        job_row
                    )
                )

                if (
                    current_job.state
                    is not ResearchJobState.RUNNING
                ):
                    raise ValueError(
                        "ResearchJob must be RUNNING before "
                        "fresh execution can create a RunAttempt"
                    )

                if (
                    current_job.cancel_requested_at
                    is not None
                ):
                    raise ValueError(
                        "ResearchJob cancellation request "
                        "blocks fresh RunAttempt creation"
                    )

                if (
                    current_job.claimed_at is not None
                    and attempt_created_at
                    < current_job.claimed_at
                ):
                    raise ValueError(
                        "attempt_created_at cannot precede "
                        "ResearchJob claimed_at"
                    )

                if current_job.attempt_id is not None:
                    raise ValueError(
                        "one ResearchJob may create at most "
                        "one new RunAttempt"
                    )

                if any(
                    value is not None
                    for value in (
                        current_job.terminal_at,
                        current_job.completion_kind,
                        current_job.reused_attempt_id,
                        current_job.reused_evidence_id,
                        current_job.reused_result_artifact_id,
                        current_job.failure_classification,
                        current_job.failure_message,
                    )
                ):
                    raise ValueError(
                        "RUNNING ResearchJob must not carry "
                        "terminal or completion fields before "
                        "fresh execution"
                    )

                trial_row = connection.execute(
                    """
                    SELECT
                        trial_id,
                        identity_schema,
                        study_revision_id,
                        instrument_id,
                        membership_episode_start,
                        membership_episode_end,
                        membership_evidence_fingerprint,
                        membership_evidence_artifact_id,
                        parameter_configuration_fingerprint,
                        registered_at,
                        experiment_spec_id,
                        disposition,
                        disposition_at,
                        reused_attempt_id,
                        failure_classification,
                        failure_message
                    FROM trials
                    WHERE trial_id = ?
                    """,
                    (
                        current_job.trial_id,
                    ),
                ).fetchone()

                if trial_row is None:
                    raise ValueError(
                        "ResearchJob Trial does not exist"
                    )

                current_trial = (
                    self._trial_from_row(
                        trial_row
                    )
                )

                if (
                    current_trial.disposition
                    is not TrialDisposition.PENDING
                ):
                    raise ValueError(
                        "Trial must be PENDING before "
                        "fresh execution can create a RunAttempt"
                    )

                spec_row = connection.execute(
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
                    (
                        experiment_spec_id,
                    ),
                ).fetchone()

                if spec_row is None:
                    raise ValueError(
                        "ExperimentSpec does not exist: "
                        f"{experiment_spec_id}"
                    )

                spec = self._spec_from_row(
                    spec_row
                )

                if (
                    current_trial.experiment_spec_id
                    is not None
                    and current_trial.experiment_spec_id
                    != spec.experiment_spec_id
                ):
                    raise ValueError(
                        "Trial is already bound to a different "
                        "ExperimentSpec"
                    )

                if (
                    current_trial.experiment_spec_id
                    is None
                ):
                    cursor = connection.execute(
                        """
                        UPDATE trials
                        SET experiment_spec_id = ?
                        WHERE
                            trial_id = ?
                            AND disposition = ?
                            AND experiment_spec_id IS NULL
                        """,
                        (
                            spec.experiment_spec_id,
                            current_trial.trial_id,
                            TrialDisposition.PENDING.value,
                        ),
                    )

                    if cursor.rowcount != 1:
                        raise RuntimeError(
                            "Trial binding lost its PENDING/unbound "
                            "precondition"
                        )

                attempt = RunAttempt(
                    attempt_id=(
                        self._attempt_id_factory()
                    ),
                    experiment_spec_id=(
                        spec.experiment_spec_id
                    ),
                    state=RunAttemptState.RUNNING,
                    created_at=attempt_created_at,
                )

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
                    ) VALUES (
                        ?, ?, ?, ?,
                        NULL, NULL, NULL, NULL, NULL, NULL
                    )
                    """,
                    (
                        attempt.attempt_id,
                        attempt.experiment_spec_id,
                        attempt.state.value,
                        attempt.created_at.isoformat(
                            timespec="microseconds"
                        ),
                    ),
                )

                cursor = connection.execute(
                    """
                    UPDATE research_jobs
                    SET attempt_id = ?
                    WHERE
                        job_id = ?
                        AND state = ?
                        AND cancel_requested_at IS NULL
                        AND attempt_id IS NULL
                        AND terminal_at IS NULL
                        AND completion_kind IS NULL
                        AND reused_attempt_id IS NULL
                        AND reused_evidence_id IS NULL
                        AND reused_result_artifact_id IS NULL
                        AND failure_classification IS NULL
                        AND failure_message IS NULL
                    """,
                    (
                        attempt.attempt_id,
                        current_job.job_id,
                        ResearchJobState.RUNNING.value,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "ResearchJob attempt link lost its "
                        "RUNNING/unlinked precondition"
                    )

                updated_trial_row = connection.execute(
                    """
                    SELECT
                        trial_id,
                        identity_schema,
                        study_revision_id,
                        instrument_id,
                        membership_episode_start,
                        membership_episode_end,
                        membership_evidence_fingerprint,
                        membership_evidence_artifact_id,
                        parameter_configuration_fingerprint,
                        registered_at,
                        experiment_spec_id,
                        disposition,
                        disposition_at,
                        reused_attempt_id,
                        failure_classification,
                        failure_message
                    FROM trials
                    WHERE trial_id = ?
                    """,
                    (
                        current_trial.trial_id,
                    ),
                ).fetchone()

                updated_job_row = connection.execute(
                    """
                    SELECT
                        job_id,
                        trial_id,
                        state,
                        created_at,
                        claimed_at,
                        terminal_at,
                        worker_id,
                        cancel_requested_at,
                        attempt_id,
                        completion_kind,
                        reused_attempt_id,
                        reused_evidence_id,
                        reused_result_artifact_id,
                        failure_classification,
                        failure_message
                    FROM research_jobs
                    WHERE job_id = ?
                    """,
                    (
                        current_job.job_id,
                    ),
                ).fetchone()

                attempt_row = connection.execute(
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
                    (
                        attempt.attempt_id,
                    ),
                ).fetchone()

                if (
                    updated_trial_row is None
                    or updated_job_row is None
                    or attempt_row is None
                ):
                    raise RuntimeError(
                        "atomic execution identities disappeared "
                        "before commit"
                    )

                updated_trial = (
                    self._trial_from_row(
                        updated_trial_row
                    )
                )

                updated_job = (
                    self._research_job_from_row(
                        updated_job_row
                    )
                )

                persisted_attempt = (
                    self._attempt_from_row(
                        attempt_row
                    )
                )

                if (
                    updated_trial.experiment_spec_id
                    != spec.experiment_spec_id
                    or updated_job.attempt_id
                    != persisted_attempt.attempt_id
                    or persisted_attempt.experiment_spec_id
                    != spec.experiment_spec_id
                    or persisted_attempt.state
                    is not RunAttemptState.RUNNING
                ):
                    raise RuntimeError(
                        "atomic execution identity linkage "
                        "is internally inconsistent"
                    )

                connection.commit()

            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise ValueError(
                    "atomic Trial/ResearchJob/RunAttempt link "
                    "could not be persisted"
                ) from error

            except Exception:
                connection.rollback()
                raise

        return (
            updated_trial,
            updated_job,
            persisted_attempt,
        )

    def fail_running_job_without_attempt(
        self,
        *,
        job_id: str,
        terminal_at: datetime,
        failure_classification: str,
        failure_message: str,
        trial_disposition: TrialDisposition = (
            TrialDisposition.FAILED
        ),
    ) -> tuple[Trial, ResearchJob, TrialDispositionEvent]:
        """
        Atomically fail one claimed job before any RunAttempt exists.

        BEHAVIOR IMPACT: ADDED
        PRIMARY BEHAVIOR IDS: RESEARCH-RULE-014, RESEARCH-RULE-015
        PRESERVED BEHAVIOR IDS: RESEARCH-RULE-016
        """

        if (
            not isinstance(job_id, str)
            or not job_id
        ):
            raise ValueError(
                "job_id must be a non-empty string"
            )

        if (
            not isinstance(terminal_at, datetime)
            or terminal_at.utcoffset() is None
        ):
            raise ValueError(
                "terminal_at must be a timezone-aware datetime"
            )

        if (
            not isinstance(
                trial_disposition,
                TrialDisposition,
            )
            or trial_disposition not in {
                TrialDisposition.FAILED,
                TrialDisposition.INVALID,
                TrialDisposition.INSUFFICIENT,
            }
        ):
            raise ValueError(
                "trial_disposition must be FAILED, "
                "INVALID or INSUFFICIENT"
            )

        for field_name, value in (
            (
                "failure_classification",
                failure_classification,
            ),
            (
                "failure_message",
                failure_message,
            ),
        ):
            if (
                not isinstance(value, str)
                or not value
            ):
                raise ValueError(
                    f"{field_name} must be a non-empty string"
                )

        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                row = connection.execute(
                    """
                    SELECT
                        j.trial_id,
                        j.state,
                        j.claimed_at,
                        j.terminal_at,
                        j.attempt_id,
                        j.completion_kind,
                        j.reused_attempt_id,
                        j.reused_evidence_id,
                        j.reused_result_artifact_id,
                        j.failure_classification,
                        j.failure_message,
                        t.disposition,
                        t.experiment_spec_id
                    FROM research_jobs j
                    JOIN trials t
                        ON t.trial_id = j.trial_id
                    WHERE j.job_id = ?
                    """,
                    (job_id,),
                ).fetchone()

                if row is None:
                    raise ValueError(
                        f"ResearchJob does not exist: {job_id}"
                    )

                (
                    trial_id,
                    job_state,
                    claimed_at_value,
                    job_terminal_at,
                    attempt_id,
                    completion_kind,
                    reused_attempt_id,
                    reused_evidence_id,
                    reused_result_artifact_id,
                    existing_failure_classification,
                    existing_failure_message,
                    current_trial_disposition,
                    _trial_spec_id,
                ) = row

                if (
                    job_state
                    != ResearchJobState.RUNNING.value
                ):
                    raise ValueError(
                        "ResearchJob must be RUNNING "
                        "before pre-attempt failure"
                    )

                if claimed_at_value is not None:
                    claimed_at = datetime.fromisoformat(
                        claimed_at_value
                    )

                    if terminal_at < claimed_at:
                        raise ValueError(
                            "terminal_at cannot precede "
                            "ResearchJob claim"
                        )

                if any(
                    value is not None
                    for value in (
                        job_terminal_at,
                        attempt_id,
                        completion_kind,
                        reused_attempt_id,
                        reused_evidence_id,
                        reused_result_artifact_id,
                        existing_failure_classification,
                        existing_failure_message,
                    )
                ):
                    raise ValueError(
                        "pre-attempt failure requires an "
                        "uncompleted ResearchJob with no "
                        "attempt or reuse lineage"
                    )

                if (
                    current_trial_disposition
                    != TrialDisposition.PENDING.value
                ):
                    raise ValueError(
                        "Trial must be PENDING before "
                        "pre-attempt failure"
                    )

                cursor = connection.execute(
                    """
                    UPDATE research_jobs
                    SET
                        state = ?,
                        terminal_at = ?,
                        failure_classification = ?,
                        failure_message = ?
                    WHERE
                        job_id = ?
                        AND state = ?
                        AND terminal_at IS NULL
                        AND attempt_id IS NULL
                        AND completion_kind IS NULL
                        AND reused_attempt_id IS NULL
                        AND reused_evidence_id IS NULL
                        AND reused_result_artifact_id IS NULL
                        AND failure_classification IS NULL
                        AND failure_message IS NULL
                    """,
                    (
                        ResearchJobState.FAILED.value,
                        terminal_at.isoformat(
                            timespec="microseconds"
                        ),
                        failure_classification,
                        failure_message,
                        job_id,
                        ResearchJobState.RUNNING.value,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "ResearchJob pre-attempt failure "
                        "lost its RUNNING/unlinked precondition"
                    )

                cursor = connection.execute(
                    """
                    UPDATE trials
                    SET
                        disposition = ?,
                        disposition_at = ?,
                        failure_classification = ?,
                        failure_message = ?
                    WHERE
                        trial_id = ?
                        AND disposition = ?
                    """,
                    (
                        trial_disposition.value,
                        terminal_at.isoformat(
                            timespec="microseconds"
                        ),
                        failure_classification,
                        failure_message,
                        trial_id,
                        TrialDisposition.PENDING.value,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "Trial pre-attempt failure lost "
                        "its PENDING precondition"
                    )

                sequence_number = connection.execute(
                    """
                    SELECT
                        COALESCE(
                            MAX(sequence_number),
                            0
                        ) + 1
                    FROM trial_disposition_events
                    WHERE trial_id = ?
                    """,
                    (trial_id,),
                ).fetchone()[0]

                event_id = canonical_fingerprint(
                    {
                        "trial_id": trial_id,
                        "sequence_number": sequence_number,
                        "new_disposition": (
                            trial_disposition.value
                        ),
                    },
                    schema=(
                        _TRIAL_DISPOSITION_EVENT_SCHEMA_ID
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO trial_disposition_events (
                        event_id,
                        trial_id,
                        sequence_number,
                        previous_disposition,
                        new_disposition,
                        occurred_at,
                        causing_job_id,
                        reason_classification,
                        reason_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        trial_id,
                        sequence_number,
                        TrialDisposition.PENDING.value,
                        trial_disposition.value,
                        terminal_at.isoformat(
                            timespec="microseconds"
                        ),
                        job_id,
                        failure_classification,
                        failure_message,
                    ),
                )

                connection.commit()

            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise ValueError(
                    "pre-attempt ResearchJob failure "
                    "could not be persisted"
                ) from error
            except Exception:
                connection.rollback()
                raise

        trial = self.load_trial(
            trial_id
        )
        job = self.load_research_job(
            job_id
        )
        events = self.load_trial_disposition_events(
            trial_id
        )

        if (
            trial is None
            or job is None
            or not events
        ):
            raise RuntimeError(
                "committed pre-attempt failure lineage "
                "could not be reloaded"
            )

        return (
            trial,
            job,
            events[-1],
        )

    def terminalize_running_job_attempt_with_evidence(
        self,
        attempt_id: str,
        *,
        job_id: str,
        state: RunAttemptState,
        terminal_at: datetime,
        evidence: ResearchEvidence,
        runtime_session_id: str | None = None,
        result_artifact: ResearchArtifact | None = None,
        failure_classification: str | None = None,
        failure_message: str | None = None,
    ) -> RunAttempt:
        """
        Atomically terminalize one ResearchJob-owned fresh execution.

        BEHAVIOR IMPACT: ADDED
        PRIMARY BEHAVIOR IDS: RESEARCH-RULE-014, RESEARCH-RULE-015
        PRESERVED: RESEARCH-RULE-001, RESEARCH-RULE-009,
        RESEARCH-RULE-010.
        """

        if state not in {
            RunAttemptState.SUCCEEDED,
            RunAttemptState.FAILED,
        }:
            raise ValueError(
                "job execution terminalization requires "
                "SUCCEEDED or FAILED"
            )

        if not isinstance(evidence, ResearchEvidence):
            raise TypeError("evidence must be ResearchEvidence")

        if (
            result_artifact is not None
            and not isinstance(
                result_artifact,
                ResearchArtifact,
            )
        ):
            raise TypeError(
                "result_artifact must be a "
                "ResearchArtifact or None"
            )

        if state is RunAttemptState.SUCCEEDED:
            if result_artifact is None:
                raise ValueError(
                    "successful job execution requires "
                    "a result artifact"
                )

            if (
                failure_classification is not None
                or failure_message is not None
            ):
                raise ValueError(
                    "successful job execution cannot carry "
                    "failure metadata"
                )

            if (
                evidence.status
                is not ResearchEvidenceStatus.ACCEPTED
            ):
                raise ValueError(
                    "successful job execution requires "
                    "ACCEPTED evidence"
                )

            if (
                research_artifact_reference(
                    result_artifact.artifact_id
                )
                not in evidence.artifact_references
            ):
                raise ValueError(
                    "successful evidence must reference "
                    "the exact Backtest result artifact"
                )

        if state is RunAttemptState.FAILED:
            if result_artifact is not None:
                raise ValueError(
                    "failed job execution cannot carry "
                    "a result artifact"
                )

            if (
                evidence.status
                is ResearchEvidenceStatus.ACCEPTED
            ):
                raise ValueError(
                    "failed job execution cannot use "
                    "ACCEPTED evidence"
                )

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                row = connection.execute(
                    """
                    SELECT
                        j.trial_id,
                        j.state,
                        j.claimed_at,
                        j.terminal_at,
                        j.attempt_id,
                        j.completion_kind,
                        j.reused_attempt_id,
                        j.reused_evidence_id,
                        j.reused_result_artifact_id,
                        t.experiment_spec_id,
                        t.disposition,
                        a.experiment_spec_id,
                        a.state,
                        a.created_at,
                        a.runtime_session_id,
                        s.dataset_fingerprint,
                        s.configuration_fingerprint,
                        s.repository_revision
                    FROM research_jobs j
                    JOIN trials t
                        ON t.trial_id = j.trial_id
                    JOIN run_attempts a
                        ON a.attempt_id = ?
                    JOIN experiment_specs s
                        ON s.experiment_spec_id
                        = a.experiment_spec_id
                    WHERE j.job_id = ?
                    """,
                    (
                        attempt_id,
                        job_id,
                    ),
                ).fetchone()

                if row is None:
                    raise ValueError(
                        "ResearchJob or RunAttempt does not exist"
                    )

                (
                    trial_id,
                    job_state,
                    claimed_at_value,
                    job_terminal_at,
                    linked_attempt_id,
                    completion_kind,
                    reused_attempt_id,
                    reused_evidence_id,
                    reused_result_artifact_id,
                    trial_spec_id,
                    trial_disposition,
                    attempt_spec_id,
                    attempt_state,
                    attempt_created_at_value,
                    current_runtime_session_id,
                    spec_dataset_fingerprint,
                    spec_configuration_fingerprint,
                    spec_repository_revision,
                ) = row

                if (
                    job_state
                    != ResearchJobState.RUNNING.value
                ):
                    raise ValueError(
                        "ResearchJob must be RUNNING "
                        "before execution terminalization"
                    )

                if linked_attempt_id != attempt_id:
                    raise ValueError(
                        "ResearchJob is not linked to "
                        "the supplied RunAttempt"
                    )

                if any(
                    value is not None
                    for value in (
                        job_terminal_at,
                        completion_kind,
                        reused_attempt_id,
                        reused_evidence_id,
                        reused_result_artifact_id,
                    )
                ):
                    raise ValueError(
                        "RUNNING ResearchJob already carries "
                        "terminal or reuse lineage"
                    )

                if (
                    trial_disposition
                    != TrialDisposition.PENDING.value
                ):
                    raise ValueError(
                        "Trial must be PENDING before "
                        "execution terminalization"
                    )

                if trial_spec_id != attempt_spec_id:
                    raise ValueError(
                        "Trial and RunAttempt must reference "
                        "the same ExperimentSpec"
                    )

                if (
                    attempt_state
                    != RunAttemptState.RUNNING.value
                ):
                    raise ValueError(
                        "RunAttempt must be RUNNING before "
                        "execution terminalization"
                    )

                attempt_created_at = datetime.fromisoformat(
                    attempt_created_at_value
                )

                if terminal_at < attempt_created_at:
                    raise ValueError(
                        "terminal_at cannot precede "
                        "RunAttempt creation"
                    )

                if claimed_at_value is not None:
                    claimed_at = datetime.fromisoformat(
                        claimed_at_value
                    )
                    if terminal_at < claimed_at:
                        raise ValueError(
                            "terminal_at cannot precede "
                            "ResearchJob claim"
                        )

                if (
                    current_runtime_session_id is not None
                    and runtime_session_id is not None
                    and current_runtime_session_id
                    != runtime_session_id
                ):
                    raise ValueError(
                        "runtime_session_id cannot be replaced"
                    )

                final_runtime_session_id = (
                    current_runtime_session_id
                    if runtime_session_id is None
                    else runtime_session_id
                )

                if state is RunAttemptState.SUCCEEDED:
                    if (
                        evidence.dataset_fingerprint
                        != spec_dataset_fingerprint
                        or evidence.configuration_fingerprint
                        != spec_configuration_fingerprint
                        or evidence.repository_revision
                        != spec_repository_revision
                    ):
                        raise ValueError(
                            "successful evidence does not match "
                            "the exact ExperimentSpec"
                        )

                    if (
                        evidence.result_fingerprint
                        != result_artifact.artifact_id
                    ):
                        raise ValueError(
                            "successful evidence/result identity "
                            "does not match"
                        )

                    if (
                        result_artifact.artifact_kind
                        is not
                        ResearchArtifactKind.BACKTEST_RESULT
                        or result_artifact.schema_id
                        != BACKTEST_RESULT_SCHEMA
                    ):
                        raise ValueError(
                            "successful execution requires "
                            "canonical Backtest result artifact"
                        )

                    connection.execute(
                        """
                        INSERT OR IGNORE INTO research_artifacts (
                            artifact_id,
                            artifact_kind,
                            schema_id,
                            relative_path,
                            byte_count,
                            created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            result_artifact.artifact_id,
                            result_artifact.artifact_kind.value,
                            result_artifact.schema_id,
                            result_artifact.relative_path,
                            result_artifact.byte_count,
                            result_artifact.created_at.isoformat(
                                timespec="microseconds"
                            ),
                        ),
                    )

                    artifact_row = connection.execute(
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
                        (
                            result_artifact.artifact_id,
                        ),
                    ).fetchone()

                    if artifact_row is None:
                        raise RuntimeError(
                            "result artifact metadata disappeared"
                        )

                    registered_artifact = (
                        self._artifact_from_row(
                            artifact_row
                        )
                    )

                    if (
                        self._artifact_semantics(
                            registered_artifact
                        )
                        != self._artifact_semantics(
                            result_artifact
                        )
                    ):
                        raise ValueError(
                            "result artifact identity already "
                            "has different immutable metadata"
                        )

                _insert_research_evidence(
                    connection,
                    evidence,
                )

                result_artifact_id = (
                    result_artifact.artifact_id
                    if result_artifact is not None
                    else None
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
                        AND state = ?
                    """,
                    (
                        state.value,
                        terminal_at.isoformat(
                            timespec="microseconds"
                        ),
                        final_runtime_session_id,
                        result_artifact_id,
                        evidence.evidence_id,
                        failure_classification,
                        failure_message,
                        attempt_id,
                        RunAttemptState.RUNNING.value,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "RunAttempt terminal transition lost "
                        "its RUNNING precondition"
                    )

                if state is RunAttemptState.SUCCEEDED:
                    job_state_value = (
                        ResearchJobState.SUCCEEDED.value
                    )
                    completion_kind_value = (
                        ResearchJobCompletionKind.EXECUTED.value
                    )
                    trial_disposition_value = (
                        TrialDisposition.EXECUTED.value
                    )
                    event_reason = (
                        "fresh_execution_succeeded"
                    )
                    job_failure_classification = None
                    job_failure_message = None
                else:
                    job_state_value = (
                        ResearchJobState.FAILED.value
                    )
                    completion_kind_value = None
                    trial_disposition_value = (
                        TrialDisposition.FAILED.value
                    )
                    event_reason = (
                        failure_classification
                        or "execution_failed"
                    )
                    job_failure_classification = (
                        failure_classification
                    )
                    job_failure_message = failure_message

                cursor = connection.execute(
                    """
                    UPDATE research_jobs
                    SET
                        state = ?,
                        terminal_at = ?,
                        completion_kind = ?,
                        failure_classification = ?,
                        failure_message = ?
                    WHERE
                        job_id = ?
                        AND state = ?
                        AND attempt_id = ?
                        AND terminal_at IS NULL
                        AND completion_kind IS NULL
                        AND reused_attempt_id IS NULL
                        AND reused_evidence_id IS NULL
                        AND reused_result_artifact_id IS NULL
                    """,
                    (
                        job_state_value,
                        terminal_at.isoformat(
                            timespec="microseconds"
                        ),
                        completion_kind_value,
                        job_failure_classification,
                        job_failure_message,
                        job_id,
                        ResearchJobState.RUNNING.value,
                        attempt_id,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "ResearchJob terminal transition lost "
                        "its RUNNING/linkage precondition"
                    )

                cursor = connection.execute(
                    """
                    UPDATE trials
                    SET
                        disposition = ?,
                        disposition_at = ?,
                        failure_classification = ?,
                        failure_message = ?
                    WHERE
                        trial_id = ?
                        AND disposition = ?
                        AND experiment_spec_id = ?
                    """,
                    (
                        trial_disposition_value,
                        terminal_at.isoformat(
                            timespec="microseconds"
                        ),
                        job_failure_classification,
                        job_failure_message,
                        trial_id,
                        TrialDisposition.PENDING.value,
                        attempt_spec_id,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "Trial terminal transition lost "
                        "its PENDING/specification precondition"
                    )

                sequence_number = connection.execute(
                    """
                    SELECT
                        COALESCE(
                            MAX(sequence_number),
                            0
                        ) + 1
                    FROM trial_disposition_events
                    WHERE trial_id = ?
                    """,
                    (trial_id,),
                ).fetchone()[0]

                event_id = canonical_fingerprint(
                    {
                        "trial_id": trial_id,
                        "sequence_number": sequence_number,
                        "new_disposition": (
                            trial_disposition_value
                        ),
                    },
                    schema=(
                        _TRIAL_DISPOSITION_EVENT_SCHEMA_ID
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO trial_disposition_events (
                        event_id,
                        trial_id,
                        sequence_number,
                        previous_disposition,
                        new_disposition,
                        occurred_at,
                        causing_job_id,
                        reason_classification,
                        reason_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        trial_id,
                        sequence_number,
                        TrialDisposition.PENDING.value,
                        trial_disposition_value,
                        terminal_at.isoformat(
                            timespec="microseconds"
                        ),
                        job_id,
                        event_reason,
                        failure_message,
                    ),
                )

                terminal = RunAttempt(
                    attempt_id=attempt_id,
                    experiment_spec_id=attempt_spec_id,
                    state=state,
                    created_at=attempt_created_at,
                    terminal_at=terminal_at,
                    runtime_session_id=(
                        final_runtime_session_id
                    ),
                    result_artifact_id=(
                        result_artifact_id
                    ),
                    evidence_id=evidence.evidence_id,
                    failure_classification=(
                        failure_classification
                    ),
                    failure_message=failure_message,
                )

                connection.commit()

            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise ValueError(
                    "coordinated ResearchJob execution "
                    "terminalization could not be persisted"
                ) from error
            except Exception:
                connection.rollback()
                raise

        return terminal

    def complete_running_job_with_exact_reuse(
        self,
        *,
        job_id: str,
        experiment_spec_id: str,
        reused_attempt_id: str,
        terminal_at: datetime,
        requested_dataset_reference_artifact_id: (
            str | None
        ) = None,
        source_dataset_reference_artifact_id: (
            str | None
        ) = None,
    ) -> tuple[Trial, ResearchJob, TrialDispositionEvent]:
        """Atomically complete one RUNNING job by exact accepted reuse."""

        if not isinstance(terminal_at, datetime) or terminal_at.utcoffset() is None:
            raise ValueError("terminal_at must be a timezone-aware datetime")

        dataset_lineage_supplied = (
            requested_dataset_reference_artifact_id
            is not None
            or source_dataset_reference_artifact_id
            is not None
        )

        if dataset_lineage_supplied and (
            requested_dataset_reference_artifact_id
            is None
            or source_dataset_reference_artifact_id
            is None
        ):
            raise ValueError(
                "exact reuse DatasetReference lineage "
                "requires both requested and source artifacts"
            )

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")

                row = connection.execute(
                    """
                    SELECT
                        j.trial_id, j.state, j.claimed_at,
                        j.cancel_requested_at, j.attempt_id,
                        j.terminal_at, j.completion_kind,
                        j.reused_attempt_id, j.reused_evidence_id,
                        j.reused_result_artifact_id,
                        t.experiment_spec_id, t.disposition,
                        sr.evidence_reuse_policy,
                        a.experiment_spec_id, a.state,
                        a.evidence_id, a.result_artifact_id,
                        e.status, e.dataset_fingerprint,
                        e.configuration_fingerprint,
                        e.repository_revision, e.result_fingerprint,
                        e.artifact_references,
                        s.dataset_fingerprint,
                        s.configuration_fingerprint,
                        s.repository_revision,
                        s.manifest_artifact_id,
                        ma.artifact_kind, ma.schema_id,
                        ra.artifact_kind, ra.schema_id
                    FROM research_jobs j
                    JOIN trials t ON t.trial_id = j.trial_id
                    JOIN study_revisions sr
                        ON sr.study_revision_id = t.study_revision_id
                    JOIN experiment_specs s
                        ON s.experiment_spec_id = ?
                    JOIN run_attempts a
                        ON a.attempt_id = ?
                    JOIN research_evidence e
                        ON e.evidence_id = a.evidence_id
                    JOIN research_artifacts ma
                        ON ma.artifact_id = s.manifest_artifact_id
                    JOIN research_artifacts ra
                        ON ra.artifact_id = a.result_artifact_id
                    WHERE j.job_id = ?
                    """,
                    (
                        experiment_spec_id,
                        reused_attempt_id,
                        job_id,
                    ),
                ).fetchone()

                if row is None:
                    raise ValueError(
                        "exact reuse source or ResearchJob does not exist"
                    )

                (
                    trial_id, job_state, claimed_at,
                    cancel_requested_at, attempt_id,
                    job_terminal_at, completion_kind,
                    job_reused_attempt, job_reused_evidence,
                    job_reused_result,
                    trial_spec_id, trial_disposition, reuse_policy,
                    source_spec_id, source_state,
                    evidence_id, result_artifact_id,
                    evidence_status, evidence_dataset_fp,
                    evidence_config_fp, evidence_revision,
                    evidence_result_fp,
                    evidence_artifact_references_json,
                    spec_dataset_fp,
                    spec_config_fp, spec_revision,
                    manifest_artifact_id,
                    manifest_artifact_kind,
                    manifest_artifact_schema,
                    artifact_kind, artifact_schema,
                ) = row

                if job_state != ResearchJobState.RUNNING.value:
                    raise ValueError("ResearchJob must be RUNNING for reuse")
                if cancel_requested_at is not None:
                    raise ValueError(
                        "ResearchJob cancellation request "
                        "blocks exact reuse completion"
                    )
                if claimed_at is not None and terminal_at < datetime.fromisoformat(claimed_at):
                    raise ValueError("terminal_at cannot precede job claim")
                if any(v is not None for v in (
                    attempt_id, job_terminal_at, completion_kind,
                    job_reused_attempt, job_reused_evidence,
                    job_reused_result,
                )):
                    raise ValueError("RUNNING ResearchJob already carries completion lineage")
                if trial_disposition != TrialDisposition.PENDING.value:
                    raise ValueError("Trial must be PENDING for exact reuse")
                if trial_spec_id not in (None, experiment_spec_id):
                    raise ValueError("Trial is bound to a different ExperimentSpec")
                if reuse_policy != EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED.value:
                    raise ValueError("StudyRevision forbids evidence reuse")
                if source_spec_id != experiment_spec_id or source_state != RunAttemptState.SUCCEEDED.value:
                    raise ValueError("reuse requires a successful exact ExperimentSpec attempt")
                if evidence_status != ResearchEvidenceStatus.ACCEPTED.value:
                    raise ValueError("reuse requires ACCEPTED evidence")
                if (
                    evidence_dataset_fp != spec_dataset_fp
                    or evidence_config_fp != spec_config_fp
                    or evidence_revision != spec_revision
                    or evidence_result_fp != result_artifact_id
                ):
                    raise ValueError("reuse evidence does not match exact ExperimentSpec/result")
                if (
                    manifest_artifact_kind
                    != ResearchArtifactKind.BACKTEST_RUN_MANIFEST.value
                    or manifest_artifact_schema
                    != BACKTEST_RUN_MANIFEST_SCHEMA
                ):
                    raise ValueError(
                        "reuse requires canonical Backtest manifest artifact"
                    )
                if (
                    artifact_kind != ResearchArtifactKind.BACKTEST_RESULT.value
                    or artifact_schema != BACKTEST_RESULT_SCHEMA
                ):
                    raise ValueError("reuse requires canonical Backtest result artifact")

                try:
                    evidence_artifact_references = tuple(
                        json.loads(
                            evidence_artifact_references_json
                        )
                    )
                except (TypeError, ValueError, json.JSONDecodeError) as error:
                    raise ValueError(
                        "reuse evidence artifact references are invalid"
                    ) from error

                if (
                    research_artifact_reference(
                        manifest_artifact_id
                    )
                    not in evidence_artifact_references
                ):
                    raise ValueError(
                        "reuse evidence must reference "
                        "the exact Backtest manifest artifact"
                    )

                if (
                    research_artifact_reference(
                        result_artifact_id
                    )
                    not in evidence_artifact_references
                ):
                    raise ValueError(
                        "reuse evidence must reference "
                        "the exact Backtest result artifact"
                    )

                if dataset_lineage_supplied:
                    requested_dataset_row = (
                        connection.execute(
                            """
                            SELECT artifact_kind, schema_id
                            FROM research_artifacts
                            WHERE artifact_id = ?
                            """,
                            (
                                requested_dataset_reference_artifact_id,
                            ),
                        ).fetchone()
                    )

                    source_dataset_row = (
                        connection.execute(
                            """
                            SELECT artifact_kind, schema_id
                            FROM research_artifacts
                            WHERE artifact_id = ?
                            """,
                            (
                                source_dataset_reference_artifact_id,
                            ),
                        ).fetchone()
                    )

                    for (
                        label,
                        artifact_row,
                    ) in (
                        (
                            "requested",
                            requested_dataset_row,
                        ),
                        (
                            "source",
                            source_dataset_row,
                        ),
                    ):
                        if artifact_row is None:
                            raise ValueError(
                                "exact reuse "
                                f"{label} DatasetReference "
                                "artifact does not exist"
                            )

                        if (
                            artifact_row[0]
                            != ResearchArtifactKind
                            .DATASET_REFERENCE
                            .value
                            or artifact_row[1]
                            != DATASET_REFERENCE_SCHEMA_ID
                        ):
                            raise ValueError(
                                "exact reuse "
                                f"{label} dataset lineage "
                                "requires a canonical "
                                "DatasetReference artifact"
                            )

                    if (
                        research_artifact_reference(
                            source_dataset_reference_artifact_id
                        )
                        not in evidence_artifact_references
                    ):
                        raise ValueError(
                            "reuse evidence must reference "
                            "the exact source DatasetReference artifact"
                        )

                sequence_number = connection.execute(
                    """
                    SELECT COALESCE(MAX(sequence_number), 0) + 1
                    FROM trial_disposition_events
                    WHERE trial_id = ?
                    """,
                    (trial_id,),
                ).fetchone()[0]

                event_id = canonical_fingerprint(
                    {
                        "trial_id": trial_id,
                        "sequence_number": sequence_number,
                        "new_disposition": TrialDisposition.REUSED.value,
                    },
                    schema=_TRIAL_DISPOSITION_EVENT_SCHEMA_ID,
                )

                connection.execute(
                    """
                    UPDATE trials
                    SET experiment_spec_id = ?,
                        disposition = ?,
                        disposition_at = ?,
                        reused_attempt_id = ?,
                        failure_classification = NULL,
                        failure_message = NULL
                    WHERE trial_id = ? AND disposition = ?
                    """,
                    (
                        experiment_spec_id,
                        TrialDisposition.REUSED.value,
                        terminal_at.isoformat(timespec="microseconds"),
                        reused_attempt_id,
                        trial_id,
                        TrialDisposition.PENDING.value,
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO trial_disposition_events (
                        event_id, trial_id, sequence_number,
                        previous_disposition, new_disposition,
                        occurred_at, causing_job_id,
                        reason_classification, reason_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL)
                    """,
                    (
                        event_id,
                        trial_id,
                        sequence_number,
                        TrialDisposition.PENDING.value,
                        TrialDisposition.REUSED.value,
                        terminal_at.isoformat(timespec="microseconds"),
                        job_id,
                        "exact_accepted_evidence_reuse",
                    ),
                )

                cursor = connection.execute(
                    """
                    UPDATE research_jobs
                    SET state = ?, terminal_at = ?, completion_kind = ?,
                        reused_attempt_id = ?, reused_evidence_id = ?,
                        reused_result_artifact_id = ?
                    WHERE job_id = ? AND state = ?
                      AND cancel_requested_at IS NULL
                      AND attempt_id IS NULL
                      AND terminal_at IS NULL
                      AND completion_kind IS NULL
                    """,
                    (
                        ResearchJobState.SUCCEEDED.value,
                        terminal_at.isoformat(timespec="microseconds"),
                        ResearchJobCompletionKind.REUSED.value,
                        reused_attempt_id,
                        evidence_id,
                        result_artifact_id,
                        job_id,
                        ResearchJobState.RUNNING.value,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "exact reuse lost its RUNNING/uncompleted job precondition"
                    )

                if dataset_lineage_supplied:
                    connection.execute(
                        """
                        INSERT INTO
                            research_job_reuse_dataset_lineage (
                                job_id,
                                requested_dataset_reference_artifact_id,
                                source_dataset_reference_artifact_id
                            )
                        VALUES (?, ?, ?)
                        """,
                        (
                            job_id,
                            requested_dataset_reference_artifact_id,
                            source_dataset_reference_artifact_id,
                        ),
                    )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

        trial = self.load_trial(trial_id)
        job = self.load_research_job(job_id)
        events = self.load_trial_disposition_events(trial_id)

        if trial is None or job is None or not events:
            raise RuntimeError("committed exact reuse lineage could not be reloaded")

        return trial, job, events[-1]

    def retry_trial(
        self,
        trial_id: str,
        *,
        retry_requested_at: datetime,
    ) -> tuple[
        Trial,
        ResearchJob,
        TrialDispositionEvent,
    ]:
        """
        Atomically create one explicit retry job for one Trial.

        BEHAVIOR IMPACT: ADDED
        PRIMARY BEHAVIOR IDS: RESEARCH-RULE-008,
        RESEARCH-RULE-014, RESEARCH-RULE-015
        """

        if (
            not isinstance(trial_id, str)
            or not trial_id
        ):
            raise ValueError(
                "trial_id must be a non-empty string"
            )

        if (
            not isinstance(
                retry_requested_at,
                datetime,
            )
            or retry_requested_at.utcoffset()
            is None
        ):
            raise ValueError(
                "retry_requested_at must be a "
                "timezone-aware datetime"
            )

        retryable = {
            TrialDisposition.FAILED.value,
            TrialDisposition.CANCELLED.value,
            TrialDisposition.INTERRUPTED.value,
        }

        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                trial_row = connection.execute(
                    """
                    SELECT
                        disposition,
                        disposition_at,
                        experiment_spec_id
                    FROM trials
                    WHERE trial_id = ?
                    """,
                    (trial_id,),
                ).fetchone()

                if trial_row is None:
                    raise ValueError(
                        f"Trial does not exist: {trial_id}"
                    )

                (
                    previous_disposition,
                    disposition_at_value,
                    _experiment_spec_id,
                ) = trial_row

                if previous_disposition not in retryable:
                    raise ValueError(
                        "Trial is not eligible for ordinary "
                        "retry from its current disposition"
                    )

                disposition_at = datetime.fromisoformat(
                    disposition_at_value
                )

                if (
                    retry_requested_at
                    < disposition_at
                ):
                    raise ValueError(
                        "retry_requested_at cannot precede "
                        "the current Trial disposition time"
                    )

                active_job_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM research_jobs
                    WHERE
                        trial_id = ?
                        AND state IN ('QUEUED', 'RUNNING')
                    """,
                    (trial_id,),
                ).fetchone()[0]

                if active_job_count != 0:
                    raise ValueError(
                        "retry requires no existing QUEUED "
                        "or RUNNING ResearchJob"
                    )

                terminal_job_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM research_jobs
                    WHERE
                        trial_id = ?
                        AND state IN (
                            'SUCCEEDED',
                            'FAILED',
                            'CANCELLED',
                            'INTERRUPTED'
                        )
                    """,
                    (trial_id,),
                ).fetchone()[0]

                if terminal_job_count < 1:
                    raise ValueError(
                        "retry requires prior terminal "
                        "ResearchJob history"
                    )

                retry_ordinal = (
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM trial_disposition_events
                        WHERE
                            trial_id = ?
                            AND new_disposition = 'PENDING'
                            AND previous_disposition IN (
                                'FAILED',
                                'CANCELLED',
                                'INTERRUPTED'
                            )
                        """,
                        (trial_id,),
                    ).fetchone()[0]
                    + 1
                )

                job_id = _retry_research_job_id(
                    trial_id,
                    retry_ordinal,
                )

                existing_retry = connection.execute(
                    """
                    SELECT trial_id
                    FROM research_jobs
                    WHERE job_id = ?
                    """,
                    (job_id,),
                ).fetchone()

                if existing_retry is not None:
                    raise ValueError(
                        "deterministic retry ResearchJob "
                        "identity already exists"
                    )

                sequence_number = (
                    connection.execute(
                        """
                        SELECT
                            COALESCE(
                                MAX(sequence_number),
                                0
                            ) + 1
                        FROM trial_disposition_events
                        WHERE trial_id = ?
                        """,
                        (trial_id,),
                    ).fetchone()[0]
                )

                event_id = canonical_fingerprint(
                    {
                        "trial_id": trial_id,
                        "sequence_number": (
                            sequence_number
                        ),
                        "new_disposition": (
                            TrialDisposition.PENDING.value
                        ),
                    },
                    schema=(
                        _TRIAL_DISPOSITION_EVENT_SCHEMA_ID
                    ),
                )

                occurred_at = (
                    retry_requested_at.isoformat(
                        timespec="microseconds"
                    )
                )

                cursor = connection.execute(
                    """
                    UPDATE trials
                    SET
                        disposition = ?,
                        disposition_at = ?,
                        reused_attempt_id = NULL,
                        failure_classification = NULL,
                        failure_message = NULL
                    WHERE
                        trial_id = ?
                        AND disposition = ?
                    """,
                    (
                        TrialDisposition.PENDING.value,
                        occurred_at,
                        trial_id,
                        previous_disposition,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "retry lost its Trial disposition "
                        "precondition"
                    )

                connection.execute(
                    """
                    INSERT INTO research_jobs (
                        job_id,
                        trial_id,
                        state,
                        created_at,
                        claimed_at,
                        terminal_at,
                        worker_id,
                        cancel_requested_at,
                        attempt_id,
                        completion_kind,
                        reused_attempt_id,
                        reused_evidence_id,
                        reused_result_artifact_id,
                        failure_classification,
                        failure_message
                    ) VALUES (
                        ?, ?, 'QUEUED', ?,
                        NULL, NULL, NULL, NULL, NULL,
                        NULL, NULL, NULL, NULL, NULL, NULL
                    )
                    """,
                    (
                        job_id,
                        trial_id,
                        occurred_at,
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO trial_disposition_events (
                        event_id,
                        trial_id,
                        sequence_number,
                        previous_disposition,
                        new_disposition,
                        occurred_at,
                        causing_job_id,
                        reason_classification,
                        reason_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        trial_id,
                        sequence_number,
                        previous_disposition,
                        TrialDisposition.PENDING.value,
                        occurred_at,
                        job_id,
                        "explicit_retry",
                        "explicit retry requested",
                    ),
                )

                connection.commit()

            except sqlite3.IntegrityError as error:
                connection.rollback()
                raise ValueError(
                    "explicit retry could not be "
                    "persisted atomically"
                ) from error
            except Exception:
                connection.rollback()
                raise

        trial = self.load_trial(
            trial_id
        )
        job = self.load_research_job(
            job_id
        )
        events = self.load_trial_disposition_events(
            trial_id
        )

        if (
            trial is None
            or job is None
            or not events
        ):
            raise RuntimeError(
                "committed retry lineage could not "
                "be reloaded"
            )

        return (
            trial,
            job,
            events[-1],
        )

    def cancel_study_revision_batch(
        self,
        *,
        study_revision_id: str,
        requested_at: datetime,
    ) -> tuple[ResearchJob, ...]:
        """
        Atomically cancel active work for one StudyRevision batch.

        QUEUED jobs become CANCELLED immediately without creating a
        RunAttempt. RUNNING jobs remain RUNNING and receive a durable
        cancellation request for cooperative acknowledgement. No retry
        job is created automatically.
        """

        if (
            not isinstance(study_revision_id, str)
            or not study_revision_id
        ):
            raise ValueError(
                "study_revision_id must be a non-empty string"
            )

        if (
            not isinstance(requested_at, datetime)
            or requested_at.utcoffset() is None
        ):
            raise ValueError(
                "requested_at must be a timezone-aware datetime"
            )

        affected_job_ids: list[str] = []

        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                revision_row = connection.execute(
                    """
                    SELECT initial_batch_started_at
                    FROM study_revisions
                    WHERE study_revision_id = ?
                    """,
                    (
                        study_revision_id,
                    ),
                ).fetchone()

                if revision_row is None:
                    raise ValueError(
                        "StudyRevision does not exist"
                    )

                if revision_row[0] is None:
                    raise ValueError(
                        "StudyRevision batch must be started "
                        "before cancellation"
                    )

                rows = connection.execute(
                    """
                    SELECT
                        j.job_id,
                        j.trial_id,
                        j.state,
                        j.created_at,
                        j.claimed_at,
                        j.terminal_at,
                        j.worker_id,
                        j.cancel_requested_at,
                        j.attempt_id,
                        j.completion_kind,
                        j.reused_attempt_id,
                        j.reused_evidence_id,
                        j.reused_result_artifact_id,
                        j.failure_classification,
                        j.failure_message,
                        t.disposition
                    FROM research_jobs j
                    JOIN trials t
                        ON t.trial_id = j.trial_id
                    WHERE
                        t.study_revision_id = ?
                        AND j.state IN (?, ?)
                    ORDER BY
                        j.created_at ASC,
                        j.job_id ASC
                    """,
                    (
                        study_revision_id,
                        ResearchJobState.QUEUED.value,
                        ResearchJobState.RUNNING.value,
                    ),
                ).fetchall()

                active = tuple(
                    (
                        self._research_job_from_row(
                            row[:15]
                        ),
                        row[15],
                    )
                    for row in rows
                )

                for current_job, trial_disposition in active:
                    if (
                        trial_disposition
                        != TrialDisposition.PENDING.value
                    ):
                        raise RuntimeError(
                            "active ResearchJob batch cancellation "
                            "requires a PENDING Trial"
                        )

                    if requested_at < current_job.created_at:
                        raise ValueError(
                            "requested_at cannot precede "
                            "ResearchJob creation"
                        )

                    if (
                        current_job.state
                        is ResearchJobState.RUNNING
                        and current_job.claimed_at is not None
                        and requested_at
                        < current_job.claimed_at
                    ):
                        raise ValueError(
                            "requested_at cannot precede "
                            "ResearchJob claim"
                        )

                queued = tuple(
                    job
                    for job, _
                    in active
                    if job.state
                    is ResearchJobState.QUEUED
                )

                running = tuple(
                    job
                    for job, _
                    in active
                    if job.state
                    is ResearchJobState.RUNNING
                )

                terminal_text = requested_at.isoformat(
                    timespec="microseconds"
                )

                for job in queued:
                    cursor = connection.execute(
                        """
                        UPDATE research_jobs
                        SET
                            state = ?,
                            terminal_at = ?
                        WHERE
                            job_id = ?
                            AND state = ?
                            AND claimed_at IS NULL
                            AND worker_id IS NULL
                            AND cancel_requested_at IS NULL
                            AND attempt_id IS NULL
                            AND terminal_at IS NULL
                            AND completion_kind IS NULL
                            AND reused_attempt_id IS NULL
                            AND reused_evidence_id IS NULL
                            AND reused_result_artifact_id IS NULL
                        """,
                        (
                            ResearchJobState.CANCELLED.value,
                            terminal_text,
                            job.job_id,
                            ResearchJobState.QUEUED.value,
                        ),
                    )

                    if cursor.rowcount != 1:
                        raise RuntimeError(
                            "batch queued cancellation lost its "
                            "QUEUED/unclaimed precondition"
                        )

                    affected_job_ids.append(
                        job.job_id
                    )

                for job in running:
                    if job.cancel_requested_at is None:
                        cursor = connection.execute(
                            """
                            UPDATE research_jobs
                            SET cancel_requested_at = ?
                            WHERE
                                job_id = ?
                                AND state = ?
                                AND cancel_requested_at IS NULL
                                AND terminal_at IS NULL
                            """,
                            (
                                terminal_text,
                                job.job_id,
                                ResearchJobState.RUNNING.value,
                            ),
                        )

                        if cursor.rowcount != 1:
                            raise RuntimeError(
                                "batch running cancellation request "
                                "lost its RUNNING precondition"
                            )

                    affected_job_ids.append(
                        job.job_id
                    )

                for job in queued:
                    other_active_count = (
                        connection.execute(
                            """
                            SELECT COUNT(*)
                            FROM research_jobs
                            WHERE
                                trial_id = ?
                                AND job_id <> ?
                                AND state IN ('QUEUED', 'RUNNING')
                            """,
                            (
                                job.trial_id,
                                job.job_id,
                            ),
                        ).fetchone()[0]
                    )

                    if other_active_count != 0:
                        continue

                    cursor = connection.execute(
                        """
                        UPDATE trials
                        SET
                            disposition = ?,
                            disposition_at = ?,
                            reused_attempt_id = NULL,
                            failure_classification = NULL,
                            failure_message = NULL
                        WHERE
                            trial_id = ?
                            AND disposition = ?
                        """,
                        (
                            TrialDisposition.CANCELLED.value,
                            terminal_text,
                            job.trial_id,
                            TrialDisposition.PENDING.value,
                        ),
                    )

                    if cursor.rowcount != 1:
                        raise RuntimeError(
                            "batch queued cancellation lost its "
                            "PENDING Trial precondition"
                        )

                    sequence_number = (
                        connection.execute(
                            """
                            SELECT
                                COALESCE(
                                    MAX(sequence_number),
                                    0
                                ) + 1
                            FROM trial_disposition_events
                            WHERE trial_id = ?
                            """,
                            (
                                job.trial_id,
                            ),
                        ).fetchone()[0]
                    )

                    event_id = canonical_fingerprint(
                        {
                            "trial_id": job.trial_id,
                            "sequence_number": (
                                sequence_number
                            ),
                            "new_disposition": (
                                TrialDisposition.CANCELLED.value
                            ),
                        },
                        schema=(
                            _TRIAL_DISPOSITION_EVENT_SCHEMA_ID
                        ),
                    )

                    connection.execute(
                        """
                        INSERT INTO trial_disposition_events (
                            event_id,
                            trial_id,
                            sequence_number,
                            previous_disposition,
                            new_disposition,
                            occurred_at,
                            causing_job_id,
                            reason_classification,
                            reason_message
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            job.trial_id,
                            sequence_number,
                            TrialDisposition.PENDING.value,
                            TrialDisposition.CANCELLED.value,
                            terminal_text,
                            job.job_id,
                            "batch_cancellation",
                            (
                                "ResearchJob cancelled by "
                                "StudyRevision batch cancellation"
                            ),
                        ),
                    )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

        affected: list[ResearchJob] = []

        for job_id in affected_job_ids:
            job = self.load_research_job(
                job_id
            )

            if job is None:
                raise RuntimeError(
                    "committed batch cancellation "
                    "could not reload ResearchJob"
                )

            affected.append(job)

        return tuple(affected)

    def cancel_queued_research_job(
        self,
        *,
        job_id: str,
        terminal_at: datetime,
    ) -> tuple[
        Trial,
        ResearchJob,
        TrialDispositionEvent | None,
    ]:
        """
        Atomically cancel one still-QUEUED ResearchJob.

        M9.4e queued cancellation creates no RunAttempt. The Trial becomes
        CANCELLED only when no other QUEUED or RUNNING job can still
        complete that same Trial.
        """

        if (
            not isinstance(job_id, str)
            or not job_id
        ):
            raise ValueError(
                "job_id must be a non-empty string"
            )

        if (
            not isinstance(terminal_at, datetime)
            or terminal_at.utcoffset() is None
        ):
            raise ValueError(
                "terminal_at must be a timezone-aware datetime"
            )

        event_created = False

        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                row = connection.execute(
                    """
                    SELECT
                        j.job_id,
                        j.trial_id,
                        j.state,
                        j.created_at,
                        j.claimed_at,
                        j.terminal_at,
                        j.worker_id,
                        j.cancel_requested_at,
                        j.attempt_id,
                        j.completion_kind,
                        j.reused_attempt_id,
                        j.reused_evidence_id,
                        j.reused_result_artifact_id,
                        j.failure_classification,
                        j.failure_message,
                        t.disposition
                    FROM research_jobs j
                    JOIN trials t
                        ON t.trial_id = j.trial_id
                    WHERE j.job_id = ?
                    """,
                    (job_id,),
                ).fetchone()

                if row is None:
                    raise ValueError(
                        f"ResearchJob does not exist: {job_id}"
                    )

                current_job = (
                    self._research_job_from_row(
                        row[:15]
                    )
                )
                trial_disposition = row[15]

                if (
                    current_job.state
                    is not ResearchJobState.QUEUED
                ):
                    raise ValueError(
                        "queued cancellation requires "
                        "a QUEUED ResearchJob"
                    )

                if terminal_at < current_job.created_at:
                    raise ValueError(
                        "terminal_at cannot precede "
                        "ResearchJob created_at"
                    )

                if (
                    trial_disposition
                    != TrialDisposition.PENDING.value
                ):
                    raise ValueError(
                        "queued cancellation requires "
                        "a PENDING Trial"
                    )

                if current_job.cancel_requested_at is not None:
                    raise ValueError(
                        "QUEUED ResearchJob cannot already "
                        "carry a cancellation request"
                    )

                cursor = connection.execute(
                    """
                    UPDATE research_jobs
                    SET
                        state = ?,
                        terminal_at = ?
                    WHERE
                        job_id = ?
                        AND state = ?
                        AND claimed_at IS NULL
                        AND worker_id IS NULL
                        AND cancel_requested_at IS NULL
                        AND attempt_id IS NULL
                        AND terminal_at IS NULL
                        AND completion_kind IS NULL
                        AND reused_attempt_id IS NULL
                        AND reused_evidence_id IS NULL
                        AND reused_result_artifact_id IS NULL
                    """,
                    (
                        ResearchJobState.CANCELLED.value,
                        terminal_at.isoformat(
                            timespec="microseconds"
                        ),
                        job_id,
                        ResearchJobState.QUEUED.value,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "queued cancellation lost its "
                        "QUEUED/unclaimed precondition"
                    )

                other_active_count = (
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM research_jobs
                        WHERE
                            trial_id = ?
                            AND job_id <> ?
                            AND state IN ('QUEUED', 'RUNNING')
                        """,
                        (
                            current_job.trial_id,
                            job_id,
                        ),
                    ).fetchone()[0]
                )

                if other_active_count == 0:
                    cursor = connection.execute(
                        """
                        UPDATE trials
                        SET
                            disposition = ?,
                            disposition_at = ?,
                            reused_attempt_id = NULL,
                            failure_classification = NULL,
                            failure_message = NULL
                        WHERE
                            trial_id = ?
                            AND disposition = ?
                        """,
                        (
                            TrialDisposition.CANCELLED.value,
                            terminal_at.isoformat(
                                timespec="microseconds"
                            ),
                            current_job.trial_id,
                            TrialDisposition.PENDING.value,
                        ),
                    )

                    if cursor.rowcount != 1:
                        raise RuntimeError(
                            "queued cancellation lost its "
                            "PENDING Trial precondition"
                        )

                    sequence_number = (
                        connection.execute(
                            """
                            SELECT
                                COALESCE(
                                    MAX(sequence_number),
                                    0
                                ) + 1
                            FROM trial_disposition_events
                            WHERE trial_id = ?
                            """,
                            (
                                current_job.trial_id,
                            ),
                        ).fetchone()[0]
                    )

                    event_id = canonical_fingerprint(
                        {
                            "trial_id": (
                                current_job.trial_id
                            ),
                            "sequence_number": (
                                sequence_number
                            ),
                            "new_disposition": (
                                TrialDisposition.CANCELLED.value
                            ),
                        },
                        schema=(
                            _TRIAL_DISPOSITION_EVENT_SCHEMA_ID
                        ),
                    )

                    connection.execute(
                        """
                        INSERT INTO trial_disposition_events (
                            event_id,
                            trial_id,
                            sequence_number,
                            previous_disposition,
                            new_disposition,
                            occurred_at,
                            causing_job_id,
                            reason_classification,
                            reason_message
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            current_job.trial_id,
                            sequence_number,
                            TrialDisposition.PENDING.value,
                            TrialDisposition.CANCELLED.value,
                            terminal_at.isoformat(
                                timespec="microseconds"
                            ),
                            job_id,
                            "queued_cancellation",
                            (
                                "ResearchJob cancelled before claim"
                            ),
                        ),
                    )

                    event_created = True

                connection.commit()

            except Exception:
                connection.rollback()
                raise

        trial = self.load_trial(
            current_job.trial_id
        )
        job = self.load_research_job(
            job_id
        )

        if trial is None or job is None:
            raise RuntimeError(
                "committed queued cancellation "
                "could not be reloaded"
            )

        event = None

        if event_created:
            events = (
                self.load_trial_disposition_events(
                    current_job.trial_id
                )
            )

            if not events:
                raise RuntimeError(
                    "queued cancellation event "
                    "could not be reloaded"
                )

            event = events[-1]

        return trial, job, event

    def request_running_research_job_cancellation(
        self,
        *,
        job_id: str,
        requested_at: datetime,
    ) -> ResearchJob:
        """
        Durably request cancellation of one RUNNING ResearchJob.

        The ResearchJob intentionally remains RUNNING until its worker
        acknowledges a safe cooperative cancellation checkpoint or the
        authoritative computation truthfully terminates.
        """

        if (
            not isinstance(job_id, str)
            or not job_id
        ):
            raise ValueError(
                "job_id must be a non-empty string"
            )

        if (
            not isinstance(requested_at, datetime)
            or requested_at.utcoffset() is None
        ):
            raise ValueError(
                "requested_at must be a timezone-aware datetime"
            )

        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                row = connection.execute(
                    """
                    SELECT
                        job_id,
                        trial_id,
                        state,
                        created_at,
                        claimed_at,
                        terminal_at,
                        worker_id,
                        cancel_requested_at,
                        attempt_id,
                        completion_kind,
                        reused_attempt_id,
                        reused_evidence_id,
                        reused_result_artifact_id,
                        failure_classification,
                        failure_message
                    FROM research_jobs
                    WHERE job_id = ?
                    """,
                    (job_id,),
                ).fetchone()

                if row is None:
                    raise ValueError(
                        f"ResearchJob does not exist: {job_id}"
                    )

                current = (
                    self._research_job_from_row(
                        row
                    )
                )

                if (
                    current.state
                    is not ResearchJobState.RUNNING
                ):
                    raise ValueError(
                        "running cancellation request requires "
                        "a RUNNING ResearchJob"
                    )

                if (
                    current.claimed_at is not None
                    and requested_at < current.claimed_at
                ):
                    raise ValueError(
                        "requested_at cannot precede "
                        "ResearchJob claim"
                    )

                if current.cancel_requested_at is None:
                    cursor = connection.execute(
                        """
                        UPDATE research_jobs
                        SET cancel_requested_at = ?
                        WHERE
                            job_id = ?
                            AND state = ?
                            AND cancel_requested_at IS NULL
                            AND terminal_at IS NULL
                        """,
                        (
                            requested_at.isoformat(
                                timespec="microseconds"
                            ),
                            job_id,
                            ResearchJobState.RUNNING.value,
                        ),
                    )

                    if cursor.rowcount != 1:
                        raise RuntimeError(
                            "running cancellation request "
                            "lost its RUNNING precondition"
                        )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

        persisted = self.load_research_job(
            job_id
        )

        if persisted is None:
            raise RuntimeError(
                "committed running cancellation request "
                "could not be reloaded"
            )

        return persisted


    def acknowledge_running_research_job_cancellation(
        self,
        *,
        job_id: str,
        terminal_at: datetime,
    ) -> tuple[
        Trial,
        ResearchJob,
        TrialDispositionEvent,
    ]:
        """
        Atomically acknowledge one cooperative RUNNING cancellation.

        This primitive is valid only before financial execution has
        started: the job must still have no RunAttempt or reuse lineage.
        The durable cancellation request is preserved for audit.
        """

        if (
            not isinstance(job_id, str)
            or not job_id
        ):
            raise ValueError(
                "job_id must be a non-empty string"
            )

        if (
            not isinstance(terminal_at, datetime)
            or terminal_at.utcoffset() is None
        ):
            raise ValueError(
                "terminal_at must be a timezone-aware datetime"
            )

        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                row = connection.execute(
                    """
                    SELECT
                        j.job_id,
                        j.trial_id,
                        j.state,
                        j.created_at,
                        j.claimed_at,
                        j.terminal_at,
                        j.worker_id,
                        j.cancel_requested_at,
                        j.attempt_id,
                        j.completion_kind,
                        j.reused_attempt_id,
                        j.reused_evidence_id,
                        j.reused_result_artifact_id,
                        j.failure_classification,
                        j.failure_message,
                        t.disposition
                    FROM research_jobs j
                    JOIN trials t
                        ON t.trial_id = j.trial_id
                    WHERE j.job_id = ?
                    """,
                    (job_id,),
                ).fetchone()

                if row is None:
                    raise ValueError(
                        f"ResearchJob does not exist: {job_id}"
                    )

                current = self._research_job_from_row(
                    row[:15]
                )
                trial_disposition = row[15]

                if (
                    current.state
                    is not ResearchJobState.RUNNING
                ):
                    raise ValueError(
                        "cancellation acknowledgement requires "
                        "a RUNNING ResearchJob"
                    )

                if current.cancel_requested_at is None:
                    raise ValueError(
                        "cancellation acknowledgement requires "
                        "a durable cancellation request"
                    )

                if (
                    terminal_at
                    < current.cancel_requested_at
                ):
                    raise ValueError(
                        "terminal_at cannot precede "
                        "the cancellation request"
                    )

                if (
                    trial_disposition
                    != TrialDisposition.PENDING.value
                ):
                    raise ValueError(
                        "cancellation acknowledgement requires "
                        "a PENDING Trial"
                    )

                if any(
                    value is not None
                    for value in (
                        current.terminal_at,
                        current.attempt_id,
                        current.completion_kind,
                        current.reused_attempt_id,
                        current.reused_evidence_id,
                        current.reused_result_artifact_id,
                        current.failure_classification,
                        current.failure_message,
                    )
                ):
                    raise ValueError(
                        "cancellation acknowledgement requires "
                        "an uncompleted pre-attempt ResearchJob"
                    )

                cursor = connection.execute(
                    """
                    UPDATE research_jobs
                    SET
                        state = ?,
                        terminal_at = ?
                    WHERE
                        job_id = ?
                        AND state = ?
                        AND cancel_requested_at IS NOT NULL
                        AND terminal_at IS NULL
                        AND attempt_id IS NULL
                        AND completion_kind IS NULL
                        AND reused_attempt_id IS NULL
                        AND reused_evidence_id IS NULL
                        AND reused_result_artifact_id IS NULL
                        AND failure_classification IS NULL
                        AND failure_message IS NULL
                    """,
                    (
                        ResearchJobState.CANCELLED.value,
                        terminal_at.isoformat(
                            timespec="microseconds"
                        ),
                        job_id,
                        ResearchJobState.RUNNING.value,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "cancellation acknowledgement lost "
                        "its RUNNING/pre-attempt precondition"
                    )

                other_active_count = (
                    connection.execute(
                        """
                        SELECT COUNT(*)
                        FROM research_jobs
                        WHERE
                            trial_id = ?
                            AND job_id <> ?
                            AND state IN ('QUEUED', 'RUNNING')
                        """,
                        (
                            current.trial_id,
                            job_id,
                        ),
                    ).fetchone()[0]
                )

                if other_active_count != 0:
                    raise RuntimeError(
                        "running cancellation acknowledgement "
                        "found another active ResearchJob"
                    )

                cursor = connection.execute(
                    """
                    UPDATE trials
                    SET
                        disposition = ?,
                        disposition_at = ?,
                        reused_attempt_id = NULL,
                        failure_classification = NULL,
                        failure_message = NULL
                    WHERE
                        trial_id = ?
                        AND disposition = ?
                    """,
                    (
                        TrialDisposition.CANCELLED.value,
                        terminal_at.isoformat(
                            timespec="microseconds"
                        ),
                        current.trial_id,
                        TrialDisposition.PENDING.value,
                    ),
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "cancellation acknowledgement lost "
                        "its PENDING Trial precondition"
                    )

                sequence_number = (
                    connection.execute(
                        """
                        SELECT
                            COALESCE(
                                MAX(sequence_number),
                                0
                            ) + 1
                        FROM trial_disposition_events
                        WHERE trial_id = ?
                        """,
                        (current.trial_id,),
                    ).fetchone()[0]
                )

                event_id = canonical_fingerprint(
                    {
                        "trial_id": current.trial_id,
                        "sequence_number": sequence_number,
                        "new_disposition": (
                            TrialDisposition.CANCELLED.value
                        ),
                    },
                    schema=(
                        _TRIAL_DISPOSITION_EVENT_SCHEMA_ID
                    ),
                )

                connection.execute(
                    """
                    INSERT INTO trial_disposition_events (
                        event_id,
                        trial_id,
                        sequence_number,
                        previous_disposition,
                        new_disposition,
                        occurred_at,
                        causing_job_id,
                        reason_classification,
                        reason_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        current.trial_id,
                        sequence_number,
                        TrialDisposition.PENDING.value,
                        TrialDisposition.CANCELLED.value,
                        terminal_at.isoformat(
                            timespec="microseconds"
                        ),
                        job_id,
                        "running_cancellation_acknowledged",
                        (
                            "ResearchJob cancellation acknowledged "
                            "at a cooperative pre-execution checkpoint"
                        ),
                    ),
                )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

        trial = self.load_trial(
            current.trial_id
        )
        job = self.load_research_job(
            job_id
        )
        events = self.load_trial_disposition_events(
            current.trial_id
        )

        if (
            trial is None
            or job is None
            or not events
        ):
            raise RuntimeError(
                "committed cancellation acknowledgement "
                "could not be reloaded"
            )

        return trial, job, events[-1]

    def recover_running_research_jobs(
        self,
        *,
        terminal_at: datetime,
    ) -> tuple[ResearchJob, ...]:
        """
        Atomically recover stale RUNNING ResearchJobs as INTERRUPTED.

        When a job owns a RUNNING RunAttempt, the attempt, job and Trial
        are interrupted in the same SQLite transaction. No retry or new
        claim is created automatically.
        """

        if (
            not isinstance(terminal_at, datetime)
            or terminal_at.utcoffset() is None
        ):
            raise ValueError(
                "terminal_at must be a timezone-aware datetime"
            )

        recovered_job_ids: list[str] = []

        with closing(self._connect()) as connection:
            try:
                connection.execute(
                    "BEGIN IMMEDIATE"
                )

                rows = connection.execute(
                    """
                    SELECT
                        j.job_id,
                        j.trial_id,
                        j.state,
                        j.created_at,
                        j.claimed_at,
                        j.terminal_at,
                        j.worker_id,
                        j.cancel_requested_at,
                        j.attempt_id,
                        j.completion_kind,
                        j.reused_attempt_id,
                        j.reused_evidence_id,
                        j.reused_result_artifact_id,
                        j.failure_classification,
                        j.failure_message,
                        t.disposition
                    FROM research_jobs j
                    JOIN trials t
                        ON t.trial_id = j.trial_id
                    WHERE j.state = ?
                    ORDER BY
                        j.claimed_at ASC,
                        j.job_id ASC
                    """,
                    (
                        ResearchJobState.RUNNING.value,
                    ),
                ).fetchall()

                for row in rows:
                    current = self._research_job_from_row(
                        row[:15]
                    )
                    trial_disposition = row[15]

                    if (
                        trial_disposition
                        != TrialDisposition.PENDING.value
                    ):
                        raise RuntimeError(
                            "RUNNING ResearchJob recovery requires "
                            "a PENDING Trial"
                        )

                    effective_terminal_at = max(
                        terminal_at,
                        current.created_at,
                        current.claimed_at
                        or current.created_at,
                    )

                    if any(
                        value is not None
                        for value in (
                            current.terminal_at,
                            current.completion_kind,
                            current.reused_attempt_id,
                            current.reused_evidence_id,
                            current.reused_result_artifact_id,
                        )
                    ):
                        raise RuntimeError(
                            "RUNNING ResearchJob recovery found "
                            "terminal or reuse lineage"
                        )

                    if current.attempt_id is not None:
                        attempt_row = connection.execute(
                            """
                            SELECT
                                state,
                                created_at
                            FROM run_attempts
                            WHERE attempt_id = ?
                            """,
                            (
                                current.attempt_id,
                            ),
                        ).fetchone()

                        if attempt_row is None:
                            raise RuntimeError(
                                "RUNNING ResearchJob references "
                                "a missing RunAttempt"
                            )

                        if (
                            attempt_row[0]
                            != RunAttemptState.RUNNING.value
                        ):
                            raise RuntimeError(
                                "RUNNING ResearchJob recovery requires "
                                "its linked RunAttempt to be RUNNING"
                            )

                        attempt_created_at = (
                            datetime.fromisoformat(
                                attempt_row[1]
                            )
                        )

                        attempt_terminal_at = max(
                            effective_terminal_at,
                            attempt_created_at,
                        )

                        cursor = connection.execute(
                            """
                            UPDATE run_attempts
                            SET
                                state = ?,
                                terminal_at = ?,
                                result_artifact_id = NULL,
                                evidence_id = NULL,
                                failure_classification = ?,
                                failure_message = ?
                            WHERE
                                attempt_id = ?
                                AND state = ?
                            """,
                            (
                                RunAttemptState.INTERRUPTED.value,
                                attempt_terminal_at.isoformat(
                                    timespec="microseconds"
                                ),
                                "application_restart",
                                (
                                    "RUNNING attempt recovered as "
                                    "INTERRUPTED during application startup"
                                ),
                                current.attempt_id,
                                RunAttemptState.RUNNING.value,
                            ),
                        )

                        if cursor.rowcount != 1:
                            raise RuntimeError(
                                "RunAttempt restart recovery lost "
                                "its RUNNING precondition"
                            )

                    cursor = connection.execute(
                        """
                        UPDATE research_jobs
                        SET
                            state = ?,
                            terminal_at = ?,
                            failure_classification = ?,
                            failure_message = ?
                        WHERE
                            job_id = ?
                            AND state = ?
                            AND terminal_at IS NULL
                            AND completion_kind IS NULL
                            AND reused_attempt_id IS NULL
                            AND reused_evidence_id IS NULL
                            AND reused_result_artifact_id IS NULL
                        """,
                        (
                            ResearchJobState.INTERRUPTED.value,
                            effective_terminal_at.isoformat(
                                timespec="microseconds"
                            ),
                            "application_restart",
                            (
                                "RUNNING ResearchJob recovered as "
                                "INTERRUPTED during application startup"
                            ),
                            current.job_id,
                            ResearchJobState.RUNNING.value,
                        ),
                    )

                    if cursor.rowcount != 1:
                        raise RuntimeError(
                            "ResearchJob restart recovery lost "
                            "its RUNNING precondition"
                        )

                    other_active_count = (
                        connection.execute(
                            """
                            SELECT COUNT(*)
                            FROM research_jobs
                            WHERE
                                trial_id = ?
                                AND job_id <> ?
                                AND state IN ('QUEUED', 'RUNNING')
                            """,
                            (
                                current.trial_id,
                                current.job_id,
                            ),
                        ).fetchone()[0]
                    )

                    if other_active_count != 0:
                        raise RuntimeError(
                            "restart recovery found another "
                            "active ResearchJob for the Trial"
                        )

                    cursor = connection.execute(
                        """
                        UPDATE trials
                        SET
                            disposition = ?,
                            disposition_at = ?,
                            reused_attempt_id = NULL,
                            failure_classification = ?,
                            failure_message = ?
                        WHERE
                            trial_id = ?
                            AND disposition = ?
                        """,
                        (
                            TrialDisposition.INTERRUPTED.value,
                            effective_terminal_at.isoformat(
                                timespec="microseconds"
                            ),
                            "application_restart",
                            (
                                "Trial interrupted because its "
                                "RUNNING ResearchJob survived restart"
                            ),
                            current.trial_id,
                            TrialDisposition.PENDING.value,
                        ),
                    )

                    if cursor.rowcount != 1:
                        raise RuntimeError(
                            "restart recovery lost its "
                            "PENDING Trial precondition"
                        )

                    sequence_number = (
                        connection.execute(
                            """
                            SELECT
                                COALESCE(
                                    MAX(sequence_number),
                                    0
                                ) + 1
                            FROM trial_disposition_events
                            WHERE trial_id = ?
                            """,
                            (
                                current.trial_id,
                            ),
                        ).fetchone()[0]
                    )

                    event_id = canonical_fingerprint(
                        {
                            "trial_id": current.trial_id,
                            "sequence_number": (
                                sequence_number
                            ),
                            "new_disposition": (
                                TrialDisposition.INTERRUPTED.value
                            ),
                        },
                        schema=(
                            _TRIAL_DISPOSITION_EVENT_SCHEMA_ID
                        ),
                    )

                    connection.execute(
                        """
                        INSERT INTO trial_disposition_events (
                            event_id,
                            trial_id,
                            sequence_number,
                            previous_disposition,
                            new_disposition,
                            occurred_at,
                            causing_job_id,
                            reason_classification,
                            reason_message
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            event_id,
                            current.trial_id,
                            sequence_number,
                            TrialDisposition.PENDING.value,
                            TrialDisposition.INTERRUPTED.value,
                            effective_terminal_at.isoformat(
                                timespec="microseconds"
                            ),
                            current.job_id,
                            "application_restart",
                            (
                                "RUNNING ResearchJob interrupted "
                                "during application startup recovery"
                            ),
                        ),
                    )

                    recovered_job_ids.append(
                        current.job_id
                    )

                connection.commit()

            except Exception:
                connection.rollback()
                raise

        recovered = []

        for job_id in recovered_job_ids:
            job = self.load_research_job(
                job_id
            )

            if (
                job is None
                or job.state
                is not ResearchJobState.INTERRUPTED
            ):
                raise RuntimeError(
                    "committed ResearchJob restart recovery "
                    "could not be reloaded"
                )

            recovered.append(job)

        return tuple(recovered)

    def save_queued_research_job(
        self,
        job: ResearchJob,
    ) -> ResearchJob:
        """
        Reject supported lower-level ResearchJob insertion bypasses.

        Initial jobs belong to Start; retry jobs belong to Retry.
        """
        raise ValueError(
            "direct ResearchJob persistence is unsupported; "
            "use authoritative Start or Retry"
        )

    def _save_queued_research_job(
        self,
        job: ResearchJob,
    ) -> ResearchJob:
        """
        Legacy storage primitive retained only for internal/test
        persistence verification. It is not a supported lifecycle API.
        """

        if not isinstance(job, ResearchJob):
            raise TypeError(
                "job must be a ResearchJob"
            )

        if (
            job.state is not ResearchJobState.QUEUED
            or job.cancel_requested_at is not None
        ):
            raise ValueError(
                "new ResearchJob persistence requires "
                "an uncancelled QUEUED job"
            )

        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO research_jobs (
                            job_id,
                            trial_id,
                            state,
                            created_at,
                            claimed_at,
                            terminal_at,
                            worker_id,
                            cancel_requested_at,
                            attempt_id,
                            completion_kind,
                            reused_attempt_id,
                            reused_evidence_id,
                            reused_result_artifact_id,
                            failure_classification,
                            failure_message
                        ) VALUES (
                            ?, ?, ?, ?,
                            NULL, NULL, NULL, NULL, NULL,
                            NULL, NULL, NULL, NULL, NULL, NULL
                        )
                        """,
                        (
                            job.job_id,
                            job.trial_id,
                            job.state.value,
                            job.created_at.isoformat(
                                timespec="microseconds"
                            ),
                        ),
                    )
        except sqlite3.IntegrityError as error:
            existing = self.load_research_job(
                job.job_id
            )

            if (
                existing is not None
                and self._research_job_semantics(existing)
                == self._research_job_semantics(job)
            ):
                return existing

            raise ValueError(
                "QUEUED ResearchJob requires an existing "
                "Trial and unique non-conflicting job identity"
            ) from error

        return job

    def load_research_job(
        self,
        job_id: str,
    ) -> ResearchJob | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    job_id,
                    trial_id,
                    state,
                    created_at,
                    claimed_at,
                    terminal_at,
                    worker_id,
                    cancel_requested_at,
                    attempt_id,
                    completion_kind,
                    reused_attempt_id,
                    reused_evidence_id,
                    reused_result_artifact_id,
                    failure_classification,
                    failure_message
                FROM research_jobs
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        if row is None:
            return None

        return self._research_job_from_row(row)

    def load_research_job_reuse_dataset_lineage(
        self,
        job_id: str,
    ) -> tuple[str, str] | None:
        """
        Load durable requested/source DatasetReference artifact IDs
        for one registered exact-reuse completion.
        """

        if (
            not isinstance(job_id, str)
            or not job_id
        ):
            raise ValueError(
                "job_id must be a non-empty string"
            )

        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    requested_dataset_reference_artifact_id,
                    source_dataset_reference_artifact_id
                FROM research_job_reuse_dataset_lineage
                WHERE job_id = ?
                """,
                (job_id,),
            ).fetchone()

        if row is None:
            return None

        return (
            row[0],
            row[1],
        )

    def list_research_jobs_for_trial(
        self,
        trial_id: str,
    ) -> tuple[ResearchJob, ...]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                """
                SELECT
                    job_id,
                    trial_id,
                    state,
                    created_at,
                    claimed_at,
                    terminal_at,
                    worker_id,
                    cancel_requested_at,
                    attempt_id,
                    completion_kind,
                    reused_attempt_id,
                    reused_evidence_id,
                    reused_result_artifact_id,
                    failure_classification,
                    failure_message
                FROM research_jobs
                WHERE trial_id = ?
                ORDER BY created_at, job_id
                """,
                (trial_id,),
            ).fetchall()

        return tuple(
            self._research_job_from_row(row)
            for row in rows
        )

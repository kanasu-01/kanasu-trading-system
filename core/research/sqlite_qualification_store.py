"""SQLite persistence for the minimal M9.5 qualification gate."""

from contextlib import closing
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import sqlite3

from core.research.models.qualification import (
    CriterionOutcome,
    EvidenceValidity,
    FixedCandidateRevision,
    QualificationDecision,
    QualificationOutcome,
)
from core.research.models.qualification_policy import QualificationPolicy
from core.research.models.dataset_reference import (
    DATASET_REFERENCE_SCHEMA_ID,
)
from core.research.models.research_catalog import (
    ResearchArtifactKind,
)
from core.research.research_schema import initialize_research_schema


class SQLiteQualificationStore:
    """Persist policy activation, fixed candidates and append-only decisions."""

    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection:
            initialize_research_schema(connection)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def register_policy(
        self,
        policy: QualificationPolicy,
        *,
        created_at: datetime,
    ) -> QualificationPolicy:
        if not isinstance(policy, QualificationPolicy):
            raise TypeError("policy must be a QualificationPolicy")
        if created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")

        threshold_text = str(policy.net_profitable_trade_rate_threshold_pct)
        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO qualification_policies (
                            policy_id, version, threshold_text, created_at
                        ) VALUES (?, ?, ?, ?)
                        """,
                        (
                            policy.policy_id,
                            policy.version,
                            threshold_text,
                            created_at.isoformat(timespec="microseconds"),
                        ),
                    )
        except sqlite3.IntegrityError as error:
            existing = self.load_policy(policy.policy_id)
            if existing is not None and existing == policy:
                return existing
            raise ValueError(
                "qualification policy version or identity already exists"
            ) from error
        return policy

    def load_policy(self, policy_id: str) -> QualificationPolicy | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT version, threshold_text
                FROM qualification_policies
                WHERE policy_id = ?
                """,
                (policy_id,),
            ).fetchone()
        if row is None:
            return None
        policy = QualificationPolicy(row[0], Decimal(row[1]))
        if policy.policy_id != policy_id:
            raise RuntimeError("stored qualification policy identity mismatch")
        return policy

    def activate_policy(
        self,
        policy_id: str,
        *,
        activated_at: datetime,
    ) -> None:
        if activated_at.utcoffset() is None:
            raise ValueError("activated_at must be timezone-aware")

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN IMMEDIATE")
                target = connection.execute(
                    """
                    SELECT version
                    FROM qualification_policies
                    WHERE policy_id = ?
                    """,
                    (policy_id,),
                ).fetchone()
                if target is None:
                    raise ValueError("cannot activate an unregistered policy")

                current = connection.execute(
                    """
                    SELECT p.version
                    FROM qualification_policy_activations AS a
                    JOIN qualification_policies AS p
                      ON p.policy_id = a.policy_id
                    ORDER BY a.activation_sequence DESC
                    LIMIT 1
                    """
                ).fetchone()
                if current is not None and target[0] <= current[0]:
                    raise ValueError(
                        "policy activation must advance to a newer version"
                    )

                connection.execute(
                    """
                    INSERT INTO qualification_policy_activations (
                        policy_id, activated_at
                    ) VALUES (?, ?)
                    """,
                    (
                        policy_id,
                        activated_at.isoformat(timespec="microseconds"),
                    ),
                )
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()

    def load_active_policy(self) -> QualificationPolicy | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT policy_id
                FROM qualification_policy_activations
                ORDER BY activation_sequence DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        policy = self.load_policy(row[0])
        if policy is None:
            raise RuntimeError("active qualification policy is missing")
        return policy

    def save_candidate_revision(
        self,
        candidate: FixedCandidateRevision,
    ) -> FixedCandidateRevision:
        if not isinstance(candidate, FixedCandidateRevision):
            raise TypeError("candidate must be a FixedCandidateRevision")
        try:
            with closing(self._connect()) as connection:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO fixed_candidate_revisions (
                            candidate_revision_id,
                            study_revision_id,
                            trial_id,
                            experiment_spec_id,
                            parameter_configuration_fingerprint,
                            created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            candidate.candidate_revision_id,
                            candidate.study_revision_id,
                            candidate.trial_id,
                            candidate.experiment_spec_id,
                            candidate.parameter_configuration_fingerprint,
                            candidate.created_at.isoformat(timespec="microseconds"),
                        ),
                    )
        except sqlite3.IntegrityError as error:
            existing = self.load_candidate_revision(
                candidate.candidate_revision_id
            )
            if (
                existing is not None
                and existing.candidate_revision_id == candidate.candidate_revision_id
                and existing.study_revision_id == candidate.study_revision_id
                and existing.trial_id == candidate.trial_id
                and existing.experiment_spec_id == candidate.experiment_spec_id
                and existing.parameter_configuration_fingerprint
                == candidate.parameter_configuration_fingerprint
            ):
                return existing
            raise ValueError(
                "fixed CandidateRevision identity already has different data"
            ) from error
        return candidate

    def load_candidate_revision(
        self,
        candidate_revision_id: str,
    ) -> FixedCandidateRevision | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    candidate_revision_id,
                    study_revision_id,
                    trial_id,
                    experiment_spec_id,
                    parameter_configuration_fingerprint,
                    created_at
                FROM fixed_candidate_revisions
                WHERE candidate_revision_id = ?
                """,
                (candidate_revision_id,),
            ).fetchone()
        if row is None:
            return None
        return FixedCandidateRevision(
            candidate_revision_id=row[0],
            study_revision_id=row[1],
            trial_id=row[2],
            experiment_spec_id=row[3],
            parameter_configuration_fingerprint=row[4],
            created_at=datetime.fromisoformat(row[5]),
        )

    def append_decision(self, decision: QualificationDecision) -> None:
        if not isinstance(decision, QualificationDecision):
            raise TypeError("decision must be a QualificationDecision")
        with closing(self._connect()) as connection:
            try:
                with connection:
                    connection.execute(
                        """
                        INSERT INTO qualification_decisions (
                            decision_id,
                            created_at,
                            evaluator_version,
                            policy_id,
                            policy_version,
                            threshold_text,
                            study_revision_id,
                            trial_id,
                            candidate_revision_id,
                            attempt_id,
                            evidence_id,
                            result_artifact_id,
                            evidence_validity,
                            criterion_outcome,
                            outcome,
                            profitable_trade_count,
                            completed_trade_count,
                            rate_numerator,
                            rate_denominator,
                            reason
                        ) VALUES (
                            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                        )
                        """,
                        (
                            decision.decision_id,
                            decision.created_at.isoformat(timespec="microseconds"),
                            decision.evaluator_version,
                            decision.policy_id,
                            decision.policy_version,
                            decision.threshold_text,
                            decision.study_revision_id,
                            decision.trial_id,
                            decision.candidate_revision_id,
                            decision.attempt_id,
                            decision.evidence_id,
                            decision.result_artifact_id,
                            decision.evidence_validity.value,
                            decision.criterion_outcome.value,
                            decision.outcome.value,
                            decision.profitable_trade_count,
                            decision.completed_trade_count,
                            decision.rate_numerator,
                            decision.rate_denominator,
                            decision.reason,
                        ),
                    )
                    if decision.evidence_id is not None:
                        evidence_row = connection.execute(
                            """
                            SELECT artifact_references
                            FROM research_evidence
                            WHERE evidence_id = ?
                            """,
                            (decision.evidence_id,),
                        ).fetchone()

                        dataset_reference_ids = []
                        if evidence_row is not None:
                            try:
                                artifact_references = json.loads(
                                    evidence_row[0]
                                )
                            except (
                                TypeError,
                                ValueError,
                                json.JSONDecodeError,
                            ):
                                artifact_references = ()

                            if isinstance(
                                artifact_references,
                                list,
                            ):
                                for reference in artifact_references:
                                    if (
                                        not isinstance(reference, str)
                                        or not reference.startswith(
                                            "artifact:sha256:"
                                        )
                                    ):
                                        continue

                                    artifact_id = reference.removeprefix(
                                        "artifact:"
                                    )
                                    artifact_row = connection.execute(
                                        """
                                        SELECT artifact_kind, schema_id
                                        FROM research_artifacts
                                        WHERE artifact_id = ?
                                        """,
                                        (artifact_id,),
                                    ).fetchone()

                                    if artifact_row == (
                                        ResearchArtifactKind
                                        .DATASET_REFERENCE
                                        .value,
                                        DATASET_REFERENCE_SCHEMA_ID,
                                    ):
                                        dataset_reference_ids.append(
                                            artifact_id
                                        )

                        if len(dataset_reference_ids) == 1:
                            connection.execute(
                                """
                                INSERT INTO qualification_dataset_admissions (
                                    decision_id,
                                    dataset_reference_artifact_id
                                ) VALUES (?, ?)
                                """,
                                (
                                    decision.decision_id,
                                    dataset_reference_ids[0],
                                ),
                            )
            except sqlite3.IntegrityError as error:
                raise ValueError(
                    "QualificationDecision is append-only and must be unique"
                ) from error

    @staticmethod
    def _decision_from_row(row) -> QualificationDecision:
        return QualificationDecision(
            decision_id=row[0],
            created_at=datetime.fromisoformat(row[1]),
            evaluator_version=row[2],
            policy_id=row[3],
            policy_version=row[4],
            threshold_text=row[5],
            study_revision_id=row[6],
            trial_id=row[7],
            candidate_revision_id=row[8],
            attempt_id=row[9],
            evidence_id=row[10],
            result_artifact_id=row[11],
            evidence_validity=EvidenceValidity(row[12]),
            criterion_outcome=CriterionOutcome(row[13]),
            outcome=QualificationOutcome(row[14]),
            profitable_trade_count=row[15],
            completed_trade_count=row[16],
            rate_numerator=row[17],
            rate_denominator=row[18],
            reason=row[19],
        )

    def load_current_decision(
        self,
        trial_id: str,
    ) -> QualificationDecision | None:
        policy = self.load_active_policy()
        if policy is None:
            return None
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT
                    decision_id,
                    created_at,
                    evaluator_version,
                    policy_id,
                    policy_version,
                    threshold_text,
                    study_revision_id,
                    trial_id,
                    candidate_revision_id,
                    attempt_id,
                    evidence_id,
                    result_artifact_id,
                    evidence_validity,
                    criterion_outcome,
                    outcome,
                    profitable_trade_count,
                    completed_trade_count,
                    rate_numerator,
                    rate_denominator,
                    reason
                FROM qualification_decisions
                WHERE trial_id = ? AND policy_id = ?
                ORDER BY decision_sequence DESC
                LIMIT 1
                """,
                (trial_id, policy.policy_id),
            ).fetchone()
        return None if row is None else self._decision_from_row(row)

    def list_current_eligible_decisions(
        self,
        study_revision_id: str,
    ) -> tuple[QualificationDecision, ...]:
        """
        Return current-policy ELIGIBLE decisions for one StudyRevision.

        Active-policy resolution and latest-per-Trial selection share one
        SQLite read snapshot. Latest selection occurs before ELIGIBLE filtering
        so an older eligible decision cannot survive a later current-policy
        reject.
        """
        if not isinstance(study_revision_id, str) or not study_revision_id:
            raise ValueError(
                "study_revision_id must be a non-empty string"
            )

        with closing(self._connect()) as connection:
            try:
                connection.execute("BEGIN")
                policy_row = connection.execute(
                    """
                    SELECT policy_id
                    FROM qualification_policy_activations
                    ORDER BY activation_sequence DESC
                    LIMIT 1
                    """
                ).fetchone()
                if policy_row is None:
                    raise RuntimeError(
                        "no active QualificationPolicy; "
                        "current eligibility unavailable"
                    )

                rows = connection.execute(
                    """
                    SELECT
                        q.decision_id,
                        q.created_at,
                        q.evaluator_version,
                        q.policy_id,
                        q.policy_version,
                        q.threshold_text,
                        q.study_revision_id,
                        q.trial_id,
                        q.candidate_revision_id,
                        q.attempt_id,
                        q.evidence_id,
                        q.result_artifact_id,
                        q.evidence_validity,
                        q.criterion_outcome,
                        q.outcome,
                        q.profitable_trade_count,
                        q.completed_trade_count,
                        q.rate_numerator,
                        q.rate_denominator,
                        q.reason
                    FROM qualification_decisions AS q
                    JOIN (
                        SELECT
                            trial_id,
                            MAX(decision_sequence) AS decision_sequence
                        FROM qualification_decisions
                        WHERE policy_id = ?
                          AND study_revision_id = ?
                        GROUP BY trial_id
                    ) AS latest
                      ON latest.decision_sequence = q.decision_sequence
                    WHERE q.outcome = 'ELIGIBLE'
                    ORDER BY q.trial_id
                    """,
                    (policy_row[0], study_revision_id),
                ).fetchall()
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        return tuple(
            self._decision_from_row(row)
            for row in rows
        )

    def load_dataset_admission(
        self,
        decision_id: str,
    ) -> str | None:
        """Return the exact DatasetReference frozen with one qualification decision."""
        if not isinstance(decision_id, str) or not decision_id:
            raise ValueError("decision_id must be a non-empty string")
        with closing(self._connect()) as connection:
            row = connection.execute(
                """
                SELECT dataset_reference_artifact_id
                FROM qualification_dataset_admissions
                WHERE decision_id = ?
                """,
                (decision_id,),
            ).fetchone()
        return None if row is None else row[0]

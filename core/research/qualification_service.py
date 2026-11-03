"""Minimal M9.5 qualification of one selected registered historical Trial."""

from datetime import datetime
from fractions import Fraction
import sqlite3
from uuid import uuid4

from core.research.models.qualification import (
    CriterionOutcome,
    EvidenceValidity,
    FixedCandidateRevision,
    QUALIFICATION_EVALUATOR_VERSION,
    QualificationDecision,
    QualificationOutcome,
)
from core.research.models.registered_study import TrialDisposition
from core.research.study_aggregation import (
    StudyAggregationError,
    StudyAggregationService,
)


class QualificationOperationalError(RuntimeError):
    """Reliable qualification could not be completed because storage failed."""


def _is_operational_failure(error: BaseException) -> bool:
    current = error
    seen = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, sqlite3.Error):
            return True
        if isinstance(current, PermissionError):
            return True
        if isinstance(current, OSError) and not isinstance(
            current, FileNotFoundError
        ):
            return True
        current = current.__cause__ or current.__context__
    return False


class QualificationService:
    """Evaluate one explicitly selected Trial under the active policy."""

    def __init__(
        self,
        *,
        catalog_store,
        artifact_store,
        qualification_store,
    ):
        self.catalog_store = catalog_store
        self.artifact_store = artifact_store
        self.qualification_store = qualification_store

    def _append_noneligible(
        self,
        *,
        trial,
        policy,
        created_at: datetime,
        validity: EvidenceValidity,
        reason: str,
    ) -> QualificationDecision:
        outcome = (
            QualificationOutcome.INSUFFICIENT
            if validity is EvidenceValidity.INSUFFICIENT
            else QualificationOutcome.INVALID
        )
        decision = QualificationDecision(
            decision_id=f"qualification-{uuid4().hex}",
            created_at=created_at,
            evaluator_version=QUALIFICATION_EVALUATOR_VERSION,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            threshold_text=str(
                policy.net_profitable_trade_rate_threshold_pct
            ),
            study_revision_id=trial.study_revision_id,
            trial_id=trial.trial_id,
            evidence_validity=validity,
            criterion_outcome=CriterionOutcome.NOT_EVALUATED,
            outcome=outcome,
            reason=reason,
        )
        self.qualification_store.append_decision(decision)
        return decision

    @staticmethod
    def _lineage_from_snapshot(snapshot, trial, result_artifact_id):
        events = snapshot.disposition_events
        if not events or events[-1].causing_job_id is None:
            raise ValueError("verified Trial lacks terminal causing-job lineage")
        job = next(
            (
                item
                for item in snapshot.jobs
                if item.job_id == events[-1].causing_job_id
            ),
            None,
        )
        if job is None:
            raise ValueError("verified Trial causing job is absent")

        if trial.disposition is TrialDisposition.EXECUTED:
            attempt_id = job.attempt_id
            candidates = dict(snapshot.owned_attempts)
        else:
            attempt_id = job.reused_attempt_id
            candidates = dict(snapshot.reused_attempts)

        if attempt_id is None or attempt_id not in candidates:
            raise ValueError("verified Trial attempt lineage is absent")
        attempt = candidates[attempt_id]
        if attempt.evidence_id is None:
            raise ValueError("verified Trial evidence identity is absent")
        if attempt.result_artifact_id != result_artifact_id:
            raise ValueError("verified Trial result lineage changed")
        return attempt_id, attempt.evidence_id

    def evaluate_selected_trial(
        self,
        trial_id: str,
        *,
        evaluated_at: datetime,
    ) -> QualificationDecision:
        if evaluated_at.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")

        try:
            policy = self.qualification_store.load_active_policy()
            if policy is None:
                raise QualificationOperationalError(
                    "no active QualificationPolicy; no eligibility decision created"
                )
            trial = self.catalog_store.load_trial(trial_id)
        except QualificationOperationalError:
            raise
        except Exception as error:
            raise QualificationOperationalError(
                "qualification authority could not be loaded"
            ) from error

        if trial is None:
            raise ValueError("selected Trial is not registered")

        if trial.disposition not in {
            TrialDisposition.EXECUTED,
            TrialDisposition.REUSED,
        }:
            try:
                return self._append_noneligible(
                    trial=trial,
                    policy=policy,
                    created_at=evaluated_at,
                    validity=EvidenceValidity.INSUFFICIENT,
                    reason=(
                        "selected Trial has no completed result-bearing disposition"
                    ),
                )
            except Exception as error:
                raise QualificationOperationalError(
                    "INSUFFICIENT decision could not be persisted"
                ) from error

        verifier = StudyAggregationService(
            catalog_store=self.catalog_store,
            artifact_store=self.artifact_store,
        )

        try:
            verified = verifier.load_verified_trial_backtest(trial.trial_id)
            result_artifact_id = verified.result_artifact_id
            payload = verified.payload
            snapshot = self.catalog_store.load_research_trial_detail_snapshot(
                trial.trial_id
            )
            if snapshot is None:
                raise ValueError("selected Trial snapshot disappeared")
            attempt_id, evidence_id = self._lineage_from_snapshot(
                snapshot,
                trial,
                result_artifact_id,
            )
        except StudyAggregationError as error:
            if _is_operational_failure(error):
                raise QualificationOperationalError(
                    "saved Backtest evidence could not be reliably verified"
                ) from error
            try:
                return self._append_noneligible(
                    trial=trial,
                    policy=policy,
                    created_at=evaluated_at,
                    validity=EvidenceValidity.INVALID,
                    reason="saved Backtest evidence failed integrity or identity checks",
                )
            except Exception as persist_error:
                raise QualificationOperationalError(
                    "INVALID decision could not be persisted"
                ) from persist_error
        except Exception as error:
            if _is_operational_failure(error):
                raise QualificationOperationalError(
                    "saved Backtest evidence could not be reliably inspected"
                ) from error
            try:
                return self._append_noneligible(
                    trial=trial,
                    policy=policy,
                    created_at=evaluated_at,
                    validity=EvidenceValidity.INVALID,
                    reason="saved Backtest lineage could not be proven",
                )
            except Exception as persist_error:
                raise QualificationOperationalError(
                    "INVALID decision could not be persisted"
                ) from persist_error

        trades = tuple(payload["trades"])
        completed_count = len(trades)
        candidate = FixedCandidateRevision.from_verified_trial(
            trial,
            created_at=evaluated_at,
        )
        if completed_count == 0:
            decision = QualificationDecision(
                decision_id=f"qualification-{uuid4().hex}",
                created_at=evaluated_at,
                evaluator_version=QUALIFICATION_EVALUATOR_VERSION,
                policy_id=policy.policy_id,
                policy_version=policy.version,
                threshold_text=str(
                    policy.net_profitable_trade_rate_threshold_pct
                ),
                study_revision_id=trial.study_revision_id,
                trial_id=trial.trial_id,
                candidate_revision_id=candidate.candidate_revision_id,
                attempt_id=attempt_id,
                evidence_id=evidence_id,
                result_artifact_id=result_artifact_id,
                evidence_validity=EvidenceValidity.VALID,
                criterion_outcome=CriterionOutcome.NOT_EVALUATED,
                outcome=QualificationOutcome.INSUFFICIENT,
                profitable_trade_count=0,
                completed_trade_count=0,
                reason="verified Backtest has zero completed trades",
            )
            try:
                self.qualification_store.save_candidate_revision(candidate)
                self.qualification_store.append_decision(decision)
            except Exception as error:
                raise QualificationOperationalError(
                    "zero-trade INSUFFICIENT decision could not be persisted"
                ) from error
            return decision

        profitable_count = sum(trade["pnl"] > 0 for trade in trades)
        rate = Fraction(profitable_count * 100, completed_count)
        threshold = Fraction(
            policy.net_profitable_trade_rate_threshold_pct
        )
        criterion = (
            CriterionOutcome.SATISFIED
            if rate >= threshold
            else CriterionOutcome.NOT_SATISFIED
        )
        outcome = (
            QualificationOutcome.ELIGIBLE
            if criterion is CriterionOutcome.SATISFIED
            else QualificationOutcome.REJECTED
        )

        decision = QualificationDecision(
            decision_id=f"qualification-{uuid4().hex}",
            created_at=evaluated_at,
            evaluator_version=QUALIFICATION_EVALUATOR_VERSION,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            threshold_text=str(
                policy.net_profitable_trade_rate_threshold_pct
            ),
            study_revision_id=trial.study_revision_id,
            trial_id=trial.trial_id,
            candidate_revision_id=candidate.candidate_revision_id,
            attempt_id=attempt_id,
            evidence_id=evidence_id,
            result_artifact_id=result_artifact_id,
            evidence_validity=EvidenceValidity.VALID,
            criterion_outcome=criterion,
            outcome=outcome,
            profitable_trade_count=profitable_count,
            completed_trade_count=completed_count,
            rate_numerator=profitable_count * 100,
            rate_denominator=completed_count,
            reason=(
                "verified profitable-trade rate meets active policy threshold"
                if outcome is QualificationOutcome.ELIGIBLE
                else "verified profitable-trade rate is below active policy threshold"
            ),
        )

        try:
            self.qualification_store.save_candidate_revision(candidate)
            self.qualification_store.append_decision(decision)
        except Exception as error:
            raise QualificationOperationalError(
                "qualification decision could not be durably persisted"
            ) from error
        return decision

    def current_eligibility(self, trial_id: str) -> str | None:
        """Return the current eligible CandidateRevision for one Trial, if any."""
        try:
            decision = self.qualification_store.load_current_decision(trial_id)
        except Exception as error:
            raise QualificationOperationalError(
                "current qualification state could not be read"
            ) from error
        if decision is None or decision.outcome is not QualificationOutcome.ELIGIBLE:
            return None
        return decision.candidate_revision_id

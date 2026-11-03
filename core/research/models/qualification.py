"""Minimal fixed-candidate M9.5 qualification records."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from fractions import Fraction
import re

from core.research.reproducibility import canonical_fingerprint


_FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")
FIXED_CANDIDATE_REVISION_SCHEMA_ID = "kanasu.fixed-candidate-revision.v1"
QUALIFICATION_DECISION_SCHEMA_ID = "kanasu.qualification-decision.v1"
QUALIFICATION_EVALUATOR_VERSION = "m9.5-v1"


class EvidenceValidity(str, Enum):
    VALID = "VALID"
    INSUFFICIENT = "INSUFFICIENT"
    INVALID = "INVALID"


class CriterionOutcome(str, Enum):
    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    NOT_EVALUATED = "NOT_EVALUATED"


class QualificationOutcome(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    REJECTED = "REJECTED"
    INSUFFICIENT = "INSUFFICIENT"
    INVALID = "INVALID"


def _require_fingerprint(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not _FINGERPRINT_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field_name} must use sha256:<64 lowercase hexadecimal>"
        )


def _require_nonempty(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True)
class FixedCandidateRevision:
    candidate_revision_id: str
    study_revision_id: str
    trial_id: str
    experiment_spec_id: str
    parameter_configuration_fingerprint: str
    created_at: datetime
    identity_schema: str = FIXED_CANDIDATE_REVISION_SCHEMA_ID

    @classmethod
    def from_verified_trial(cls, trial, *, created_at: datetime):
        if created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if trial.experiment_spec_id is None:
            raise ValueError("verified fixed candidate requires ExperimentSpec")

        payload = {
            "study_revision_id": trial.study_revision_id,
            "trial_id": trial.trial_id,
            "experiment_spec_id": trial.experiment_spec_id,
            "parameter_configuration_fingerprint": (
                trial.parameter_configuration_fingerprint
            ),
        }
        candidate_revision_id = canonical_fingerprint(
            payload,
            schema=FIXED_CANDIDATE_REVISION_SCHEMA_ID,
        )
        return cls(
            candidate_revision_id=candidate_revision_id,
            study_revision_id=trial.study_revision_id,
            trial_id=trial.trial_id,
            experiment_spec_id=trial.experiment_spec_id,
            parameter_configuration_fingerprint=(
                trial.parameter_configuration_fingerprint
            ),
            created_at=created_at,
        )

    def __post_init__(self) -> None:
        for name in (
            "candidate_revision_id",
            "study_revision_id",
            "trial_id",
            "experiment_spec_id",
            "parameter_configuration_fingerprint",
        ):
            _require_fingerprint(getattr(self, name), name)
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if self.identity_schema != FIXED_CANDIDATE_REVISION_SCHEMA_ID:
            raise ValueError("unexpected fixed CandidateRevision schema")


@dataclass(frozen=True)
class QualificationDecision:
    decision_id: str
    created_at: datetime
    evaluator_version: str
    policy_id: str
    policy_version: int
    threshold_text: str
    study_revision_id: str
    trial_id: str
    evidence_validity: EvidenceValidity
    criterion_outcome: CriterionOutcome
    outcome: QualificationOutcome
    reason: str
    candidate_revision_id: str | None = None
    attempt_id: str | None = None
    evidence_id: str | None = None
    result_artifact_id: str | None = None
    profitable_trade_count: int | None = None
    completed_trade_count: int | None = None
    rate_numerator: int | None = None
    rate_denominator: int | None = None
    identity_schema: str = QUALIFICATION_DECISION_SCHEMA_ID

    def __post_init__(self) -> None:
        _require_nonempty(self.decision_id, "decision_id")
        _require_nonempty(self.evaluator_version, "evaluator_version")
        _require_fingerprint(self.policy_id, "policy_id")
        _require_fingerprint(self.study_revision_id, "study_revision_id")
        _require_fingerprint(self.trial_id, "trial_id")
        if self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if type(self.policy_version) is not int or self.policy_version <= 0:
            raise ValueError("policy_version must be a positive integer")
        _require_nonempty(self.threshold_text, "threshold_text")
        _require_nonempty(self.reason, "reason")
        if self.identity_schema != QUALIFICATION_DECISION_SCHEMA_ID:
            raise ValueError("unexpected QualificationDecision schema")

        if self.candidate_revision_id is not None:
            _require_fingerprint(
                self.candidate_revision_id,
                "candidate_revision_id",
            )
        if self.result_artifact_id is not None:
            _require_fingerprint(self.result_artifact_id, "result_artifact_id")
        for name in ("attempt_id", "evidence_id"):
            value = getattr(self, name)
            if value is not None:
                _require_nonempty(value, name)

        counts = (
            self.profitable_trade_count,
            self.completed_trade_count,
        )
        rate = (self.rate_numerator, self.rate_denominator)

        if self.outcome in {
            QualificationOutcome.ELIGIBLE,
            QualificationOutcome.REJECTED,
        }:
            if self.evidence_validity is not EvidenceValidity.VALID:
                raise ValueError("economic decision requires VALID evidence")
            if any(value is None for value in counts + rate):
                raise ValueError("economic decision requires exact trade-rate counts")
            if self.completed_trade_count <= 0 or self.rate_denominator <= 0:
                raise ValueError("economic decision requires positive denominator")
            if self.profitable_trade_count < 0:
                raise ValueError("profitable_trade_count cannot be negative")
            if self.profitable_trade_count > self.completed_trade_count:
                raise ValueError("profitable trades cannot exceed completed trades")
            if self.rate_numerator != self.profitable_trade_count * 100:
                raise ValueError("rate numerator must equal profitable_count * 100")
            if self.rate_denominator != self.completed_trade_count:
                raise ValueError("rate denominator must equal completed_trade_count")
            if self.candidate_revision_id is None:
                raise ValueError("economic decision requires fixed CandidateRevision")
            expected_criterion = (
                CriterionOutcome.SATISFIED
                if self.outcome is QualificationOutcome.ELIGIBLE
                else CriterionOutcome.NOT_SATISFIED
            )
            if self.criterion_outcome is not expected_criterion:
                raise ValueError("criterion and qualification outcome disagree")
            return

        if self.criterion_outcome is not CriterionOutcome.NOT_EVALUATED:
            raise ValueError("non-economic outcome cannot evaluate criterion")

        if self.outcome is QualificationOutcome.INVALID:
            if self.evidence_validity is not EvidenceValidity.INVALID:
                raise ValueError("INVALID outcome requires INVALID evidence")
            if any(value is not None for value in counts + rate):
                raise ValueError("INVALID decision must not invent trade-rate counts")
            return

        if self.outcome is not QualificationOutcome.INSUFFICIENT:
            raise ValueError("unsupported qualification outcome")

        if self.evidence_validity is EvidenceValidity.INSUFFICIENT:
            if any(value is not None for value in counts + rate):
                raise ValueError("missing evidence must not invent trade-rate counts")
            return

        if self.evidence_validity is not EvidenceValidity.VALID:
            raise ValueError("INSUFFICIENT outcome has inconsistent evidence state")
        if self.profitable_trade_count != 0 or self.completed_trade_count != 0:
            raise ValueError("VALID-but-INSUFFICIENT means verified zero trades")
        if any(value is not None for value in rate):
            raise ValueError("zero-trade rate is undefined")
        if self.candidate_revision_id is None:
            raise ValueError("verified zero-trade result requires CandidateRevision")

    @property
    def exact_rate(self) -> Fraction | None:
        if self.rate_numerator is None or self.rate_denominator is None:
            return None
        return Fraction(self.rate_numerator, self.rate_denominator)

"""M9.4 registered Study, Trial and ResearchJob record models."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re


_FINGERPRINT_PATTERN = re.compile(
    r"^sha256:[0-9a-f]{64}$"
)

STUDY_REVISION_SCHEMA_ID = "kanasu.study-revision.v1"
TRIAL_IDENTITY_SCHEMA_ID = "kanasu.trial.v1"
TRIAL_MEMBERSHIP_EVIDENCE_SCHEMA_ID = (
    "kanasu.trial-membership-evidence.v1"
)
INITIAL_RESEARCH_JOB_SCHEMA_ID = (
    "kanasu.initial-research-job.v1"
)
RESEARCH_MAX_WORKERS_SAFETY_CEILING = 16


class EvidenceReusePolicy(str, Enum):
    ALLOW_EXACT_ACCEPTED = "ALLOW_EXACT_ACCEPTED"
    FORCE_NEW_EXECUTION = "FORCE_NEW_EXECUTION"


class TrialDisposition(str, Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    REUSED = "REUSED"
    INVALID = "INVALID"
    INSUFFICIENT = "INSUFFICIENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


class ResearchJobState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


class ResearchJobCompletionKind(str, Enum):
    EXECUTED = "EXECUTED"
    REUSED = "REUSED"


_TERMINAL_JOB_STATES = {
    ResearchJobState.SUCCEEDED,
    ResearchJobState.FAILED,
    ResearchJobState.CANCELLED,
    ResearchJobState.INTERRUPTED,
}


def _require_nonempty_string(
    value: str,
    field_name: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"{field_name} must be a non-empty string"
        )


def _require_optional_string(
    value: str | None,
    field_name: str,
) -> None:
    if value is not None:
        _require_nonempty_string(value, field_name)


def _require_fingerprint(
    value: str,
    field_name: str,
) -> None:
    if (
        not isinstance(value, str)
        or not _FINGERPRINT_PATTERN.fullmatch(value)
    ):
        raise ValueError(
            f"{field_name} must use "
            "sha256:<64 lowercase hexadecimal>"
        )


def _require_optional_fingerprint(
    value: str | None,
    field_name: str,
) -> None:
    if value is not None:
        _require_fingerprint(value, field_name)


def _require_aware_datetime(
    value: datetime,
    field_name: str,
) -> None:
    if not isinstance(value, datetime):
        raise TypeError(
            f"{field_name} must be a datetime"
        )
    if value.utcoffset() is None:
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )


def _require_optional_aware_datetime(
    value: datetime | None,
    field_name: str,
) -> None:
    if value is not None:
        _require_aware_datetime(value, field_name)


@dataclass(frozen=True)
class Study:
    study_id: str
    created_at: datetime
    display_title: str
    archived: bool = False

    def __post_init__(self) -> None:
        _require_nonempty_string(
            self.study_id,
            "study_id",
        )
        _require_aware_datetime(
            self.created_at,
            "created_at",
        )
        _require_nonempty_string(
            self.display_title,
            "display_title",
        )
        if type(self.archived) is not bool:
            raise TypeError("archived must be a bool")


@dataclass(frozen=True)
class StudyRevision:
    study_revision_id: str
    study_id: str
    revision_number: int
    plan_artifact_id: str
    repository_revision: str
    evidence_reuse_policy: EvidenceReusePolicy
    registered_at: datetime
    initial_batch_started_at: datetime | None = None
    identity_schema: str = STUDY_REVISION_SCHEMA_ID

    def __post_init__(self) -> None:
        _require_fingerprint(
            self.study_revision_id,
            "study_revision_id",
        )
        _require_nonempty_string(
            self.study_id,
            "study_id",
        )

        if (
            type(self.revision_number) is not int
            or self.revision_number <= 0
        ):
            raise ValueError(
                "revision_number must be a positive integer"
            )

        _require_fingerprint(
            self.plan_artifact_id,
            "plan_artifact_id",
        )
        _require_nonempty_string(
            self.repository_revision,
            "repository_revision",
        )

        if not isinstance(
            self.evidence_reuse_policy,
            EvidenceReusePolicy,
        ):
            raise TypeError(
                "evidence_reuse_policy must be an "
                "EvidenceReusePolicy"
            )

        _require_aware_datetime(
            self.registered_at,
            "registered_at",
        )
        _require_optional_aware_datetime(
            self.initial_batch_started_at,
            "initial_batch_started_at",
        )

        if (
            self.initial_batch_started_at is not None
            and self.initial_batch_started_at
            < self.registered_at
        ):
            raise ValueError(
                "initial_batch_started_at cannot precede "
                "registered_at"
            )

        if (
            self.identity_schema
            != STUDY_REVISION_SCHEMA_ID
        ):
            raise ValueError(
                "identity_schema must be "
                f"{STUDY_REVISION_SCHEMA_ID}"
            )


@dataclass(frozen=True)
class Trial:
    trial_id: str
    study_revision_id: str
    instrument_id: str
    membership_episode_start: datetime
    membership_episode_end: datetime
    membership_evidence_fingerprint: str
    membership_evidence_artifact_id: str
    parameter_configuration_fingerprint: str
    registered_at: datetime
    disposition: TrialDisposition
    disposition_at: datetime
    experiment_spec_id: str | None = None
    reused_attempt_id: str | None = None
    failure_classification: str | None = None
    failure_message: str | None = None
    identity_schema: str = TRIAL_IDENTITY_SCHEMA_ID

    def __post_init__(self) -> None:
        _require_fingerprint(
            self.trial_id,
            "trial_id",
        )
        _require_fingerprint(
            self.study_revision_id,
            "study_revision_id",
        )
        _require_nonempty_string(
            self.instrument_id,
            "instrument_id",
        )
        _require_aware_datetime(
            self.membership_episode_start,
            "membership_episode_start",
        )
        _require_aware_datetime(
            self.membership_episode_end,
            "membership_episode_end",
        )

        if (
            self.membership_episode_end
            <= self.membership_episode_start
        ):
            raise ValueError(
                "membership_episode_end must be after "
                "membership_episode_start"
            )

        _require_fingerprint(
            self.membership_evidence_fingerprint,
            "membership_evidence_fingerprint",
        )
        _require_fingerprint(
            self.membership_evidence_artifact_id,
            "membership_evidence_artifact_id",
        )

        if (
            self.membership_evidence_artifact_id
            != self.membership_evidence_fingerprint
        ):
            raise ValueError(
                "membership evidence artifact identity must "
                "match membership_evidence_fingerprint"
            )

        _require_fingerprint(
            self.parameter_configuration_fingerprint,
            "parameter_configuration_fingerprint",
        )
        _require_aware_datetime(
            self.registered_at,
            "registered_at",
        )

        if not isinstance(
            self.disposition,
            TrialDisposition,
        ):
            raise TypeError(
                "disposition must be a TrialDisposition"
            )

        _require_aware_datetime(
            self.disposition_at,
            "disposition_at",
        )

        if self.disposition_at < self.registered_at:
            raise ValueError(
                "disposition_at cannot precede registered_at"
            )

        _require_optional_fingerprint(
            self.experiment_spec_id,
            "experiment_spec_id",
        )
        _require_optional_string(
            self.reused_attempt_id,
            "reused_attempt_id",
        )
        _require_optional_string(
            self.failure_classification,
            "failure_classification",
        )
        _require_optional_string(
            self.failure_message,
            "failure_message",
        )

        if self.identity_schema != TRIAL_IDENTITY_SCHEMA_ID:
            raise ValueError(
                "identity_schema must be "
                f"{TRIAL_IDENTITY_SCHEMA_ID}"
            )


@dataclass(frozen=True)
class TrialDispositionEvent:
    event_id: str
    trial_id: str
    sequence_number: int
    previous_disposition: TrialDisposition | None
    new_disposition: TrialDisposition
    occurred_at: datetime
    causing_job_id: str | None = None
    reason_classification: str | None = None
    reason_message: str | None = None

    def __post_init__(self) -> None:
        _require_nonempty_string(
            self.event_id,
            "event_id",
        )
        _require_fingerprint(
            self.trial_id,
            "trial_id",
        )

        if (
            type(self.sequence_number) is not int
            or self.sequence_number <= 0
        ):
            raise ValueError(
                "sequence_number must be a positive integer"
            )

        if (
            self.previous_disposition is not None
            and not isinstance(
                self.previous_disposition,
                TrialDisposition,
            )
        ):
            raise TypeError(
                "previous_disposition must be a "
                "TrialDisposition or None"
            )

        if not isinstance(
            self.new_disposition,
            TrialDisposition,
        ):
            raise TypeError(
                "new_disposition must be a TrialDisposition"
            )

        _require_aware_datetime(
            self.occurred_at,
            "occurred_at",
        )
        _require_optional_string(
            self.causing_job_id,
            "causing_job_id",
        )
        _require_optional_string(
            self.reason_classification,
            "reason_classification",
        )
        _require_optional_string(
            self.reason_message,
            "reason_message",
        )


@dataclass(frozen=True)
class ResearchJob:
    job_id: str
    trial_id: str
    state: ResearchJobState
    created_at: datetime
    claimed_at: datetime | None = None
    terminal_at: datetime | None = None
    worker_id: str | None = None
    cancel_requested_at: datetime | None = None
    attempt_id: str | None = None
    completion_kind: ResearchJobCompletionKind | None = None
    reused_attempt_id: str | None = None
    reused_evidence_id: str | None = None
    reused_result_artifact_id: str | None = None
    failure_classification: str | None = None
    failure_message: str | None = None

    def __post_init__(self) -> None:
        _require_nonempty_string(
            self.job_id,
            "job_id",
        )
        _require_fingerprint(
            self.trial_id,
            "trial_id",
        )

        if not isinstance(
            self.state,
            ResearchJobState,
        ):
            raise TypeError(
                "state must be a ResearchJobState"
            )

        _require_aware_datetime(
            self.created_at,
            "created_at",
        )
        _require_optional_aware_datetime(
            self.claimed_at,
            "claimed_at",
        )
        _require_optional_aware_datetime(
            self.terminal_at,
            "terminal_at",
        )
        _require_optional_aware_datetime(
            self.cancel_requested_at,
            "cancel_requested_at",
        )

        for field_name, value in (
            ("claimed_at", self.claimed_at),
            ("terminal_at", self.terminal_at),
            (
                "cancel_requested_at",
                self.cancel_requested_at,
            ),
        ):
            if (
                value is not None
                and value < self.created_at
            ):
                raise ValueError(
                    f"{field_name} cannot precede created_at"
                )

        _require_optional_string(
            self.worker_id,
            "worker_id",
        )
        _require_optional_string(
            self.attempt_id,
            "attempt_id",
        )
        _require_optional_string(
            self.reused_attempt_id,
            "reused_attempt_id",
        )
        _require_optional_string(
            self.reused_evidence_id,
            "reused_evidence_id",
        )
        _require_optional_fingerprint(
            self.reused_result_artifact_id,
            "reused_result_artifact_id",
        )
        _require_optional_string(
            self.failure_classification,
            "failure_classification",
        )
        _require_optional_string(
            self.failure_message,
            "failure_message",
        )

        if (
            self.completion_kind is not None
            and not isinstance(
                self.completion_kind,
                ResearchJobCompletionKind,
            )
        ):
            raise TypeError(
                "completion_kind must be a "
                "ResearchJobCompletionKind or None"
            )

        terminal = (
            self.state in _TERMINAL_JOB_STATES
        )

        if terminal != (self.terminal_at is not None):
            raise ValueError(
                "terminal ResearchJob state requires "
                "terminal_at and non-terminal state forbids it"
            )

        if self.state is ResearchJobState.QUEUED:
            if (
                self.claimed_at is not None
                or self.worker_id is not None
                or self.attempt_id is not None
                or self.completion_kind is not None
            ):
                raise ValueError(
                    "QUEUED ResearchJob cannot already be "
                    "claimed, attempted or completed"
                )

        if self.state is ResearchJobState.RUNNING:
            if (
                self.claimed_at is None
                or self.worker_id is None
            ):
                raise ValueError(
                    "RUNNING ResearchJob requires claim "
                    "time and worker identity"
                )

        if self.state is ResearchJobState.SUCCEEDED:
            if self.completion_kind is None:
                raise ValueError(
                    "SUCCEEDED ResearchJob requires "
                    "completion_kind"
                )

            if (
                self.completion_kind
                is ResearchJobCompletionKind.EXECUTED
            ):
                if self.attempt_id is None:
                    raise ValueError(
                        "EXECUTED ResearchJob requires "
                        "attempt_id"
                    )

                if any(
                    value is not None
                    for value in (
                        self.reused_attempt_id,
                        self.reused_evidence_id,
                        self.reused_result_artifact_id,
                    )
                ):
                    raise ValueError(
                        "EXECUTED ResearchJob cannot carry "
                        "reused-source references"
                    )

            if (
                self.completion_kind
                is ResearchJobCompletionKind.REUSED
            ):
                if self.attempt_id is not None:
                    raise ValueError(
                        "REUSED ResearchJob cannot create "
                        "a new attempt_id"
                    )

                if any(
                    value is None
                    for value in (
                        self.reused_attempt_id,
                        self.reused_evidence_id,
                        self.reused_result_artifact_id,
                    )
                ):
                    raise ValueError(
                        "REUSED ResearchJob requires exact "
                        "attempt, evidence and result sources"
                    )

        elif self.completion_kind is not None:
            raise ValueError(
                "only SUCCEEDED ResearchJob may have "
                "completion_kind"
            )


@dataclass(frozen=True)
class ResearchQueueSnapshot:
    """Truthful Trial and ResearchJob counts for one StudyRevision."""

    study_revision_id: str
    initial_batch_started_at: datetime | None
    total_registered_trials: int

    pending_trials: int = 0
    executed_trials: int = 0
    reused_trials: int = 0
    invalid_trials: int = 0
    insufficient_trials: int = 0
    failed_trials: int = 0
    cancelled_trials: int = 0
    interrupted_trials: int = 0

    queued_jobs: int = 0
    running_jobs: int = 0
    succeeded_jobs: int = 0
    failed_jobs: int = 0
    cancelled_jobs: int = 0
    interrupted_jobs: int = 0

    def __post_init__(self) -> None:
        _require_fingerprint(
            self.study_revision_id,
            "study_revision_id",
        )

        _require_optional_aware_datetime(
            self.initial_batch_started_at,
            "initial_batch_started_at",
        )

        count_fields = (
            "total_registered_trials",
            "pending_trials",
            "executed_trials",
            "reused_trials",
            "invalid_trials",
            "insufficient_trials",
            "failed_trials",
            "cancelled_trials",
            "interrupted_trials",
            "queued_jobs",
            "running_jobs",
            "succeeded_jobs",
            "failed_jobs",
            "cancelled_jobs",
            "interrupted_jobs",
        )

        for field_name in count_fields:
            value = getattr(
                self,
                field_name,
            )

            if (
                type(value) is not int
                or value < 0
            ):
                raise ValueError(
                    f"{field_name} must be a non-negative integer"
                )

        trial_count = sum(
            (
                self.pending_trials,
                self.executed_trials,
                self.reused_trials,
                self.invalid_trials,
                self.insufficient_trials,
                self.failed_trials,
                self.cancelled_trials,
                self.interrupted_trials,
            )
        )

        if trial_count != self.total_registered_trials:
            raise ValueError(
                "Trial disposition counts must equal "
                "total_registered_trials"
            )

    @property
    def total_jobs(self) -> int:
        return sum(
            (
                self.queued_jobs,
                self.running_jobs,
                self.succeeded_jobs,
                self.failed_jobs,
                self.cancelled_jobs,
                self.interrupted_jobs,
            )
        )

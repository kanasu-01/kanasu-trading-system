"""Immutable M9.2 research-catalog record models."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
import re


_FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")

EXPERIMENT_SPEC_SCHEMA_ID = "kanasu.experiment-spec.v1"


class ResearchArtifactKind(str, Enum):
    BACKTEST_RUN_MANIFEST = "BACKTEST_RUN_MANIFEST"
    BACKTEST_RESULT = "BACKTEST_RESULT"
    DATASET_REFERENCE = "DATASET_REFERENCE"
    STUDY_REVISION_PLAN = "STUDY_REVISION_PLAN"
    TRIAL_MEMBERSHIP_EVIDENCE = "TRIAL_MEMBERSHIP_EVIDENCE"


class ComputationKind(str, Enum):
    BACKTEST = "BACKTEST"


class RunAttemptState(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


_TERMINAL_ATTEMPT_STATES = {
    RunAttemptState.SUCCEEDED,
    RunAttemptState.FAILED,
    RunAttemptState.CANCELLED,
    RunAttemptState.INTERRUPTED,
}


def _require_nonempty_string(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_fingerprint(value: str, field_name: str) -> None:
    if (
        not isinstance(value, str)
        or not _FINGERPRINT_PATTERN.fullmatch(value)
    ):
        raise ValueError(
            f"{field_name} must use "
            "sha256:<64 lowercase hexadecimal>"
        )


def _require_aware_datetime(value: datetime, field_name: str) -> None:
    if not isinstance(value, datetime):
        raise TypeError(f"{field_name} must be a datetime")
    if value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _require_optional_string(
    value: str | None,
    field_name: str,
) -> None:
    if value is not None:
        _require_nonempty_string(value, field_name)


def _require_relative_posix_path(value: str) -> None:
    _require_nonempty_string(value, "relative_path")

    if "\\" in value:
        raise ValueError(
            "relative_path must use machine-independent POSIX separators"
        )

    path = PurePosixPath(value)

    if (
        path.is_absolute()
        or value == "."
        or ".." in path.parts
    ):
        raise ValueError(
            "relative_path must be a safe relative POSIX path"
        )


@dataclass(frozen=True)
class ResearchArtifact:
    artifact_id: str
    artifact_kind: ResearchArtifactKind
    schema_id: str
    relative_path: str
    byte_count: int
    created_at: datetime

    def __post_init__(self) -> None:
        _require_fingerprint(self.artifact_id, "artifact_id")

        if not isinstance(self.artifact_kind, ResearchArtifactKind):
            raise TypeError(
                "artifact_kind must be a ResearchArtifactKind"
            )

        _require_nonempty_string(self.schema_id, "schema_id")
        _require_relative_posix_path(self.relative_path)

        if type(self.byte_count) is not int or self.byte_count < 0:
            raise ValueError(
                "byte_count must be a non-negative integer"
            )

        _require_aware_datetime(self.created_at, "created_at")


@dataclass(frozen=True)
class ExperimentSpec:
    experiment_spec_id: str
    computation_kind: ComputationKind
    manifest_artifact_id: str
    dataset_fingerprint: str
    configuration_fingerprint: str
    repository_revision: str
    created_at: datetime
    identity_schema: str = EXPERIMENT_SPEC_SCHEMA_ID

    def __post_init__(self) -> None:
        _require_fingerprint(
            self.experiment_spec_id,
            "experiment_spec_id",
        )

        if not isinstance(self.computation_kind, ComputationKind):
            raise TypeError(
                "computation_kind must be a ComputationKind"
            )

        _require_fingerprint(
            self.manifest_artifact_id,
            "manifest_artifact_id",
        )
        _require_fingerprint(
            self.dataset_fingerprint,
            "dataset_fingerprint",
        )
        _require_fingerprint(
            self.configuration_fingerprint,
            "configuration_fingerprint",
        )
        _require_nonempty_string(
            self.repository_revision,
            "repository_revision",
        )
        _require_aware_datetime(self.created_at, "created_at")

        if self.identity_schema != EXPERIMENT_SPEC_SCHEMA_ID:
            raise ValueError(
                "identity_schema must be "
                f"{EXPERIMENT_SPEC_SCHEMA_ID}"
            )


@dataclass(frozen=True)
class RunAttempt:
    attempt_id: str
    experiment_spec_id: str
    state: RunAttemptState
    created_at: datetime
    terminal_at: datetime | None = None
    runtime_session_id: str | None = None
    result_artifact_id: str | None = None
    evidence_id: str | None = None
    failure_classification: str | None = None
    failure_message: str | None = None

    def __post_init__(self) -> None:
        _require_nonempty_string(self.attempt_id, "attempt_id")
        _require_fingerprint(
            self.experiment_spec_id,
            "experiment_spec_id",
        )

        if not isinstance(self.state, RunAttemptState):
            raise TypeError("state must be a RunAttemptState")

        _require_aware_datetime(self.created_at, "created_at")

        if self.terminal_at is not None:
            _require_aware_datetime(
                self.terminal_at,
                "terminal_at",
            )
            if self.terminal_at < self.created_at:
                raise ValueError(
                    "terminal_at cannot precede created_at"
                )

        if (
            self.state in _TERMINAL_ATTEMPT_STATES
            and self.terminal_at is None
        ):
            raise ValueError(
                "terminal RunAttempt state requires terminal_at"
            )

        if (
            self.state not in _TERMINAL_ATTEMPT_STATES
            and self.terminal_at is not None
        ):
            raise ValueError(
                "non-terminal RunAttempt state cannot have terminal_at"
            )

        _require_optional_string(
            self.runtime_session_id,
            "runtime_session_id",
        )

        if self.result_artifact_id is not None:
            _require_fingerprint(
                self.result_artifact_id,
                "result_artifact_id",
            )

        _require_optional_string(
            self.evidence_id,
            "evidence_id",
        )
        _require_optional_string(
            self.failure_classification,
            "failure_classification",
        )
        _require_optional_string(
            self.failure_message,
            "failure_message",
        )

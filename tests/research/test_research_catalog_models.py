from datetime import datetime, timedelta, timezone

import pytest

from core.research.models.research_catalog import (
    ComputationKind,
    EXPERIMENT_SPEC_SCHEMA_ID,
    ExperimentSpec,
    ResearchArtifact,
    ResearchArtifactKind,
    RunAttempt,
    RunAttemptState,
)


INDIA = timezone(timedelta(hours=5, minutes=30))
CREATED_AT = datetime(
    2026,
    9,
    27,
    8,
    45,
    tzinfo=INDIA,
)


def fingerprint(character: str) -> str:
    return f"sha256:{character * 64}"


def artifact(**changes) -> ResearchArtifact:
    values = {
        "artifact_id": fingerprint("a"),
        "artifact_kind": (
            ResearchArtifactKind.BACKTEST_RUN_MANIFEST
        ),
        "schema_id": "kanasu.backtest-run-manifest.v1",
        "relative_path": (
            "sha256/aa/"
            + "a" * 64
            + ".json"
        ),
        "byte_count": 123,
        "created_at": CREATED_AT,
    }
    values.update(changes)
    return ResearchArtifact(**values)


def experiment_spec(**changes) -> ExperimentSpec:
    values = {
        "experiment_spec_id": fingerprint("b"),
        "computation_kind": ComputationKind.BACKTEST,
        "manifest_artifact_id": fingerprint("a"),
        "dataset_fingerprint": fingerprint("c"),
        "configuration_fingerprint": fingerprint("d"),
        "repository_revision": "4eb28d8200214bb1",
        "created_at": CREATED_AT,
    }
    values.update(changes)
    return ExperimentSpec(**values)


def run_attempt(**changes) -> RunAttempt:
    values = {
        "attempt_id": "attempt-001",
        "experiment_spec_id": fingerprint("b"),
        "state": RunAttemptState.RUNNING,
        "created_at": CREATED_AT,
    }
    values.update(changes)
    return RunAttempt(**values)


def test_research_artifact_is_immutable():
    record = artifact()

    assert (
        record.artifact_kind
        is ResearchArtifactKind.BACKTEST_RUN_MANIFEST
    )

    with pytest.raises(AttributeError):
        record.byte_count = 999


@pytest.mark.parametrize(
    "relative_path",
    [
        "/absolute/result.json",
        "../escape/result.json",
        "nested/../../escape.json",
        r"windows\machine\path.json",
        ".",
    ],
)
def test_research_artifact_rejects_nonportable_or_unsafe_paths(
    relative_path,
):
    with pytest.raises(ValueError, match="relative_path"):
        artifact(relative_path=relative_path)


@pytest.mark.parametrize(
    "byte_count",
    [-1, 1.5, True],
)
def test_research_artifact_requires_nonnegative_integer_byte_count(
    byte_count,
):
    with pytest.raises(ValueError, match="byte_count"):
        artifact(byte_count=byte_count)


def test_research_artifact_requires_timezone_aware_creation_time():
    with pytest.raises(ValueError, match="timezone-aware"):
        artifact(created_at=CREATED_AT.replace(tzinfo=None))


def test_experiment_spec_preserves_distinct_identity_inputs():
    spec = experiment_spec()

    assert spec.identity_schema == EXPERIMENT_SPEC_SCHEMA_ID
    assert spec.computation_kind is ComputationKind.BACKTEST
    assert spec.manifest_artifact_id == fingerprint("a")
    assert spec.dataset_fingerprint == fingerprint("c")
    assert spec.configuration_fingerprint == fingerprint("d")
    assert spec.repository_revision == "4eb28d8200214bb1"


@pytest.mark.parametrize(
    "field_name",
    [
        "experiment_spec_id",
        "manifest_artifact_id",
        "dataset_fingerprint",
        "configuration_fingerprint",
    ],
)
def test_experiment_spec_requires_sha256_identity_fields(field_name):
    with pytest.raises(ValueError, match=field_name):
        experiment_spec(**{field_name: "not-a-fingerprint"})


def test_experiment_spec_requires_exact_identity_schema():
    with pytest.raises(ValueError, match="identity_schema"):
        experiment_spec(identity_schema="kanasu.experiment-spec.v2")


def test_experiment_spec_requires_exact_repository_revision():
    with pytest.raises(ValueError, match="repository_revision"):
        experiment_spec(repository_revision="")


def test_run_attempt_keeps_attempt_and_spec_identity_distinct():
    attempt = run_attempt()

    assert attempt.attempt_id == "attempt-001"
    assert attempt.experiment_spec_id == fingerprint("b")
    assert attempt.state is RunAttemptState.RUNNING
    assert attempt.runtime_session_id is None


@pytest.mark.parametrize(
    "state",
    [
        RunAttemptState.QUEUED,
        RunAttemptState.RUNNING,
    ],
)
def test_nonterminal_run_attempt_has_no_terminal_timestamp(state):
    attempt = run_attempt(state=state)

    assert attempt.terminal_at is None


@pytest.mark.parametrize(
    "state",
    [
        RunAttemptState.SUCCEEDED,
        RunAttemptState.FAILED,
        RunAttemptState.CANCELLED,
        RunAttemptState.INTERRUPTED,
    ],
)
def test_terminal_run_attempt_requires_terminal_timestamp(state):
    with pytest.raises(ValueError, match="requires terminal_at"):
        run_attempt(state=state)


def test_terminal_run_attempt_accepts_distinct_runtime_and_result_identity():
    terminal_at = CREATED_AT + timedelta(seconds=5)

    attempt = run_attempt(
        state=RunAttemptState.SUCCEEDED,
        terminal_at=terminal_at,
        runtime_session_id="runtime-session-001",
        result_artifact_id=fingerprint("e"),
        evidence_id="evidence-001",
    )

    assert attempt.terminal_at == terminal_at
    assert attempt.runtime_session_id == "runtime-session-001"
    assert attempt.result_artifact_id == fingerprint("e")
    assert attempt.evidence_id == "evidence-001"


def test_run_attempt_rejects_terminal_timestamp_before_creation():
    with pytest.raises(ValueError, match="cannot precede"):
        run_attempt(
            state=RunAttemptState.FAILED,
            terminal_at=CREATED_AT - timedelta(seconds=1),
        )


def test_running_attempt_rejects_terminal_timestamp():
    with pytest.raises(ValueError, match="non-terminal"):
        run_attempt(
            terminal_at=CREATED_AT + timedelta(seconds=1),
        )


def test_run_attempt_result_artifact_must_be_content_identity():
    with pytest.raises(ValueError, match="result_artifact_id"):
        run_attempt(result_artifact_id="result.json")

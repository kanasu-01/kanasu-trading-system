from datetime import datetime, timedelta, timezone

import pytest

from core.research.models.research_catalog import (
    ComputationKind,
    ResearchArtifact,
    ResearchArtifactKind,
    RunAttemptState,
)
from core.research.reproducibility import experiment_spec_fingerprint
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)


INDIA = timezone(timedelta(hours=5, minutes=30))
CREATED_AT = datetime(
    2026,
    9,
    27,
    11,
    40,
    tzinfo=INDIA,
)


def fingerprint(character: str) -> str:
    return f"sha256:{character * 64}"


def manifest_artifact(**changes) -> ResearchArtifact:
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


def result_artifact(**changes) -> ResearchArtifact:
    values = {
        "artifact_id": fingerprint("e"),
        "artifact_kind": ResearchArtifactKind.BACKTEST_RESULT,
        "schema_id": "kanasu.backtest-result.v1",
        "relative_path": (
            "sha256/ee/"
            + "e" * 64
            + ".json"
        ),
        "byte_count": 456,
        "created_at": CREATED_AT,
    }
    values.update(changes)
    return ResearchArtifact(**values)


def new_store(tmp_path, ids=None) -> SQLiteResearchCatalogStore:
    if ids is None:
        return SQLiteResearchCatalogStore(
            tmp_path / "research.sqlite3"
        )

    iterator = iter(ids)

    return SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3",
        attempt_id_factory=lambda: next(iterator),
    )


def resolve_spec(store, **changes):
    values = {
        "computation_kind": ComputationKind.BACKTEST,
        "manifest_artifact_id": fingerprint("a"),
        "dataset_fingerprint": fingerprint("b"),
        "configuration_fingerprint": fingerprint("c"),
        "repository_revision": "24cdf677d7af0bd50d0630039fb31835af8e71e3",
        "created_at": CREATED_AT,
    }
    values.update(changes)
    return store.resolve_experiment_spec(**values)


def prepared_store(tmp_path, ids=None):
    store = new_store(tmp_path, ids=ids)
    store.save_artifact(manifest_artifact())
    spec = resolve_spec(store)
    return store, spec


def test_experiment_spec_fingerprint_is_repeatable_and_versioned():
    values = {
        "computation_kind": ComputationKind.BACKTEST,
        "manifest_artifact_id": fingerprint("a"),
        "dataset_fingerprint": fingerprint("b"),
        "configuration_fingerprint": fingerprint("c"),
        "repository_revision": "revision-001",
    }

    first = experiment_spec_fingerprint(**values)
    second = experiment_spec_fingerprint(**values)

    assert first == second
    assert first.startswith("sha256:")
    assert len(first) == 71


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    [
        ("manifest_artifact_id", fingerprint("d")),
        ("dataset_fingerprint", fingerprint("e")),
        ("configuration_fingerprint", fingerprint("f")),
        ("repository_revision", "revision-002"),
    ],
)
def test_experiment_spec_identity_changes_with_exact_inputs(
    field_name,
    replacement,
):
    values = {
        "computation_kind": ComputationKind.BACKTEST,
        "manifest_artifact_id": fingerprint("a"),
        "dataset_fingerprint": fingerprint("b"),
        "configuration_fingerprint": fingerprint("c"),
        "repository_revision": "revision-001",
    }

    baseline = experiment_spec_fingerprint(**values)
    changed = {
        **values,
        field_name: replacement,
    }

    assert experiment_spec_fingerprint(**changed) != baseline


def test_artifact_metadata_reuse_preserves_first_catalog_timestamp(tmp_path):
    store = new_store(tmp_path)
    first = manifest_artifact()
    reused = manifest_artifact(
        created_at=CREATED_AT + timedelta(minutes=1)
    )

    assert store.save_artifact(first) == first
    resolved = store.save_artifact(reused)

    assert resolved.artifact_id == first.artifact_id
    assert resolved.created_at == CREATED_AT


def test_artifact_identity_rejects_conflicting_immutable_metadata(tmp_path):
    store = new_store(tmp_path)
    store.save_artifact(manifest_artifact())

    with pytest.raises(
        ValueError,
        match="different immutable metadata",
    ):
        store.save_artifact(
            manifest_artifact(
                schema_id="kanasu.other-schema.v1"
            )
        )


def test_spec_requires_registered_manifest_artifact(tmp_path):
    store = new_store(tmp_path)

    with pytest.raises(
        ValueError,
        match="registered immutable inputs",
    ):
        resolve_spec(store)


def test_equivalent_spec_reuses_identity_and_first_creation_time(tmp_path):
    store = new_store(tmp_path)
    store.save_artifact(manifest_artifact())

    first = resolve_spec(store)
    second = resolve_spec(
        store,
        created_at=CREATED_AT + timedelta(minutes=5),
    )

    assert second.experiment_spec_id == first.experiment_spec_id
    assert second.created_at == first.created_at
    assert store.load_experiment_spec(
        first.experiment_spec_id
    ) == first


@pytest.mark.parametrize(
    ("field_name", "replacement"),
    [
        ("dataset_fingerprint", fingerprint("d")),
        ("configuration_fingerprint", fingerprint("e")),
        ("repository_revision", "different-revision"),
    ],
)
def test_spec_identity_changes_when_effective_identity_changes(
    tmp_path,
    field_name,
    replacement,
):
    store = new_store(tmp_path)
    store.save_artifact(manifest_artifact())

    baseline = resolve_spec(store)
    changed = resolve_spec(
        store,
        **{field_name: replacement},
    )

    assert changed.experiment_spec_id != baseline.experiment_spec_id


def test_retries_use_distinct_attempt_ids_for_same_spec(tmp_path):
    store, spec = prepared_store(
        tmp_path,
        ids=["attempt-one", "attempt-two"],
    )

    first = store.create_running_attempt(
        experiment_spec_id=spec.experiment_spec_id,
        created_at=CREATED_AT,
    )
    second = store.create_running_attempt(
        experiment_spec_id=spec.experiment_spec_id,
        created_at=CREATED_AT + timedelta(seconds=1),
    )

    assert first.attempt_id == "attempt-one"
    assert second.attempt_id == "attempt-two"
    assert first.experiment_spec_id == second.experiment_spec_id
    assert first.state is RunAttemptState.RUNNING
    assert second.state is RunAttemptState.RUNNING


def test_runtime_session_identity_remains_distinct_from_catalog_ids(tmp_path):
    store, spec = prepared_store(
        tmp_path,
        ids=["attempt-catalog-id"],
    )

    attempt = store.create_running_attempt(
        experiment_spec_id=spec.experiment_spec_id,
        created_at=CREATED_AT,
        runtime_session_id="runtime-session-id",
    )

    assert attempt.attempt_id == "attempt-catalog-id"
    assert attempt.runtime_session_id == "runtime-session-id"
    assert attempt.attempt_id != attempt.runtime_session_id
    assert attempt.experiment_spec_id != attempt.runtime_session_id


def test_attempt_requires_existing_spec_via_foreign_key(tmp_path):
    store = new_store(
        tmp_path,
        ids=["attempt-missing-spec"],
    )

    with pytest.raises(
        ValueError,
        match="existing ExperimentSpec",
    ):
        store.create_running_attempt(
            experiment_spec_id=fingerprint("9"),
            created_at=CREATED_AT,
        )


def test_store_reopen_loads_durable_spec_and_attempt(tmp_path):
    database_path = tmp_path / "research.sqlite3"

    first_store = SQLiteResearchCatalogStore(
        database_path,
        attempt_id_factory=lambda: "attempt-durable",
    )
    first_store.save_artifact(manifest_artifact())
    spec = resolve_spec(first_store)
    attempt = first_store.create_running_attempt(
        experiment_spec_id=spec.experiment_spec_id,
        created_at=CREATED_AT,
    )

    reopened = SQLiteResearchCatalogStore(database_path)

    assert reopened.load_experiment_spec(
        spec.experiment_spec_id
    ) == spec
    assert reopened.load_run_attempt(
        attempt.attempt_id
    ) == attempt


def test_running_attempt_transitions_once_to_success(tmp_path):
    store, spec = prepared_store(
        tmp_path,
        ids=["attempt-success"],
    )
    store.save_artifact(result_artifact())

    running = store.create_running_attempt(
        experiment_spec_id=spec.experiment_spec_id,
        created_at=CREATED_AT,
        runtime_session_id="runtime-001",
    )

    terminal = store.terminalize_attempt(
        running.attempt_id,
        state=RunAttemptState.SUCCEEDED,
        terminal_at=CREATED_AT + timedelta(seconds=5),
        result_artifact_id=fingerprint("e"),
    )

    assert terminal.state is RunAttemptState.SUCCEEDED
    assert terminal.runtime_session_id == "runtime-001"
    assert terminal.result_artifact_id == fingerprint("e")
    assert store.load_run_attempt(running.attempt_id) == terminal


def test_terminal_attempt_cannot_be_reopened_or_rewritten(tmp_path):
    store, spec = prepared_store(
        tmp_path,
        ids=["attempt-terminal"],
    )

    attempt = store.create_running_attempt(
        experiment_spec_id=spec.experiment_spec_id,
        created_at=CREATED_AT,
    )

    store.terminalize_attempt(
        attempt.attempt_id,
        state=RunAttemptState.FAILED,
        terminal_at=CREATED_AT + timedelta(seconds=3),
        failure_classification="execution_error",
        failure_message="first failure",
    )

    with pytest.raises(
        ValueError,
        match="cannot be reopened",
    ):
        store.terminalize_attempt(
            attempt.attempt_id,
            state=RunAttemptState.INTERRUPTED,
            terminal_at=CREATED_AT + timedelta(seconds=4),
            failure_classification="different",
            failure_message="must not replace",
        )

    persisted = store.load_run_attempt(attempt.attempt_id)

    assert persisted.state is RunAttemptState.FAILED
    assert persisted.failure_message == "first failure"


def test_runtime_session_id_cannot_be_replaced_at_terminalization(tmp_path):
    store, spec = prepared_store(
        tmp_path,
        ids=["attempt-runtime"],
    )

    attempt = store.create_running_attempt(
        experiment_spec_id=spec.experiment_spec_id,
        created_at=CREATED_AT,
        runtime_session_id="runtime-original",
    )

    with pytest.raises(
        ValueError,
        match="cannot be replaced",
    ):
        store.terminalize_attempt(
            attempt.attempt_id,
            state=RunAttemptState.FAILED,
            terminal_at=CREATED_AT + timedelta(seconds=1),
            runtime_session_id="runtime-replacement",
        )

    persisted = store.load_run_attempt(attempt.attempt_id)

    assert persisted.state is RunAttemptState.RUNNING
    assert persisted.runtime_session_id == "runtime-original"


def test_terminal_result_reference_requires_registered_artifact(tmp_path):
    store, spec = prepared_store(
        tmp_path,
        ids=["attempt-result-fk"],
    )

    attempt = store.create_running_attempt(
        experiment_spec_id=spec.experiment_spec_id,
        created_at=CREATED_AT,
    )

    with pytest.raises(
        ValueError,
        match="references must already exist",
    ):
        store.terminalize_attempt(
            attempt.attempt_id,
            state=RunAttemptState.SUCCEEDED,
            terminal_at=CREATED_AT + timedelta(seconds=1),
            result_artifact_id=fingerprint("e"),
        )

    assert store.load_run_attempt(
        attempt.attempt_id
    ).state is RunAttemptState.RUNNING


def test_m92c_does_not_expose_cancelled_transition(tmp_path):
    store, spec = prepared_store(
        tmp_path,
        ids=["attempt-cancel"],
    )

    attempt = store.create_running_attempt(
        experiment_spec_id=spec.experiment_spec_id,
        created_at=CREATED_AT,
    )

    with pytest.raises(
        ValueError,
        match="SUCCEEDED, FAILED or INTERRUPTED",
    ):
        store.terminalize_attempt(
            attempt.attempt_id,
            state=RunAttemptState.CANCELLED,
            terminal_at=CREATED_AT + timedelta(seconds=1),
        )

    assert store.load_run_attempt(
        attempt.attempt_id
    ).state is RunAttemptState.RUNNING

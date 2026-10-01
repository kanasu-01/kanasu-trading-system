from datetime import datetime, timedelta, timezone

import pytest

from core.research.models.registered_study import (
    EvidenceReusePolicy,
    ResearchJob,
    ResearchJobState,
    Study,
    StudyRevision,
    Trial,
    TrialDisposition,
    TrialDispositionEvent,
)
from core.research.models.research_catalog import (
    ResearchArtifact,
    ResearchArtifactKind,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)


INDIA = timezone(timedelta(hours=5, minutes=30))
CREATED_AT = datetime(
    2026,
    10,
    1,
    8,
    0,
    tzinfo=INDIA,
)


def fp(character: str) -> str:
    return f"sha256:{character * 64}"


def plan_artifact(
    artifact_id: str = fp("a"),
) -> ResearchArtifact:
    return ResearchArtifact(
        artifact_id=artifact_id,
        artifact_kind=(
            ResearchArtifactKind.STUDY_REVISION_PLAN
        ),
        schema_id="kanasu.study-revision-plan.v1",
        relative_path=(
            "sha256/"
            + artifact_id[7:9]
            + "/"
            + artifact_id[7:]
            + ".json"
        ),
        byte_count=321,
        created_at=CREATED_AT,
    )



def membership_evidence_artifact() -> ResearchArtifact:
    artifact_id = fp("e")

    return ResearchArtifact(
        artifact_id=artifact_id,
        artifact_kind=(
            ResearchArtifactKind.TRIAL_MEMBERSHIP_EVIDENCE
        ),
        schema_id="kanasu.trial-membership-evidence.v1",
        relative_path=(
            "sha256/ee/"
            + "e" * 64
            + ".json"
        ),
        byte_count=654,
        created_at=CREATED_AT,
    )



def other_artifact() -> ResearchArtifact:
    return ResearchArtifact(
        artifact_id=fp("b"),
        artifact_kind=(
            ResearchArtifactKind.BACKTEST_RUN_MANIFEST
        ),
        schema_id="kanasu.backtest-run-manifest.v1",
        relative_path=(
            "sha256/bb/"
            + "b" * 64
            + ".json"
        ),
        byte_count=123,
        created_at=CREATED_AT,
    )


def study() -> Study:
    return Study(
        study_id="study-001",
        created_at=CREATED_AT,
        display_title="M9.4 registered research",
    )


def revision(
    *,
    study_revision_id: str = fp("c"),
    plan_artifact_id: str = fp("a"),
    registered_at: datetime = CREATED_AT,
) -> StudyRevision:
    return StudyRevision(
        study_revision_id=study_revision_id,
        study_id="study-001",
        revision_number=1,
        plan_artifact_id=plan_artifact_id,
        repository_revision=(
            "199ec3492a5af682482d0bee40c669420833563c"
        ),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
        registered_at=registered_at,
    )


def trial(
    *,
    trial_id: str = fp("d"),
    study_revision_id: str = fp("c"),
) -> Trial:
    return Trial(
        trial_id=trial_id,
        study_revision_id=study_revision_id,
        instrument_id="instrument-reliance",
        membership_episode_start=CREATED_AT,
        membership_episode_end=(
            CREATED_AT + timedelta(days=30)
        ),
        membership_evidence_fingerprint=fp("e"),
        membership_evidence_artifact_id=fp("e"),
        parameter_configuration_fingerprint=fp("f"),
        registered_at=CREATED_AT,
        disposition=TrialDisposition.PENDING,
        disposition_at=CREATED_AT,
    )


def initial_event(
    *,
    event_id: str = "event-001",
    trial_id: str = fp("d"),
) -> TrialDispositionEvent:
    return TrialDispositionEvent(
        event_id=event_id,
        trial_id=trial_id,
        sequence_number=1,
        previous_disposition=None,
        new_disposition=TrialDisposition.PENDING,
        occurred_at=CREATED_AT,
    )


def prepared_store(tmp_path):
    store = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )
    store.save_study(study())
    store.save_artifact(plan_artifact())
    store.save_artifact(membership_evidence_artifact())
    store.save_study_revision(revision())
    return store


def prepared_trial_store(tmp_path):
    store = prepared_store(tmp_path)
    registered = trial()
    event = initial_event()
    store.save_registered_trial(
        registered,
        event,
    )
    return store, registered, event


def test_study_round_trip_and_display_metadata_update(
    tmp_path,
):
    store = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )
    original = study()

    assert store.save_study(original) == original
    assert store.load_study(
        original.study_id
    ) == original

    updated = store.update_study_metadata(
        original.study_id,
        display_title="Renamed study",
        archived=True,
    )

    assert updated.study_id == original.study_id
    assert updated.created_at == original.created_at
    assert updated.display_title == "Renamed study"
    assert updated.archived is True
    assert store.load_study(
        original.study_id
    ) == updated


def test_study_exact_duplicate_creation_is_idempotent(
    tmp_path,
):
    store = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )
    original = study()

    assert store.save_study(original) == original
    assert store.save_study(original) == original


def test_study_revision_requires_registered_plan_artifact(
    tmp_path,
):
    store = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )
    store.save_study(study())
    store.save_artifact(other_artifact())

    with pytest.raises(
        ValueError,
        match="STUDY_REVISION_PLAN",
    ):
        store.save_study_revision(
            revision(plan_artifact_id=fp("b"))
        )


def test_study_revision_round_trip_preserves_first_registration(
    tmp_path,
):
    store = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )
    store.save_study(study())
    store.save_artifact(plan_artifact())

    first = revision()
    repeated = revision(
        registered_at=(
            CREATED_AT + timedelta(minutes=5)
        )
    )

    assert store.save_study_revision(first) == first

    resolved = store.save_study_revision(repeated)

    assert resolved.study_revision_id == (
        first.study_revision_id
    )
    assert resolved.registered_at == first.registered_at
    assert store.list_study_revisions(
        first.study_id
    ) == (first,)


def test_new_revision_persistence_does_not_accept_started_state(
    tmp_path,
):
    store = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )
    store.save_study(study())
    store.save_artifact(plan_artifact())

    started = StudyRevision(
        **{
            **revision().__dict__,
            "initial_batch_started_at": (
                CREATED_AT + timedelta(minutes=1)
            ),
        }
    )

    with pytest.raises(
        ValueError,
        match="Start owns",
    ):
        store.save_study_revision(started)


def test_trial_and_initial_event_commit_atomically(
    tmp_path,
):
    store = prepared_store(tmp_path)
    registered = trial()
    event = initial_event()

    saved = store.save_registered_trial(
        registered,
        event,
    )

    assert saved == registered
    assert store.load_trial(
        registered.trial_id
    ) == registered
    assert store.load_trial_disposition_events(
        registered.trial_id
    ) == (event,)
    assert store.list_trials_for_revision(
        registered.study_revision_id
    ) == (registered,)


def test_trial_registration_failure_leaves_no_partial_trial(
    tmp_path,
):
    store = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )
    store.save_artifact(membership_evidence_artifact())
    orphan = trial(
        study_revision_id=fp("9")
    )
    event = initial_event(
        trial_id=orphan.trial_id
    )

    with pytest.raises(
        ValueError,
        match="existing StudyRevision",
    ):
        store.save_registered_trial(
            orphan,
            event,
        )

    assert store.load_trial(orphan.trial_id) is None
    assert store.load_trial_disposition_events(
        orphan.trial_id
    ) == ()


def test_trial_registration_rejects_non_initial_event(
    tmp_path,
):
    store = prepared_store(tmp_path)
    registered = trial()

    bad_event = TrialDispositionEvent(
        event_id="event-bad",
        trial_id=registered.trial_id,
        sequence_number=2,
        previous_disposition=TrialDisposition.PENDING,
        new_disposition=TrialDisposition.PENDING,
        occurred_at=CREATED_AT,
    )

    with pytest.raises(
        ValueError,
        match="sequence 1",
    ):
        store.save_registered_trial(
            registered,
            bad_event,
        )

    assert store.load_trial(
        registered.trial_id
    ) is None


def test_trial_exact_registration_replay_is_idempotent(
    tmp_path,
):
    store = prepared_store(tmp_path)
    registered = trial()
    event = initial_event()

    assert (
        store.save_registered_trial(
            registered,
            event,
        )
        == registered
    )

    assert (
        store.save_registered_trial(
            registered,
            event,
        )
        == registered
    )

    assert store.load_trial_disposition_events(
        registered.trial_id
    ) == (event,)


def test_queued_job_round_trip_has_no_run_attempt(
    tmp_path,
):
    store, registered, _ = prepared_trial_store(
        tmp_path
    )

    job = ResearchJob(
        job_id="job-001",
        trial_id=registered.trial_id,
        state=ResearchJobState.QUEUED,
        created_at=CREATED_AT,
    )

    assert store.save_queued_research_job(
        job
    ) == job
    assert store.load_research_job(
        job.job_id
    ) == job
    assert store.list_research_jobs_for_trial(
        registered.trial_id
    ) == (job,)
    assert job.attempt_id is None


def test_job_persistence_rejects_nonqueued_lifecycle_state(
    tmp_path,
):
    store, registered, _ = prepared_trial_store(
        tmp_path
    )

    running = ResearchJob(
        job_id="job-running",
        trial_id=registered.trial_id,
        state=ResearchJobState.RUNNING,
        created_at=CREATED_AT,
        claimed_at=CREATED_AT,
        worker_id="worker-001",
    )

    with pytest.raises(
        ValueError,
        match="uncancelled QUEUED",
    ):
        store.save_queued_research_job(running)

    assert store.load_research_job(
        running.job_id
    ) is None


def test_job_requires_existing_trial(
    tmp_path,
):
    store = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )

    orphan = ResearchJob(
        job_id="job-orphan",
        trial_id=fp("8"),
        state=ResearchJobState.QUEUED,
        created_at=CREATED_AT,
    )

    with pytest.raises(
        ValueError,
        match="existing Trial",
    ):
        store.save_queued_research_job(orphan)


def test_reopen_preserves_registered_catalog_records(
    tmp_path,
):
    path = tmp_path / "research.sqlite3"

    first = SQLiteResearchCatalogStore(path)
    first.save_study(study())
    first.save_artifact(plan_artifact())
    first.save_artifact(membership_evidence_artifact())
    first.save_study_revision(revision())
    first.save_registered_trial(
        trial(),
        initial_event(),
    )

    job = ResearchJob(
        job_id="job-durable",
        trial_id=fp("d"),
        state=ResearchJobState.QUEUED,
        created_at=CREATED_AT,
    )
    first.save_queued_research_job(job)

    reopened = SQLiteResearchCatalogStore(path)

    assert reopened.load_study(
        "study-001"
    ) == study()
    assert reopened.load_study_revision(
        fp("c")
    ) == revision()
    assert reopened.load_trial(
        fp("d")
    ) == trial()
    assert reopened.load_trial_disposition_events(
        fp("d")
    ) == (initial_event(),)
    assert reopened.load_research_job(
        "job-durable"
    ) == job


def test_trial_requires_registered_membership_evidence_artifact(
    tmp_path,
):
    store = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )
    store.save_study(study())
    store.save_artifact(plan_artifact())
    store.save_study_revision(revision())

    registered = trial()

    with pytest.raises(
        ValueError,
        match="TRIAL_MEMBERSHIP_EVIDENCE",
    ):
        store.save_registered_trial(
            registered,
            initial_event(),
        )

    assert store.load_trial(
        registered.trial_id
    ) is None


def test_trial_rejects_wrong_membership_evidence_artifact_kind(
    tmp_path,
):
    store = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )
    store.save_study(study())
    store.save_artifact(plan_artifact())

    store.save_artifact(
        ResearchArtifact(
            artifact_id=fp("e"),
            artifact_kind=(
                ResearchArtifactKind.BACKTEST_RUN_MANIFEST
            ),
            schema_id="kanasu.backtest-run-manifest.v1",
            relative_path=(
                "sha256/ee/"
                + "e" * 64
                + ".json"
            ),
            byte_count=654,
            created_at=CREATED_AT,
        )
    )

    store.save_study_revision(revision())

    with pytest.raises(
        ValueError,
        match="TRIAL_MEMBERSHIP_EVIDENCE",
    ):
        store.save_registered_trial(
            trial(),
            initial_event(),
        )

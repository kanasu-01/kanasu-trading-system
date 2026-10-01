from datetime import datetime, timedelta, timezone

import pytest

from core.research.models.registered_study import (
    EvidenceReusePolicy,
    ResearchJob,
    ResearchJobCompletionKind,
    ResearchJobState,
    Study,
    StudyRevision,
    Trial,
    TrialDisposition,
    TrialDispositionEvent,
)
from core.research.models.research_catalog import (
    ResearchArtifactKind,
)


INDIA = timezone(timedelta(hours=5, minutes=30))
CREATED_AT = datetime(
    2026,
    9,
    30,
    10,
    0,
    tzinfo=INDIA,
)


def fp(character: str) -> str:
    return f"sha256:{character * 64}"


def test_study_revision_plan_is_first_class_artifact_kind():
    assert (
        ResearchArtifactKind.STUDY_REVISION_PLAN.value
        == "STUDY_REVISION_PLAN"
    )


def test_study_record_is_immutable_and_time_is_aware():
    study = Study(
        study_id="study-001",
        created_at=CREATED_AT,
        display_title="Registered momentum research",
    )

    with pytest.raises(AttributeError):
        study.display_title = "changed"

    with pytest.raises(ValueError, match="timezone-aware"):
        Study(
            study_id="study-002",
            created_at=CREATED_AT.replace(tzinfo=None),
            display_title="Invalid",
        )


def test_revision_keeps_registration_and_start_distinct():
    revision = StudyRevision(
        study_revision_id=fp("a"),
        study_id="study-001",
        revision_number=1,
        plan_artifact_id=fp("b"),
        repository_revision="199ec3492a5af682",
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
        registered_at=CREATED_AT,
        initial_batch_started_at=(
            CREATED_AT + timedelta(minutes=10)
        ),
    )

    assert revision.revision_number == 1

    with pytest.raises(
        ValueError,
        match="cannot precede registered_at",
    ):
        StudyRevision(
            study_revision_id=fp("c"),
            study_id="study-001",
            revision_number=2,
            plan_artifact_id=fp("d"),
            repository_revision="199ec3492a5af682",
            evidence_reuse_policy=(
                EvidenceReusePolicy.FORCE_NEW_EXECUTION
            ),
            registered_at=CREATED_AT,
            initial_batch_started_at=(
                CREATED_AT - timedelta(seconds=1)
            ),
        )


def test_trial_uses_continuous_membership_episode():
    trial = Trial(
        trial_id=fp("1"),
        study_revision_id=fp("2"),
        instrument_id="instrument-reliance",
        membership_episode_start=CREATED_AT,
        membership_episode_end=(
            CREATED_AT + timedelta(days=30)
        ),
        membership_evidence_fingerprint=fp("3"),
        membership_evidence_artifact_id=fp("3"),
        parameter_configuration_fingerprint=fp("4"),
        registered_at=CREATED_AT,
        disposition=TrialDisposition.PENDING,
        disposition_at=CREATED_AT,
    )

    assert trial.disposition is TrialDisposition.PENDING

    with pytest.raises(
        ValueError,
        match="must be after",
    ):
        Trial(
            trial_id=fp("5"),
            study_revision_id=fp("2"),
            instrument_id="instrument-reliance",
            membership_episode_start=CREATED_AT,
            membership_episode_end=CREATED_AT,
            membership_evidence_fingerprint=fp("3"),
            membership_evidence_artifact_id=fp("3"),
            parameter_configuration_fingerprint=fp("4"),
            registered_at=CREATED_AT,
            disposition=TrialDisposition.PENDING,
            disposition_at=CREATED_AT,
        )


def test_trial_event_requires_positive_local_sequence():
    event = TrialDispositionEvent(
        event_id="event-001",
        trial_id=fp("1"),
        sequence_number=1,
        previous_disposition=None,
        new_disposition=TrialDisposition.PENDING,
        occurred_at=CREATED_AT,
    )

    assert event.sequence_number == 1

    with pytest.raises(
        ValueError,
        match="positive integer",
    ):
        TrialDispositionEvent(
            event_id="event-invalid",
            trial_id=fp("1"),
            sequence_number=0,
            previous_disposition=None,
            new_disposition=TrialDisposition.PENDING,
            occurred_at=CREATED_AT,
        )


def test_queued_job_has_no_claim_attempt_or_completion():
    job = ResearchJob(
        job_id="job-001",
        trial_id=fp("1"),
        state=ResearchJobState.QUEUED,
        created_at=CREATED_AT,
    )

    assert job.claimed_at is None
    assert job.attempt_id is None
    assert job.completion_kind is None


def test_executed_success_requires_new_attempt():
    completed = ResearchJob(
        job_id="job-executed",
        trial_id=fp("1"),
        state=ResearchJobState.SUCCEEDED,
        created_at=CREATED_AT,
        claimed_at=CREATED_AT,
        terminal_at=CREATED_AT + timedelta(seconds=2),
        worker_id="worker-001",
        attempt_id="attempt-001",
        completion_kind=(
            ResearchJobCompletionKind.EXECUTED
        ),
    )

    assert completed.attempt_id == "attempt-001"

    with pytest.raises(
        ValueError,
        match="requires attempt_id",
    ):
        ResearchJob(
            job_id="job-invalid",
            trial_id=fp("1"),
            state=ResearchJobState.SUCCEEDED,
            created_at=CREATED_AT,
            claimed_at=CREATED_AT,
            terminal_at=(
                CREATED_AT + timedelta(seconds=2)
            ),
            worker_id="worker-001",
            completion_kind=(
                ResearchJobCompletionKind.EXECUTED
            ),
        )


def test_reused_success_has_prior_sources_and_no_new_attempt():
    reused = ResearchJob(
        job_id="job-reused",
        trial_id=fp("1"),
        state=ResearchJobState.SUCCEEDED,
        created_at=CREATED_AT,
        claimed_at=CREATED_AT,
        terminal_at=CREATED_AT + timedelta(seconds=1),
        worker_id="worker-001",
        completion_kind=ResearchJobCompletionKind.REUSED,
        reused_attempt_id="attempt-prior",
        reused_evidence_id="evidence-prior",
        reused_result_artifact_id=fp("9"),
    )

    assert reused.attempt_id is None

    with pytest.raises(
        ValueError,
        match="cannot create a new attempt_id",
    ):
        ResearchJob(
            job_id="job-invalid-reuse",
            trial_id=fp("1"),
            state=ResearchJobState.SUCCEEDED,
            created_at=CREATED_AT,
            claimed_at=CREATED_AT,
            terminal_at=(
                CREATED_AT + timedelta(seconds=1)
            ),
            worker_id="worker-001",
            attempt_id="attempt-new",
            completion_kind=(
                ResearchJobCompletionKind.REUSED
            ),
            reused_attempt_id="attempt-prior",
            reused_evidence_id="evidence-prior",
            reused_result_artifact_id=fp("9"),
        )


def test_trial_membership_evidence_is_first_class_artifact_kind():
    assert (
        ResearchArtifactKind.TRIAL_MEMBERSHIP_EVIDENCE.value
        == "TRIAL_MEMBERSHIP_EVIDENCE"
    )


def test_trial_rejects_membership_evidence_identity_mismatch():
    with pytest.raises(
        ValueError,
        match="artifact identity must match",
    ):
        Trial(
            trial_id=fp("5"),
            study_revision_id=fp("2"),
            instrument_id="instrument-reliance",
            membership_episode_start=CREATED_AT,
            membership_episode_end=(
                CREATED_AT + timedelta(days=30)
            ),
            membership_evidence_fingerprint=fp("3"),
            membership_evidence_artifact_id=fp("8"),
            parameter_configuration_fingerprint=fp("4"),
            registered_at=CREATED_AT,
            disposition=TrialDisposition.PENDING,
            disposition_at=CREATED_AT,
        )

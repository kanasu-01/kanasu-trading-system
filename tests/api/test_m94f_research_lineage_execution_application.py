from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import api.research_application as application
from core.config.app_config import AppConfig
from core.research.models.registered_study import (
    ResearchQueueSnapshot,
)


NOW = datetime(
    2026,
    10,
    2,
    12,
    0,
    tzinfo=timezone.utc,
)

REVISION_ID = "sha256:" + ("1" * 64)
TRIAL_ID = "sha256:" + ("2" * 64)
JOB_ID = "sha256:" + ("3" * 64)
ATTEMPT_ID = "attempt-001"
RESULT_ID = "sha256:" + ("4" * 64)
EVIDENCE_ID = "evidence-001"


def _config(tmp_path) -> AppConfig:
    return AppConfig(
        research_database_path=str(
            tmp_path / "research.sqlite3"
        ),
        research_artifact_root=str(
            tmp_path / "artifacts"
        ),
        research_max_workers=2,
    )


def _snapshot() -> ResearchQueueSnapshot:
    return ResearchQueueSnapshot(
        study_revision_id=REVISION_ID,
        initial_batch_started_at=NOW,
        total_registered_trials=1,
        pending_trials=0,
        executed_trials=1,
        reused_trials=0,
        invalid_trials=0,
        insufficient_trials=0,
        failed_trials=0,
        cancelled_trials=0,
        interrupted_trials=0,
        queued_jobs=0,
        running_jobs=0,
        succeeded_jobs=1,
        failed_jobs=0,
        cancelled_jobs=0,
        interrupted_jobs=0,
    )


def _revision():
    return SimpleNamespace(
        study_revision_id=REVISION_ID,
    )


def _trial():
    return SimpleNamespace(
        trial_id=TRIAL_ID,
        study_revision_id=REVISION_ID,
        instrument_id="NSE:A",
        membership_episode_start=NOW,
        membership_episode_end=NOW,
        disposition=SimpleNamespace(
            value="EXECUTED"
        ),
        disposition_at=NOW,
        experiment_spec_id=(
            "sha256:" + ("5" * 64)
        ),
        reused_attempt_id=None,
        failure_classification=None,
        failure_message=None,
    )


def _event():
    return SimpleNamespace(
        event_id="event-001",
        trial_id=TRIAL_ID,
        sequence_number=2,
        previous_disposition=SimpleNamespace(
            value="PENDING"
        ),
        new_disposition=SimpleNamespace(
            value="EXECUTED"
        ),
        occurred_at=NOW,
        causing_job_id=JOB_ID,
        reason_classification=None,
        reason_message=None,
    )


def _job():
    return SimpleNamespace(
        job_id=JOB_ID,
        trial_id=TRIAL_ID,
        state=SimpleNamespace(
            value="SUCCEEDED"
        ),
        created_at=NOW,
        claimed_at=NOW,
        terminal_at=NOW,
        worker_id="worker-001",
        cancel_requested_at=None,
        attempt_id=ATTEMPT_ID,
        completion_kind=SimpleNamespace(
            value="EXECUTED"
        ),
        reused_attempt_id=None,
        reused_evidence_id=None,
        reused_result_artifact_id=None,
        failure_classification=None,
        failure_message=None,
    )


def _attempt():
    return SimpleNamespace(
        attempt_id=ATTEMPT_ID,
        experiment_spec_id=(
            "sha256:" + ("5" * 64)
        ),
        state=SimpleNamespace(
            value="SUCCEEDED"
        ),
        created_at=NOW,
        terminal_at=NOW,
        runtime_session_id="runtime-001",
        result_artifact_id=RESULT_ID,
        evidence_id=EVIDENCE_ID,
        failure_classification=None,
        failure_message=None,
    )


class RecordingStore:
    def __init__(
        self,
        *,
        revision=None,
        trial=None,
        events=(),
        jobs=(),
        attempts=None,
    ):
        self.revision = revision
        self.trial = trial
        self.events = tuple(events)
        self.jobs = tuple(jobs)
        self.attempts = dict(
            attempts or {}
        )

        self.revision_requests = []
        self.trial_requests = []
        self.event_requests = []
        self.job_requests = []
        self.attempt_requests = []

    def load_study_revision(
        self,
        study_revision_id,
    ):
        self.revision_requests.append(
            study_revision_id
        )

        if (
            self.revision is not None
            and self.revision.study_revision_id
            == study_revision_id
        ):
            return self.revision

        return None

    def load_trial(
        self,
        trial_id,
    ):
        self.trial_requests.append(
            trial_id
        )

        if (
            self.trial is not None
            and self.trial.trial_id
            == trial_id
        ):
            return self.trial

        return None

    def load_trial_disposition_events(
        self,
        trial_id,
    ):
        self.event_requests.append(
            trial_id
        )
        return self.events

    def list_research_jobs_for_trial(
        self,
        trial_id,
    ):
        self.job_requests.append(
            trial_id
        )
        return self.jobs

    def load_run_attempt(
        self,
        attempt_id,
    ):
        self.attempt_requests.append(
            attempt_id
        )
        return self.attempts.get(
            attempt_id
        )


def test_trial_detail_exposes_durable_disposition_job_and_result_lineage(
    tmp_path,
    monkeypatch,
):
    store = RecordingStore(
        revision=_revision(),
        trial=_trial(),
        events=(_event(),),
        jobs=(_job(),),
        attempts={
            ATTEMPT_ID: _attempt(),
        },
    )

    monkeypatch.setattr(
        application,
        "SQLiteResearchCatalogStore",
        lambda _path: store,
    )

    get_detail = getattr(
        application,
        "get_research_trial_detail",
    )

    response = get_detail(
        TRIAL_ID,
        app_config=_config(tmp_path),
    )

    assert response.trial.trial_id == TRIAL_ID
    assert (
        response.trial.study_revision_id
        == REVISION_ID
    )
    assert response.trial.disposition == "EXECUTED"

    assert len(response.disposition_events) == 1

    event = response.disposition_events[0]

    assert event.sequence_number == 2
    assert event.previous_disposition == "PENDING"
    assert event.new_disposition == "EXECUTED"
    assert event.causing_job_id == JOB_ID

    assert len(response.jobs) == 1

    job = response.jobs[0]

    assert job.job_id == JOB_ID
    assert job.state == "SUCCEEDED"
    assert job.completion_kind == "EXECUTED"
    assert job.attempt_id == ATTEMPT_ID
    assert job.reused_result_artifact_id is None

    assert job.attempt is not None
    assert job.attempt.attempt_id == ATTEMPT_ID
    assert job.attempt.state == "SUCCEEDED"
    assert (
        job.attempt.result_artifact_id
        == RESULT_ID
    )
    assert job.attempt.evidence_id == EVIDENCE_ID

    assert store.trial_requests == [
        TRIAL_ID
    ]
    assert store.event_requests == [
        TRIAL_ID
    ]
    assert store.job_requests == [
        TRIAL_ID
    ]
    assert store.attempt_requests == [
        ATTEMPT_ID
    ]


def test_trial_detail_reports_missing_trial(
    tmp_path,
    monkeypatch,
):
    store = RecordingStore()

    monkeypatch.setattr(
        application,
        "SQLiteResearchCatalogStore",
        lambda _path: store,
    )

    get_detail = getattr(
        application,
        "get_research_trial_detail",
    )

    error_type = getattr(
        application,
        "ResearchTrialNotFound",
    )

    with pytest.raises(
        error_type
    ):
        get_detail(
            TRIAL_ID,
            app_config=_config(tmp_path),
        )

    assert store.trial_requests == [
        TRIAL_ID
    ]
    assert store.event_requests == []
    assert store.job_requests == []


def test_run_revision_drains_existing_queue_with_explicit_handler(
    tmp_path,
    monkeypatch,
):
    store = RecordingStore(
        revision=_revision(),
    )

    captured = {}

    class RecordingQueue:
        def __init__(
            self,
            *,
            catalog_store,
            app_config,
        ):
            captured["catalog_store"] = (
                catalog_store
            )
            captured["app_config"] = app_config

        def run_worker_pool(
            self,
            study_revision_id,
            *,
            worker_id_factory,
            claimed_at_factory,
            execute_claimed_job,
        ):
            captured["study_revision_id"] = (
                study_revision_id
            )
            captured["worker_id_factory"] = (
                worker_id_factory
            )
            captured["claimed_at_factory"] = (
                claimed_at_factory
            )
            captured["execute_claimed_job"] = (
                execute_claimed_job
            )

            return _snapshot()

    monkeypatch.setattr(
        application,
        "SQLiteResearchCatalogStore",
        lambda _path: store,
    )
    monkeypatch.setattr(
        application,
        "ResearchJobQueueService",
        RecordingQueue,
    )

    def execute_claimed_job(job):
        return job

    def worker_id_factory(slot_index):
        return f"worker-{slot_index}"

    def claimed_at_factory():
        return NOW

    run_revision = getattr(
        application,
        "run_research_revision",
    )

    response = run_revision(
        REVISION_ID,
        execute_claimed_job=(
            execute_claimed_job
        ),
        worker_id_factory=(
            worker_id_factory
        ),
        claimed_at_factory=(
            claimed_at_factory
        ),
        app_config=_config(tmp_path),
    )

    assert captured["catalog_store"] is store
    assert (
        captured["study_revision_id"]
        == REVISION_ID
    )
    assert (
        captured["execute_claimed_job"]
        is execute_claimed_job
    )
    assert (
        captured["worker_id_factory"]
        is worker_id_factory
    )
    assert (
        captured["claimed_at_factory"]
        is claimed_at_factory
    )

    assert response.study_revision_id == REVISION_ID
    assert response.total_registered_trials == 1
    assert response.executed_trials == 1
    assert response.succeeded_jobs == 1


def test_run_revision_rejects_missing_explicit_execution_handler(
    tmp_path,
):
    run_revision = getattr(
        application,
        "run_research_revision",
    )

    with pytest.raises(
        TypeError,
        match="execute_claimed_job",
    ):
        run_revision(
            REVISION_ID,
            execute_claimed_job=None,
            worker_id_factory=(
                lambda slot: f"worker-{slot}"
            ),
            claimed_at_factory=lambda: NOW,
            app_config=_config(tmp_path),
        )

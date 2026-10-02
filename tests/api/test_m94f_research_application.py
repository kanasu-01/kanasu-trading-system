from datetime import datetime, timezone

import pytest

import api.research_application as application
from api.models.research_models import (
    ResearchProgressResponse,
)
from api.research_application import (
    ResearchRevisionNotFound,
    get_research_progress,
)
from core.config.app_config import AppConfig
from core.research.models.registered_study import (
    ResearchQueueSnapshot,
)


REVISION_ID = "sha256:" + ("1" * 64)
STARTED_AT = datetime(
    2026,
    10,
    2,
    10,
    0,
    tzinfo=timezone.utc,
)


def _snapshot() -> ResearchQueueSnapshot:
    return ResearchQueueSnapshot(
        study_revision_id=REVISION_ID,
        initial_batch_started_at=STARTED_AT,
        total_registered_trials=8,
        pending_trials=1,
        executed_trials=2,
        reused_trials=1,
        invalid_trials=1,
        insufficient_trials=1,
        failed_trials=1,
        cancelled_trials=1,
        interrupted_trials=0,
        queued_jobs=1,
        running_jobs=1,
        succeeded_jobs=3,
        failed_jobs=2,
        cancelled_jobs=1,
        interrupted_jobs=1,
    )


class RecordingStore:
    def __init__(
        self,
        snapshot,
        *,
        revision_exists=True,
    ):
        self.snapshot = snapshot
        self.revision_exists = revision_exists
        self.revision_requests = []
        self.snapshot_requests = []

    def load_study_revision(
        self,
        study_revision_id,
    ):
        self.revision_requests.append(
            study_revision_id
        )

        if not self.revision_exists:
            return None

        return object()

    def load_research_queue_snapshot(
        self,
        study_revision_id,
    ):
        self.snapshot_requests.append(
            study_revision_id
        )
        return self.snapshot


def test_progress_application_exposes_truthful_snapshot(
    tmp_path,
    monkeypatch,
):
    snapshot = _snapshot()
    store = RecordingStore(snapshot)
    created_paths = []

    def store_factory(path):
        created_paths.append(str(path))
        return store

    monkeypatch.setattr(
        application,
        "SQLiteResearchCatalogStore",
        store_factory,
    )

    config = AppConfig(
        research_database_path=str(
            tmp_path / "research.sqlite3"
        )
    )

    result = get_research_progress(
        REVISION_ID,
        app_config=config,
    )

    assert isinstance(
        result,
        ResearchProgressResponse,
    )

    assert result.model_dump() == {
        "study_revision_id": REVISION_ID,
        "initial_batch_started_at": STARTED_AT,
        "total_registered_trials": 8,
        "pending_trials": 1,
        "executed_trials": 2,
        "reused_trials": 1,
        "invalid_trials": 1,
        "insufficient_trials": 1,
        "failed_trials": 1,
        "cancelled_trials": 1,
        "interrupted_trials": 0,
        "queued_jobs": 1,
        "running_jobs": 1,
        "succeeded_jobs": 3,
        "failed_jobs": 2,
        "cancelled_jobs": 1,
        "interrupted_jobs": 1,
        "total_jobs": 9,
    }

    assert created_paths == [
        str(tmp_path / "research.sqlite3")
    ]
    assert store.revision_requests == [
        REVISION_ID
    ]
    assert store.snapshot_requests == [
        REVISION_ID
    ]


def test_progress_application_reports_missing_revision(
    tmp_path,
    monkeypatch,
):
    store = RecordingStore(
        _snapshot(),
        revision_exists=False,
    )

    monkeypatch.setattr(
        application,
        "SQLiteResearchCatalogStore",
        lambda _path: store,
    )

    config = AppConfig(
        research_database_path=str(
            tmp_path / "research.sqlite3"
        )
    )

    with pytest.raises(
        ResearchRevisionNotFound
    ):
        get_research_progress(
            REVISION_ID,
            app_config=config,
        )

    assert store.revision_requests == [
        REVISION_ID
    ]
    assert store.snapshot_requests == []


def test_progress_response_contract_keeps_trial_and_job_counts_explicit():
    fields = set(
        ResearchProgressResponse.model_fields
    )

    assert fields == {
        "study_revision_id",
        "initial_batch_started_at",
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
        "total_jobs",
    }

    response = ResearchProgressResponse(
        **{
            **_snapshot().__dict__,
            "total_jobs": 9,
        }
    )

    assert (
        response.executed_trials
        + response.reused_trials
        + response.invalid_trials
        + response.insufficient_trials
        + response.failed_trials
        + response.cancelled_trials
        + response.interrupted_trials
        + response.pending_trials
        == response.total_registered_trials
    )

    assert response.total_jobs == 9

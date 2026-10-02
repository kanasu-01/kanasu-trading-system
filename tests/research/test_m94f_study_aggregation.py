from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from core.research.models.registered_study import (
    ResearchJobCompletionKind,
    ResearchJobState,
    TrialDisposition,
)
from core.research.models.research_catalog import (
    ResearchArtifact,
    ResearchArtifactKind,
    RunAttemptState,
)
from core.research.reproducibility import (
    BACKTEST_RESULT_SCHEMA,
    canonical_bytes,
)
from core.research.study_aggregation import (
    StudyAggregationError,
    StudyAggregationService,
)


NOW = datetime(
    2026,
    10,
    2,
    12,
    0,
    tzinfo=timezone.utc,
)

REVISION_ID = "sha256:" + ("a" * 64)
EXECUTED_TRIAL_ID = "sha256:" + ("1" * 64)
REUSED_TRIAL_ID = "sha256:" + ("2" * 64)
FAILED_TRIAL_ID = "sha256:" + ("3" * 64)
CANCELLED_TRIAL_ID = "sha256:" + ("4" * 64)
PENDING_TRIAL_ID = "sha256:" + ("5" * 64)

EXECUTED_ARTIFACT_ID = "sha256:" + ("b" * 64)
REUSED_ARTIFACT_ID = "sha256:" + ("c" * 64)


def _trial(
    trial_id,
    disposition,
):
    return SimpleNamespace(
        trial_id=trial_id,
        study_revision_id=REVISION_ID,
        disposition=disposition,
        reused_attempt_id=(
            "attempt-reused"
            if disposition is TrialDisposition.REUSED
            else None
        ),
    )


def _executed_job():
    return SimpleNamespace(
        job_id="job-executed",
        trial_id=EXECUTED_TRIAL_ID,
        state=ResearchJobState.SUCCEEDED,
        completion_kind=(
            ResearchJobCompletionKind.EXECUTED
        ),
        attempt_id="attempt-executed",
        reused_attempt_id=None,
        reused_result_artifact_id=None,
    )


def _reused_job():
    return SimpleNamespace(
        job_id="job-reused",
        trial_id=REUSED_TRIAL_ID,
        state=ResearchJobState.SUCCEEDED,
        completion_kind=(
            ResearchJobCompletionKind.REUSED
        ),
        attempt_id=None,
        reused_attempt_id="attempt-reused",
        reused_result_artifact_id=(
            REUSED_ARTIFACT_ID
        ),
    )


def _terminal_event(
    *,
    trial_id,
    disposition,
    job_id,
):
    return SimpleNamespace(
        trial_id=trial_id,
        new_disposition=disposition,
        causing_job_id=job_id,
    )


def _attempt():
    return SimpleNamespace(
        attempt_id="attempt-executed",
        state=RunAttemptState.SUCCEEDED,
        result_artifact_id=EXECUTED_ARTIFACT_ID,
    )


def _artifact(artifact_id):
    return ResearchArtifact(
        artifact_id=artifact_id,
        artifact_kind=(
            ResearchArtifactKind.BACKTEST_RESULT
        ),
        schema_id=BACKTEST_RESULT_SCHEMA,
        relative_path=(
            artifact_id.removeprefix("sha256:")
            + ".json"
        ),
        byte_count=1,
        created_at=NOW,
    )


def _result_bytes(
    *,
    equities,
):
    payload = {
        "trades": [],
        "bar_records": [
            {
                "equity": float(equity),
            }
            for equity in equities
        ],
        "equity_curve": [
            (
                NOW,
                float(equity),
            )
            for equity in equities
        ],
    }

    return canonical_bytes(
        payload,
        schema=BACKTEST_RESULT_SCHEMA,
    )


class CatalogStub:
    def __init__(self):
        self.trials = (
            _trial(
                EXECUTED_TRIAL_ID,
                TrialDisposition.EXECUTED,
            ),
            _trial(
                REUSED_TRIAL_ID,
                TrialDisposition.REUSED,
            ),
            _trial(
                FAILED_TRIAL_ID,
                TrialDisposition.FAILED,
            ),
            _trial(
                CANCELLED_TRIAL_ID,
                TrialDisposition.CANCELLED,
            ),
            _trial(
                PENDING_TRIAL_ID,
                TrialDisposition.PENDING,
            ),
        )

        self.jobs = {
            EXECUTED_TRIAL_ID: (
                _executed_job(),
            ),
            REUSED_TRIAL_ID: (
                _reused_job(),
            ),
            FAILED_TRIAL_ID: (),
            CANCELLED_TRIAL_ID: (),
            PENDING_TRIAL_ID: (),
        }

        self.events = {
            EXECUTED_TRIAL_ID: (
                _terminal_event(
                    trial_id=EXECUTED_TRIAL_ID,
                    disposition=TrialDisposition.EXECUTED,
                    job_id="job-executed",
                ),
            ),
            REUSED_TRIAL_ID: (
                _terminal_event(
                    trial_id=REUSED_TRIAL_ID,
                    disposition=TrialDisposition.REUSED,
                    job_id="job-reused",
                ),
            ),
            FAILED_TRIAL_ID: (),
            CANCELLED_TRIAL_ID: (),
            PENDING_TRIAL_ID: (),
        }

        self.attempts = {
            "attempt-executed": _attempt(),
            "attempt-reused": SimpleNamespace(
                attempt_id="attempt-reused",
                state=RunAttemptState.SUCCEEDED,
                result_artifact_id=REUSED_ARTIFACT_ID,
            ),
        }

        self.artifacts = {
            EXECUTED_ARTIFACT_ID: _artifact(
                EXECUTED_ARTIFACT_ID
            ),
            REUSED_ARTIFACT_ID: _artifact(
                REUSED_ARTIFACT_ID
            ),
        }

    def load_study_revision(
        self,
        study_revision_id,
    ):
        if study_revision_id != REVISION_ID:
            return None

        return object()

    def list_trials_for_revision(
        self,
        study_revision_id,
    ):
        assert study_revision_id == REVISION_ID
        return self.trials

    def list_research_jobs_for_trial(
        self,
        trial_id,
    ):
        return self.jobs[trial_id]

    def load_trial_disposition_events(
        self,
        trial_id,
    ):
        return self.events.get(
            trial_id,
            (),
        )

    def load_research_job(
        self,
        job_id,
    ):
        for jobs in self.jobs.values():
            for job in jobs:
                if job.job_id == job_id:
                    return job

        return None

    def load_run_attempt(
        self,
        attempt_id,
    ):
        return self.attempts.get(
            attempt_id
        )

    def load_artifact(
        self,
        artifact_id,
    ):
        return self.artifacts.get(
            artifact_id
        )


class ArtifactStoreStub:
    def __init__(self):
        self.payloads = {
            EXECUTED_ARTIFACT_ID: _result_bytes(
                equities=(100.0, 120.0, 108.0),
            ),
            REUSED_ARTIFACT_ID: _result_bytes(
                equities=(100.0, 95.0, 95.0),
            ),
        }

    def load_bytes(
        self,
        artifact_id,
    ):
        return self.payloads[
            artifact_id
        ]


def test_aggregation_reports_explicit_denominators_and_partial_failures():
    result = StudyAggregationService(
        catalog_store=CatalogStub(),
        artifact_store=ArtifactStoreStub(),
    ).aggregate_revision(
        REVISION_ID
    )

    assert result.study_revision_id == REVISION_ID
    assert result.aggregation_basis == (
        "INDEPENDENT_TRIAL_ACCOUNT_DISTRIBUTION"
    )

    assert result.total_registered_trials == 5
    assert result.result_bearing_trials == 2
    assert result.excluded_trials == 3

    assert result.executed_trials == 1
    assert result.reused_trials == 1
    assert result.pending_trials == 1
    assert result.failed_trials == 1
    assert result.cancelled_trials == 1
    assert result.invalid_trials == 0
    assert result.insufficient_trials == 0
    assert result.interrupted_trials == 0

    returns = result.account_return_pct

    assert returns.count == 2
    assert returns.mean == pytest.approx(
        1.5
    )
    assert returns.median == pytest.approx(
        1.5
    )
    assert returns.minimum == pytest.approx(
        -5.0
    )
    assert returns.maximum == pytest.approx(
        8.0
    )
    assert returns.positive_count == 1
    assert (
        returns.positive_proportion
        == pytest.approx(0.5)
    )

    drawdown = result.max_equity_drawdown_pct

    assert drawdown.count == 2
    assert drawdown.mean == pytest.approx(
        7.5
    )
    assert drawdown.median == pytest.approx(
        7.5
    )
    assert drawdown.minimum == pytest.approx(
        5.0
    )
    assert drawdown.maximum == pytest.approx(
        10.0
    )

    assert "portfolio_pnl" not in result.__dict__
    assert "portfolio_return" not in result.__dict__
    assert "total_pnl" not in result.__dict__


def test_aggregation_resolves_executed_and_reused_result_lineage():
    catalog = CatalogStub()
    artifact_store = ArtifactStoreStub()

    service = StudyAggregationService(
        catalog_store=catalog,
        artifact_store=artifact_store,
    )

    result = service.aggregate_revision(
        REVISION_ID
    )

    assert result.result_bearing_trials == 2

    assert set(
        result.result_artifact_ids
    ) == {
        EXECUTED_ARTIFACT_ID,
        REUSED_ARTIFACT_ID,
    }


def test_result_bearing_trial_requires_one_truthful_success_lineage():
    catalog = CatalogStub()
    catalog.jobs[
        EXECUTED_TRIAL_ID
    ] = ()

    with pytest.raises(
        StudyAggregationError,
        match="result-bearing Trial",
    ):
        StudyAggregationService(
            catalog_store=catalog,
            artifact_store=ArtifactStoreStub(),
        ).aggregate_revision(
            REVISION_ID
        )


def test_result_artifact_must_be_canonical_backtest_result():
    catalog = CatalogStub()

    catalog.artifacts[
        EXECUTED_ARTIFACT_ID
    ] = ResearchArtifact(
        artifact_id=EXECUTED_ARTIFACT_ID,
        artifact_kind=(
            ResearchArtifactKind.DATASET_REFERENCE
        ),
        schema_id="kanasu.dataset-reference.v1",
        relative_path="fixture.json",
        byte_count=1,
        created_at=NOW,
    )

    with pytest.raises(
        StudyAggregationError,
        match="canonical Backtest result",
    ):
        StudyAggregationService(
            catalog_store=catalog,
            artifact_store=ArtifactStoreStub(),
        ).aggregate_revision(
            REVISION_ID
        )


def test_missing_revision_is_rejected():
    with pytest.raises(
        StudyAggregationError,
        match="StudyRevision does not exist",
    ):
        StudyAggregationService(
            catalog_store=CatalogStub(),
            artifact_store=ArtifactStoreStub(),
        ).aggregate_revision(
            "sha256:" + ("f" * 64)
        )

def test_retry_history_does_not_make_current_result_lineage_ambiguous():
    catalog = CatalogStub()

    historical_job = SimpleNamespace(
        job_id="job-executed-historical",
        trial_id=EXECUTED_TRIAL_ID,
        state=ResearchJobState.SUCCEEDED,
        completion_kind=(
            ResearchJobCompletionKind.EXECUTED
        ),
        attempt_id="attempt-historical",
        reused_attempt_id=None,
        reused_result_artifact_id=None,
    )

    catalog.jobs[
        EXECUTED_TRIAL_ID
    ] = (
        historical_job,
        *catalog.jobs[
            EXECUTED_TRIAL_ID
        ],
    )

    catalog.attempts[
        "attempt-historical"
    ] = SimpleNamespace(
        attempt_id="attempt-historical",
        state=RunAttemptState.SUCCEEDED,
        result_artifact_id=(
            "sha256:" + ("d" * 64)
        ),
    )

    result = StudyAggregationService(
        catalog_store=catalog,
        artifact_store=ArtifactStoreStub(),
    ).aggregate_revision(
        REVISION_ID
    )

    assert result.result_bearing_trials == 2
    assert set(
        result.result_artifact_ids
    ) == {
        EXECUTED_ARTIFACT_ID,
        REUSED_ARTIFACT_ID,
    }


def test_zero_result_aggregation_preserves_all_excluded_denominators():
    catalog = CatalogStub()

    dispositions = (
        TrialDisposition.INVALID,
        TrialDisposition.INSUFFICIENT,
        TrialDisposition.FAILED,
        TrialDisposition.CANCELLED,
        TrialDisposition.INTERRUPTED,
    )

    catalog.trials = tuple(
        _trial(
            "sha256:"
            + str(index + 6) * 64,
            disposition,
        )
        for index, disposition
        in enumerate(dispositions)
    )

    result = StudyAggregationService(
        catalog_store=catalog,
        artifact_store=ArtifactStoreStub(),
    ).aggregate_revision(
        REVISION_ID
    )

    assert result.total_registered_trials == 5
    assert result.result_bearing_trials == 0
    assert result.excluded_trials == 5

    assert result.pending_trials == 0
    assert result.executed_trials == 0
    assert result.reused_trials == 0
    assert result.invalid_trials == 1
    assert result.insufficient_trials == 1
    assert result.failed_trials == 1
    assert result.cancelled_trials == 1
    assert result.interrupted_trials == 1

    for distribution in (
        result.account_return_pct,
        result.max_equity_drawdown_pct,
    ):
        assert distribution.count == 0
        assert distribution.mean is None
        assert distribution.median is None
        assert distribution.minimum is None
        assert distribution.maximum is None
        assert distribution.positive_count == 0
        assert distribution.positive_proportion is None

    assert result.result_artifact_ids == ()

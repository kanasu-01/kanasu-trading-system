from contextlib import closing
from datetime import datetime, timezone
import sqlite3

import pytest

from core.config.app_config import AppConfig
from core.market_data.historical_coverage import TimeRange
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    ResearchJobState,
    Study,
    TrialDisposition,
)
from core.research.models.research_catalog import (
    ComputationKind,
    ResearchArtifact,
    ResearchArtifactKind,
    RunAttemptState,
)
from core.research.models.universe import (
    UniverseDefinition,
    UniverseQuality,
    UniverseSnapshot,
)
from core.research.registered_study_registration import (
    RegisteredStudyRegistrationService,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.research_job_queue import (
    ResearchJobQueueService,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)


UTC = timezone.utc

JAN = datetime(2020, 1, 1, tzinfo=UTC)
FEB = datetime(2020, 2, 1, tzinfo=UTC)
MAR = datetime(2020, 3, 1, tzinfo=UTC)
APR = datetime(2020, 4, 1, tzinfo=UTC)
MAY = datetime(2020, 5, 1, tzinfo=UTC)
JUN = datetime(2020, 6, 1, tzinfo=UTC)
JUL = datetime(2020, 7, 1, tzinfo=UTC)


def _environment(
    tmp_path,
    *,
    claim_job: bool,
    parameter_variants=(
        {
            "variant": 1,
        },
    ),
):
    catalog = SQLiteResearchCatalogStore(
        tmp_path / "research.sqlite3"
    )

    artifact_store = (
        ContentAddressedResearchArtifactStore(
            tmp_path / "artifacts"
        )
    )

    catalog.save_study(
        Study(
            study_id="study-m94e",
            created_at=JAN,
            display_title="M9.4e cancellation",
        )
    )

    registration = (
        RegisteredStudyRegistrationService(
            catalog_store=catalog,
            artifact_store=artifact_store,
        )
    )

    definition = UniverseDefinition(
        name="m94e-universe",
        selection_spec="fixture",
    )

    snapshot = UniverseSnapshot(
        definition=definition,
        members=("NSE:A",),
        quality=UniverseQuality.PIT_VERIFIED,
        as_of=JAN,
        provenance_refs=("m94e-source",),
        effective_from=JAN,
        effective_to=FEB,
    )

    population = (
        registration.register_study_revision(
            study_id="study-m94e",
            research_intent=(
                "M9.4e cancellation and recovery"
            ),
            strategy_procedure_id="fixture-v1",
            timeframe="1d",
            research_range=TimeRange(
                JAN,
                FEB,
            ),
            timezone="UTC",
            initial_capital=1_000_000.0,
            risk_economic_configuration={
                "risk_per_trade_pct": 1.0,
            },
            parameter_variants=parameter_variants,
            universe_definition=definition,
            universe_snapshots=(
                snapshot,
            ),
            require_point_in_time=True,
            data_treatment_basis={
                "adjustment": "raw",
            },
            repository_revision="repo-m94e",
            evidence_reuse_policy=(
                EvidenceReusePolicy.FORCE_NEW_EXECUTION
            ),
            registered_at=MAR,
        )
    )

    queue = ResearchJobQueueService(
        catalog_store=catalog,
        app_config=AppConfig(
            research_max_workers=1
        ),
    )

    revision_id = (
        population.revision.study_revision_id
    )

    queue.start_revision(
        revision_id,
        started_at=APR,
    )

    trial = population.trials[0]

    jobs = (
        catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
    )

    assert len(jobs) == 1

    job = jobs[0]

    if claim_job:
        claimed = (
            catalog.claim_next_research_job(
                revision_id,
                "worker-m94e",
                MAY,
                max_running_jobs=1,
            )
        )

        assert claimed is not None
        job = claimed

    return (
        catalog,
        trial,
        job,
    )


def _attempt_count(
    catalog: SQLiteResearchCatalogStore,
) -> int:
    with closing(
        sqlite3.connect(
            catalog.database_path
        )
    ) as connection:
        return connection.execute(
            """
            SELECT COUNT(*)
            FROM run_attempts
            """
        ).fetchone()[0]


def test_queued_cancellation_terminalizes_job_and_trial_without_attempt(
    tmp_path,
):
    catalog, trial, job = _environment(
        tmp_path,
        claim_job=False,
    )

    before_attempts = _attempt_count(
        catalog
    )

    updated_trial, updated_job, event = (
        catalog.cancel_queued_research_job(
            job_id=job.job_id,
            terminal_at=MAY,
        )
    )

    assert _attempt_count(catalog) == before_attempts

    assert (
        updated_job.state
        is ResearchJobState.CANCELLED
    )
    assert updated_job.claimed_at is None
    assert updated_job.worker_id is None
    assert updated_job.attempt_id is None
    assert updated_job.cancel_requested_at is None
    assert updated_job.terminal_at == MAY

    assert (
        updated_trial.disposition
        is TrialDisposition.CANCELLED
    )
    assert updated_trial.disposition_at == MAY
    assert updated_trial.experiment_spec_id is None

    assert event is not None
    assert event.sequence_number == 2
    assert (
        event.previous_disposition
        is TrialDisposition.PENDING
    )
    assert (
        event.new_disposition
        is TrialDisposition.CANCELLED
    )
    assert event.causing_job_id == job.job_id
    assert (
        event.reason_classification
        == "queued_cancellation"
    )

    events = (
        catalog.load_trial_disposition_events(
            trial.trial_id
        )
    )

    assert len(events) == 2


def test_running_cancellation_request_is_durable_but_job_stays_running(
    tmp_path,
):
    catalog, trial, job = _environment(
        tmp_path,
        claim_job=True,
    )

    before_attempts = _attempt_count(
        catalog
    )

    requested = (
        catalog
        .request_running_research_job_cancellation(
            job_id=job.job_id,
            requested_at=JUN,
        )
    )

    assert _attempt_count(catalog) == before_attempts

    assert (
        requested.state
        is ResearchJobState.RUNNING
    )
    assert requested.claimed_at == MAY
    assert requested.worker_id == "worker-m94e"
    assert requested.terminal_at is None
    assert requested.attempt_id is None
    assert requested.cancel_requested_at == JUN

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.PENDING
    )

    assert len(
        catalog.load_trial_disposition_events(
            trial.trial_id
        )
    ) == 1


def test_repeated_running_cancellation_request_preserves_first_request_time(
    tmp_path,
):
    catalog, _, job = _environment(
        tmp_path,
        claim_job=True,
    )

    first = (
        catalog
        .request_running_research_job_cancellation(
            job_id=job.job_id,
            requested_at=JUN,
        )
    )

    second = (
        catalog
        .request_running_research_job_cancellation(
            job_id=job.job_id,
            requested_at=JUL,
        )
    )

    assert first.cancel_requested_at == JUN
    assert second.cancel_requested_at == JUN
    assert (
        second.state
        is ResearchJobState.RUNNING
    )


def test_queued_cancellation_can_be_explicitly_retried_without_new_trial(
    tmp_path,
):
    catalog, trial, job = _environment(
        tmp_path,
        claim_job=False,
    )

    catalog.cancel_queued_research_job(
        job_id=job.job_id,
        terminal_at=MAY,
    )

    updated_trial, retry_job, event = (
        catalog.retry_trial(
            trial.trial_id,
            retry_requested_at=JUN,
        )
    )

    assert updated_trial.trial_id == trial.trial_id
    assert (
        updated_trial.disposition
        is TrialDisposition.PENDING
    )
    assert (
        retry_job.state
        is ResearchJobState.QUEUED
    )
    assert retry_job.attempt_id is None

    assert (
        event.previous_disposition
        is TrialDisposition.CANCELLED
    )
    assert (
        event.new_disposition
        is TrialDisposition.PENDING
    )
    assert (
        event.reason_classification
        == "explicit_retry"
    )

    jobs = (
        catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
    )

    assert len(jobs) == 2
    assert {
        value.state
        for value in jobs
    } == {
        ResearchJobState.CANCELLED,
        ResearchJobState.QUEUED,
    }


def test_wrong_cancellation_operation_refuses_incompatible_job_state(
    tmp_path,
):
    catalog, _, running_job = _environment(
        tmp_path,
        claim_job=True,
    )

    with pytest.raises(
        ValueError,
        match="queued cancellation requires a QUEUED ResearchJob",
    ):
        catalog.cancel_queued_research_job(
            job_id=running_job.job_id,
            terminal_at=JUN,
        )

    assert (
        catalog.load_research_job(
            running_job.job_id
        ).state
        is ResearchJobState.RUNNING
    )



def test_running_cancellation_checkpoint_acknowledges_before_attempt(
    tmp_path,
):
    catalog, trial, job = _environment(
        tmp_path,
        claim_job=True,
    )

    catalog.request_running_research_job_cancellation(
        job_id=job.job_id,
        requested_at=JUN,
    )

    updated_trial, updated_job, event = (
        catalog
        .acknowledge_running_research_job_cancellation(
            job_id=job.job_id,
            terminal_at=JUL,
        )
    )

    assert (
        updated_job.state
        is ResearchJobState.CANCELLED
    )
    assert updated_job.claimed_at == MAY
    assert updated_job.worker_id == "worker-m94e"
    assert updated_job.cancel_requested_at == JUN
    assert updated_job.terminal_at == JUL
    assert updated_job.attempt_id is None
    assert updated_job.completion_kind is None
    assert updated_job.reused_attempt_id is None
    assert updated_job.failure_classification is None
    assert updated_job.failure_message is None
    assert _attempt_count(catalog) == 0

    assert (
        updated_trial.disposition
        is TrialDisposition.CANCELLED
    )
    assert updated_trial.disposition_at == JUL

    assert (
        event.previous_disposition
        is TrialDisposition.PENDING
    )
    assert (
        event.new_disposition
        is TrialDisposition.CANCELLED
    )
    assert event.causing_job_id == job.job_id
    assert (
        event.reason_classification
        == "running_cancellation_acknowledged"
    )


def test_running_cancellation_checkpoint_requires_durable_request(
    tmp_path,
):
    catalog, _, job = _environment(
        tmp_path,
        claim_job=True,
    )

    with pytest.raises(
        ValueError,
        match="cancellation request",
    ):
        catalog.acknowledge_running_research_job_cancellation(
            job_id=job.job_id,
            terminal_at=JUN,
        )

    persisted = catalog.load_research_job(
        job.job_id
    )

    assert persisted is not None
    assert (
        persisted.state
        is ResearchJobState.RUNNING
    )
    assert persisted.cancel_requested_at is None


def test_restart_recovery_interrupts_running_job_without_attempt(
    tmp_path,
):
    catalog, trial, job = _environment(
        tmp_path,
        claim_job=True,
    )

    recovered = catalog.recover_running_research_jobs(
        terminal_at=JUN,
    )

    assert len(recovered) == 1
    assert recovered[0].job_id == job.job_id
    assert (
        recovered[0].state
        is ResearchJobState.INTERRUPTED
    )
    assert recovered[0].terminal_at == JUN
    assert recovered[0].attempt_id is None
    assert (
        recovered[0].failure_classification
        == "application_restart"
    )

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.INTERRUPTED
    )
    assert persisted_trial.disposition_at == JUN

    events = catalog.load_trial_disposition_events(
        trial.trial_id
    )

    assert len(events) == 2
    assert (
        events[-1].new_disposition
        is TrialDisposition.INTERRUPTED
    )
    assert (
        events[-1].reason_classification
        == "application_restart"
    )

    jobs = catalog.list_research_jobs_for_trial(
        trial.trial_id
    )

    assert len(jobs) == 1
    assert all(
        value.state
        is not ResearchJobState.QUEUED
        for value in jobs
    )

    assert catalog.recover_running_research_jobs(
        terminal_at=JUL,
    ) == ()



def test_restart_recovery_interrupts_running_job_with_linked_attempt(
    tmp_path,
):
    catalog, trial, job = _environment(
        tmp_path,
        claim_job=True,
    )

    manifest_id = "sha256:" + ("a" * 64)

    catalog.save_artifact(
        ResearchArtifact(
            artifact_id=manifest_id,
            artifact_kind=(
                ResearchArtifactKind.BACKTEST_RUN_MANIFEST
            ),
            schema_id="kanasu.backtest-run-manifest.v1",
            relative_path=(
                "m94e/"
                + ("a" * 64)
                + ".json"
            ),
            byte_count=2,
            created_at=APR,
        )
    )

    spec = catalog.resolve_experiment_spec(
        computation_kind=ComputationKind.BACKTEST,
        manifest_artifact_id=manifest_id,
        dataset_fingerprint=(
            "sha256:" + ("b" * 64)
        ),
        configuration_fingerprint=(
            "sha256:" + ("c" * 64)
        ),
        repository_revision="repo-m94e",
        created_at=APR,
    )

    (
        bound_trial,
        bound_job,
        attempt,
    ) = (
        catalog
        .bind_trial_spec_create_attempt_for_running_job(
            job_id=job.job_id,
            experiment_spec_id=(
                spec.experiment_spec_id
            ),
            attempt_created_at=JUN,
        )
    )

    assert (
        bound_trial.experiment_spec_id
        == spec.experiment_spec_id
    )
    assert (
        bound_job.attempt_id
        == attempt.attempt_id
    )
    assert (
        attempt.state
        is RunAttemptState.RUNNING
    )
    assert _attempt_count(catalog) == 1

    recovered = catalog.recover_running_research_jobs(
        terminal_at=JUL,
    )

    assert len(recovered) == 1

    recovered_job = recovered[0]

    assert recovered_job.job_id == job.job_id
    assert (
        recovered_job.state
        is ResearchJobState.INTERRUPTED
    )
    assert recovered_job.terminal_at == JUL
    assert (
        recovered_job.attempt_id
        == attempt.attempt_id
    )
    assert (
        recovered_job.failure_classification
        == "application_restart"
    )

    persisted_attempt = catalog.load_run_attempt(
        attempt.attempt_id
    )

    assert persisted_attempt is not None
    assert (
        persisted_attempt.state
        is RunAttemptState.INTERRUPTED
    )
    assert persisted_attempt.terminal_at == JUL
    assert persisted_attempt.result_artifact_id is None
    assert persisted_attempt.evidence_id is None
    assert (
        persisted_attempt.failure_classification
        == "application_restart"
    )

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.INTERRUPTED
    )
    assert persisted_trial.disposition_at == JUL
    assert (
        persisted_trial.experiment_spec_id
        == spec.experiment_spec_id
    )

    jobs = catalog.list_research_jobs_for_trial(
        trial.trial_id
    )

    assert len(jobs) == 1
    assert (
        jobs[0].state
        is ResearchJobState.INTERRUPTED
    )
    assert _attempt_count(catalog) == 1

    assert catalog.recover_running_research_jobs(
        terminal_at=JUL,
    ) == ()



def test_batch_cancellation_cancels_queued_and_requests_running_without_retry(
    tmp_path,
):
    catalog, first_trial, _ = _environment(
        tmp_path,
        claim_job=False,
        parameter_variants=(
            {
                "variant": 1,
            },
            {
                "variant": 2,
            },
            {
                "variant": 3,
            },
        ),
    )

    revision_id = first_trial.study_revision_id

    trials_before = catalog.list_trials_for_revision(
        revision_id
    )

    assert len(trials_before) == 3

    jobs_before = tuple(
        job
        for trial in trials_before
        for job in catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
    )

    assert len(jobs_before) == 3
    assert all(
        job.state is ResearchJobState.QUEUED
        for job in jobs_before
    )

    running = catalog.claim_next_research_job(
        revision_id,
        "worker-m94e-batch",
        MAY,
        max_running_jobs=1,
    )

    assert running is not None
    assert (
        running.state
        is ResearchJobState.RUNNING
    )

    attempts_before = _attempt_count(
        catalog
    )

    catalog.cancel_study_revision_batch(
        study_revision_id=revision_id,
        requested_at=JUN,
    )

    trials_after = catalog.list_trials_for_revision(
        revision_id
    )

    jobs_after = tuple(
        job
        for trial in trials_after
        for job in catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
    )

    assert len(trials_after) == len(trials_before)
    assert len(jobs_after) == len(jobs_before)
    assert _attempt_count(catalog) == attempts_before

    running_after = next(
        job
        for job in jobs_after
        if job.job_id == running.job_id
    )

    assert (
        running_after.state
        is ResearchJobState.RUNNING
    )
    assert running_after.cancel_requested_at == JUN
    assert running_after.terminal_at is None
    assert running_after.attempt_id is None

    queued_after = tuple(
        job
        for job in jobs_after
        if job.job_id != running.job_id
    )

    assert len(queued_after) == 2

    assert all(
        job.state is ResearchJobState.CANCELLED
        for job in queued_after
    )

    assert all(
        job.terminal_at == JUN
        for job in queued_after
    )

    assert all(
        job.cancel_requested_at is None
        for job in queued_after
    )

    assert all(
        job.attempt_id is None
        for job in queued_after
    )

    trials_by_id = {
        trial.trial_id: trial
        for trial in trials_after
    }

    assert (
        trials_by_id[
            running_after.trial_id
        ].disposition
        is TrialDisposition.PENDING
    )

    for job in queued_after:
        assert (
            trials_by_id[
                job.trial_id
            ].disposition
            is TrialDisposition.CANCELLED
        )

    assert all(
        len(
            catalog.list_research_jobs_for_trial(
                trial.trial_id
            )
        ) == 1
        for trial in trials_after
    )

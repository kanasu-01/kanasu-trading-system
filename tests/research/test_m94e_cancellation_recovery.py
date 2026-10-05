from contextlib import closing
from datetime import datetime, timezone, timedelta
import sqlite3

import pytest

from core.config.app_config import AppConfig
from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.research.models.dataset import (
    DatasetIdentityV2,
    DatasetProvenance,
    PriceAdjustmentBasis,
)
from core.research.models.dataset_reference import (
    DatasetReference,
)
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    ResearchJobCompletionKind,
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
from core.research.models.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStatus,
)
from core.research.reproducibility import (
    BACKTEST_RESULT_SCHEMA,
    BACKTEST_RUN_MANIFEST_SCHEMA,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
    research_artifact_reference,
)
from core.runtime.dataset_context import DatasetContext
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


def _persist_m94h2_dataset_reference(
    catalog,
    artifact_store,
    *,
    source,
    created_at,
):
    candle = Candle(
        timestamp=JAN,
        open=100.0,
        high=102.0,
        low=99.0,
        close=101.0,
        volume=1000.0,
    )

    identity = DatasetIdentityV2(
        instrument_id="NSE:A",
        requested_range=TimeRange(
            JAN,
            FEB,
        ),
        timeframe="1d",
        timezone="UTC",
        price_adjustment_basis=(
            PriceAdjustmentBasis.RAW
        ),
        candles=(candle,),
    )

    reference = DatasetReference(
        identity=identity,
        provenance=DatasetProvenance(
            dataset_id=identity.dataset_id,
            instrument_id="NSE:A",
            requested_range=TimeRange(
                JAN,
                FEB,
            ),
            timeframe="1d",
            timezone="UTC",
            price_adjustment_basis=(
                PriceAdjustmentBasis.RAW
            ),
            source=source,
            coverage=(
                TimeRange(
                    JAN,
                    FEB,
                ),
            ),
            retrieved_at=created_at,
        ),
    )

    artifact = (
        artifact_store
        .persist_dataset_reference(
            reference,
            created_at=created_at,
        )
    )

    return (
        catalog
        .save_dataset_reference_artifact(
            artifact,
            reference,
        )
    )


def _environment(
    tmp_path,
    *,
    claim_job: bool,
    parameter_variants=(
        {
            "variant": 1,
        },
    ),
    evidence_reuse_policy=(
        EvidenceReusePolicy.FORCE_NEW_EXECUTION
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
                evidence_reuse_policy
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

def test_m94g4_recovery_persistence_failure_rolls_back_and_startup_refuses_to_continue(
    tmp_path,
    monkeypatch,
):
    import api.main as main_module

    catalog, trial, job = _environment(
        tmp_path,
        claim_job=True,
    )

    manifest_id = "sha256:" + ("e" * 64)

    catalog.save_artifact(
        ResearchArtifact(
            artifact_id=manifest_id,
            artifact_kind=(
                ResearchArtifactKind.BACKTEST_RUN_MANIFEST
            ),
            schema_id="kanasu.backtest-run-manifest.v1",
            relative_path=(
                "m94g4/"
                + ("e" * 64)
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
            "sha256:" + ("f" * 64)
        ),
        configuration_fingerprint=(
            "sha256:" + ("1" * 64)
        ),
        repository_revision="repo-m94g4",
        created_at=APR,
    )

    (
        _bound_trial,
        _bound_job,
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

    original_connect = catalog._connect

    class FailingRecoveryConnection:
        def __init__(self, connection):
            self._connection = connection

        def execute(self, sql, *args, **kwargs):
            normalized = " ".join(
                sql.split()
            ).upper()

            if normalized.startswith(
                "UPDATE TRIALS SET"
            ):
                raise sqlite3.OperationalError(
                    "forced recovery persistence failure"
                )

            return self._connection.execute(
                sql,
                *args,
                **kwargs,
            )

        def commit(self):
            return self._connection.commit()

        def rollback(self):
            return self._connection.rollback()

        def close(self):
            return self._connection.close()

        def __getattr__(self, name):
            return getattr(
                self._connection,
                name,
            )

    def failing_connect():
        return FailingRecoveryConnection(
            original_connect()
        )

    monkeypatch.setattr(
        catalog,
        "_connect",
        failing_connect,
    )

    class StartupConfig:
        research_database_path = (
            catalog.database_path
        )

    monkeypatch.setattr(
        main_module,
        "load_app_config",
        lambda: StartupConfig(),
    )

    monkeypatch.setattr(
        main_module,
        "SQLiteResearchCatalogStore",
        lambda _path: catalog,
    )

    with pytest.raises(
        sqlite3.OperationalError,
        match="forced recovery persistence failure",
    ):
        main_module.recover_stale_research_attempts()

    monkeypatch.setattr(
        catalog,
        "_connect",
        original_connect,
    )

    persisted_attempt = (
        catalog.load_run_attempt(
            attempt.attempt_id
        )
    )
    persisted_job = (
        catalog.load_research_job(
            job.job_id
        )
    )
    persisted_trial = (
        catalog.load_trial(
            trial.trial_id
        )
    )

    assert persisted_attempt is not None
    assert (
        persisted_attempt.state
        is RunAttemptState.RUNNING
    )
    assert persisted_attempt.terminal_at is None
    assert persisted_attempt.evidence_id is None
    assert persisted_attempt.result_artifact_id is None

    assert persisted_job is not None
    assert (
        persisted_job.state
        is ResearchJobState.RUNNING
    )
    assert persisted_job.terminal_at is None
    assert persisted_job.attempt_id == attempt.attempt_id

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.PENDING
    )

    events = (
        catalog.load_trial_disposition_events(
            trial.trial_id
        )
    )

    assert len(events) == 1
    assert (
        events[0].new_disposition
        is TrialDisposition.PENDING
    )


def test_m94g4_retry_after_recovered_interrupted_bound_work_preserves_spec_and_history(
    tmp_path,
):
    catalog, trial, job = _environment(
        tmp_path,
        claim_job=True,
    )

    manifest_id = "sha256:" + ("7" * 64)

    catalog.save_artifact(
        ResearchArtifact(
            artifact_id=manifest_id,
            artifact_kind=(
                ResearchArtifactKind.BACKTEST_RUN_MANIFEST
            ),
            schema_id="kanasu.backtest-run-manifest.v1",
            relative_path=(
                "m94g4/"
                + ("7" * 64)
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
            "sha256:" + ("8" * 64)
        ),
        configuration_fingerprint=(
            "sha256:" + ("9" * 64)
        ),
        repository_revision="repo-m94g4-retry",
        created_at=APR,
    )

    (
        _bound_trial,
        _bound_job,
        interrupted_attempt,
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

    recovered = (
        catalog.recover_running_research_jobs(
            terminal_at=JUL,
        )
    )

    assert len(recovered) == 1
    assert (
        recovered[0].state
        is ResearchJobState.INTERRUPTED
    )

    recovered_trial = (
        catalog.load_trial(
            trial.trial_id
        )
    )

    assert recovered_trial is not None
    assert (
        recovered_trial.disposition
        is TrialDisposition.INTERRUPTED
    )
    assert (
        recovered_trial.experiment_spec_id
        == spec.experiment_spec_id
    )

    (
        pending_trial,
        retry_job,
        retry_event,
    ) = catalog.retry_trial(
        trial.trial_id,
        retry_requested_at=(
            JUL + timedelta(
                seconds=1,
            )
        ),
    )

    assert (
        pending_trial.disposition
        is TrialDisposition.PENDING
    )
    assert (
        pending_trial.experiment_spec_id
        == spec.experiment_spec_id
    )
    assert (
        retry_job.state
        is ResearchJobState.QUEUED
    )
    assert retry_job.attempt_id is None
    assert (
        retry_event.previous_disposition
        is TrialDisposition.INTERRUPTED
    )
    assert (
        retry_event.new_disposition
        is TrialDisposition.PENDING
    )

    claimed_retry = (
        catalog.claim_next_research_job(
            trial.study_revision_id,
            "worker-m94g4-retry",
            JUL + timedelta(
                seconds=2,
            ),
            max_running_jobs=1,
        )
    )

    assert claimed_retry is not None
    assert claimed_retry.job_id == retry_job.job_id

    (
        rebound_trial,
        rebound_job,
        retry_attempt,
    ) = (
        catalog
        .bind_trial_spec_create_attempt_for_running_job(
            job_id=claimed_retry.job_id,
            experiment_spec_id=(
                spec.experiment_spec_id
            ),
            attempt_created_at=(
                JUL + timedelta(
                    seconds=3,
                )
            ),
        )
    )

    assert (
        rebound_trial.experiment_spec_id
        == spec.experiment_spec_id
    )
    assert (
        rebound_job.attempt_id
        == retry_attempt.attempt_id
    )
    assert (
        retry_attempt.experiment_spec_id
        == spec.experiment_spec_id
    )
    assert (
        retry_attempt.state
        is RunAttemptState.RUNNING
    )
    assert (
        retry_attempt.attempt_id
        != interrupted_attempt.attempt_id
    )

    persisted_old_attempt = (
        catalog.load_run_attempt(
            interrupted_attempt.attempt_id
        )
    )

    assert persisted_old_attempt is not None
    assert (
        persisted_old_attempt.state
        is RunAttemptState.INTERRUPTED
    )

    jobs = (
        catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
    )

    assert len(jobs) == 2
    assert {
        current.state
        for current in jobs
    } == {
        ResearchJobState.INTERRUPTED,
        ResearchJobState.RUNNING,
    }

    events = (
        catalog.load_trial_disposition_events(
            trial.trial_id
        )
    )

    assert [
        (
            event.previous_disposition,
            event.new_disposition,
        )
        for event in events
    ] == [
        (
            None,
            TrialDisposition.PENDING,
        ),
        (
            TrialDisposition.PENDING,
            TrialDisposition.INTERRUPTED,
        ),
        (
            TrialDisposition.INTERRUPTED,
            TrialDisposition.PENDING,
        ),
    ]

def test_m94g4_mixed_state_restart_recovers_only_running_work(
    tmp_path,
):
    parameter_variants = tuple(
        {
            "variant": value,
        }
        for value in range(1, 7)
    )

    catalog, first_trial, _ = _environment(
        tmp_path,
        claim_job=False,
        parameter_variants=parameter_variants,
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    revision_id = first_trial.study_revision_id

    trials = catalog.list_trials_for_revision(
        revision_id
    )

    assert len(trials) == 6

    jobs_by_trial = {
        trial.trial_id: (
            catalog.list_research_jobs_for_trial(
                trial.trial_id
            )[0]
        )
        for trial in trials
    }

    assert len(jobs_by_trial) == 6
    assert all(
        job.state is ResearchJobState.QUEUED
        for job in jobs_by_trial.values()
    )

    cancelled_trial = trials[-1]
    cancelled_job = jobs_by_trial[
        cancelled_trial.trial_id
    ]

    catalog.cancel_queued_research_job(
        job_id=cancelled_job.job_id,
        terminal_at=MAY,
    )

    def claim(worker_id, claimed_at):
        claimed = catalog.claim_next_research_job(
            revision_id,
            worker_id,
            claimed_at,
            max_running_jobs=1,
        )
        assert claimed is not None
        return claimed

    failed_job = claim(
        "worker-m94g4-failed",
        MAY + timedelta(seconds=1),
    )

    failed_trial_id = failed_job.trial_id

    catalog.fail_running_job_without_attempt(
        job_id=failed_job.job_id,
        terminal_at=MAY + timedelta(seconds=2),
        failure_classification="m94g4_fixture_failure",
        failure_message="expected mixed-state failure",
    )

    def create_spec(label):
        manifest_id = "sha256:" + {
            "executed": "1",
            "reused": "2",
            "running": "3",
        }[label] * 64

        catalog.save_artifact(
            ResearchArtifact(
                artifact_id=manifest_id,
                artifact_kind=(
                    ResearchArtifactKind.BACKTEST_RUN_MANIFEST
                ),
                schema_id=BACKTEST_RUN_MANIFEST_SCHEMA,
                relative_path=(
                    "m94g4/"
                    + manifest_id.split(":", 1)[1]
                    + ".json"
                ),
                byte_count=2,
                created_at=MAY,
            )
        )

        digit = {
            "executed": "4",
            "reused": "5",
            "running": "6",
        }[label]

        config_digit = {
            "executed": "7",
            "reused": "8",
            "running": "9",
        }[label]

        return catalog.resolve_experiment_spec(
            computation_kind=ComputationKind.BACKTEST,
            manifest_artifact_id=manifest_id,
            dataset_fingerprint=(
                "sha256:" + digit * 64
            ),
            configuration_fingerprint=(
                "sha256:" + config_digit * 64
            ),
            repository_revision="repo-m94g4-mixed",
            created_at=MAY,
        )

    artifact_store = (
        ContentAddressedResearchArtifactStore(
            tmp_path / "artifacts"
        )
    )

    def accepted_material(label, spec, created_at):
        payload = (
            '{"m94g4":"'
            + label
            + '"}'
        ).encode("ascii")

        dataset_artifact = (
            _persist_m94h2_dataset_reference(
                catalog,
                artifact_store,
                source=(
                    "fixture:m94g4-mixed-" + label
                ),
                created_at=created_at,
            )
        )

        result_artifact = artifact_store.persist_bytes(
            payload,
            artifact_kind=(
                ResearchArtifactKind.BACKTEST_RESULT
            ),
            schema_id=BACKTEST_RESULT_SCHEMA,
            created_at=created_at,
        )

        evidence = ResearchEvidence(
            evidence_id=(
                "evidence-m94g4-mixed-" + label
            ),
            created_at=created_at,
            status=ResearchEvidenceStatus.ACCEPTED,
            dataset_context=DatasetContext(
                symbol="NSE:A",
                timeframe="1d",
                timezone="UTC",
            ),
            requested_range=TimeRange(
                JAN,
                FEB,
            ),
            dataset_fingerprint=(
                spec.dataset_fingerprint
            ),
            configuration_fingerprint=(
                spec.configuration_fingerprint
            ),
            result_fingerprint=(
                result_artifact.artifact_id
            ),
            provenance=(
                (
                    "fixture",
                    "m94g4-mixed-" + label,
                ),
            ),
            repository_revision=(
                spec.repository_revision
            ),
            summary=(
                "M9.4g4 mixed-state "
                + label
                + " evidence."
            ),
            artifact_references=(
                research_artifact_reference(
                    spec.manifest_artifact_id
                ),
                research_artifact_reference(
                    result_artifact.artifact_id
                ),
                research_artifact_reference(
                    dataset_artifact.artifact_id
                ),
            ),
        )

        return evidence, result_artifact

    executed_job = claim(
        "worker-m94g4-executed",
        MAY + timedelta(seconds=3),
    )
    executed_trial_id = executed_job.trial_id
    executed_spec = create_spec("executed")

    _, _, executed_attempt = (
        catalog
        .bind_trial_spec_create_attempt_for_running_job(
            job_id=executed_job.job_id,
            experiment_spec_id=(
                executed_spec.experiment_spec_id
            ),
            attempt_created_at=(
                MAY + timedelta(seconds=4)
            ),
        )
    )

    (
        executed_evidence,
        executed_result,
    ) = accepted_material(
        "executed",
        executed_spec,
        MAY + timedelta(seconds=5),
    )

    catalog.terminalize_running_job_attempt_with_evidence(
        executed_attempt.attempt_id,
        job_id=executed_job.job_id,
        state=RunAttemptState.SUCCEEDED,
        terminal_at=MAY + timedelta(seconds=5),
        runtime_session_id="runtime-m94g4-executed",
        result_artifact=executed_result,
        evidence=executed_evidence,
    )

    reused_job = claim(
        "worker-m94g4-reused",
        MAY + timedelta(seconds=6),
    )
    reused_trial_id = reused_job.trial_id
    reused_spec = create_spec("reused")

    reuse_source_attempt = catalog.create_running_attempt(
        experiment_spec_id=(
            reused_spec.experiment_spec_id
        ),
        created_at=MAY + timedelta(seconds=7),
    )

    (
        reuse_evidence,
        reuse_result,
    ) = accepted_material(
        "reuse-source",
        reused_spec,
        MAY + timedelta(seconds=8),
    )

    reuse_dataset_artifact_id = None

    for reference in reuse_evidence.artifact_references:
        if not reference.startswith(
            "artifact:"
        ):
            continue

        artifact_id = reference.removeprefix(
            "artifact:"
        )

        artifact = catalog.load_artifact(
            artifact_id
        )

        if (
            artifact is not None
            and artifact.artifact_kind
            is ResearchArtifactKind.DATASET_REFERENCE
        ):
            reuse_dataset_artifact_id = artifact_id
            break

    assert reuse_dataset_artifact_id is not None

    reuse_source = catalog.terminalize_attempt_with_evidence(
        reuse_source_attempt.attempt_id,
        state=RunAttemptState.SUCCEEDED,
        terminal_at=MAY + timedelta(seconds=8),
        runtime_session_id="runtime-m94g4-reuse-source",
        result_artifact=reuse_result,
        evidence=reuse_evidence,
    )

    catalog._complete_running_job_with_exact_reuse(
        job_id=reused_job.job_id,
        experiment_spec_id=(
            reused_spec.experiment_spec_id
        ),
        reused_attempt_id=(
            reuse_source.attempt_id
        ),
        terminal_at=MAY + timedelta(seconds=9),
        requested_dataset_reference_artifact_id=(
            reuse_dataset_artifact_id
        ),
        source_dataset_reference_artifact_id=(
            reuse_dataset_artifact_id
        ),
    )

    running_job = claim(
        "worker-m94g4-running",
        MAY + timedelta(seconds=10),
    )
    running_trial_id = running_job.trial_id
    running_spec = create_spec("running")

    _, _, running_attempt = (
        catalog
        .bind_trial_spec_create_attempt_for_running_job(
            job_id=running_job.job_id,
            experiment_spec_id=(
                running_spec.experiment_spec_id
            ),
            attempt_created_at=(
                MAY + timedelta(seconds=11)
            ),
        )
    )

    trials_before_recovery = {
        trial.trial_id: trial
        for trial in catalog.list_trials_for_revision(
            revision_id
        )
    }

    jobs_before_recovery = {
        trial_id: (
            catalog.list_research_jobs_for_trial(
                trial_id
            )[0]
        )
        for trial_id in trials_before_recovery
    }

    assert len(trials_before_recovery) == 6
    assert len(jobs_before_recovery) == 6

    queued_trial_ids = tuple(
        trial_id
        for trial_id, job in jobs_before_recovery.items()
        if job.state is ResearchJobState.QUEUED
    )

    assert len(queued_trial_ids) == 1

    queued_trial_id = queued_trial_ids[0]

    assert (
        trials_before_recovery[
            queued_trial_id
        ].disposition
        is TrialDisposition.PENDING
    )
    assert (
        trials_before_recovery[
            cancelled_trial.trial_id
        ].disposition
        is TrialDisposition.CANCELLED
    )
    assert (
        trials_before_recovery[
            failed_trial_id
        ].disposition
        is TrialDisposition.FAILED
    )
    assert (
        trials_before_recovery[
            executed_trial_id
        ].disposition
        is TrialDisposition.EXECUTED
    )
    assert (
        trials_before_recovery[
            reused_trial_id
        ].disposition
        is TrialDisposition.REUSED
    )
    assert (
        trials_before_recovery[
            running_trial_id
        ].disposition
        is TrialDisposition.PENDING
    )

    assert (
        jobs_before_recovery[
            executed_trial_id
        ].completion_kind
        is ResearchJobCompletionKind.EXECUTED
    )
    assert (
        jobs_before_recovery[
            reused_trial_id
        ].completion_kind
        is ResearchJobCompletionKind.REUSED
    )
    assert (
        jobs_before_recovery[
            running_trial_id
        ].state
        is ResearchJobState.RUNNING
    )

    recovered = catalog.recover_running_research_jobs(
        terminal_at=JUN,
    )

    assert len(recovered) == 1
    assert recovered[0].job_id == running_job.job_id
    assert (
        recovered[0].state
        is ResearchJobState.INTERRUPTED
    )

    trials_after = {
        trial.trial_id: trial
        for trial in catalog.list_trials_for_revision(
            revision_id
        )
    }

    jobs_after = {
        trial_id: (
            catalog.list_research_jobs_for_trial(
                trial_id
            )[0]
        )
        for trial_id in trials_after
    }

    assert len(trials_after) == 6
    assert set(trials_after) == set(
        trials_before_recovery
    )
    assert len(jobs_after) == 6

    assert (
        jobs_after[queued_trial_id].state
        is ResearchJobState.QUEUED
    )
    assert (
        trials_after[queued_trial_id].disposition
        is TrialDisposition.PENDING
    )

    assert (
        jobs_after[
            cancelled_trial.trial_id
        ].state
        is ResearchJobState.CANCELLED
    )
    assert (
        trials_after[
            cancelled_trial.trial_id
        ].disposition
        is TrialDisposition.CANCELLED
    )

    assert (
        jobs_after[failed_trial_id].state
        is ResearchJobState.FAILED
    )
    assert (
        trials_after[failed_trial_id].disposition
        is TrialDisposition.FAILED
    )

    assert (
        jobs_after[executed_trial_id].state
        is ResearchJobState.SUCCEEDED
    )
    assert (
        jobs_after[
            executed_trial_id
        ].completion_kind
        is ResearchJobCompletionKind.EXECUTED
    )
    assert (
        trials_after[
            executed_trial_id
        ].disposition
        is TrialDisposition.EXECUTED
    )

    assert (
        jobs_after[reused_trial_id].state
        is ResearchJobState.SUCCEEDED
    )
    assert (
        jobs_after[
            reused_trial_id
        ].completion_kind
        is ResearchJobCompletionKind.REUSED
    )
    assert (
        trials_after[
            reused_trial_id
        ].disposition
        is TrialDisposition.REUSED
    )

    assert (
        jobs_after[running_trial_id].state
        is ResearchJobState.INTERRUPTED
    )
    assert (
        trials_after[
            running_trial_id
        ].disposition
        is TrialDisposition.INTERRUPTED
    )

    persisted_running_attempt = (
        catalog.load_run_attempt(
            running_attempt.attempt_id
        )
    )

    assert persisted_running_attempt is not None
    assert (
        persisted_running_attempt.state
        is RunAttemptState.INTERRUPTED
    )
    assert (
        persisted_running_attempt.failure_classification
        == "application_restart"
    )

    assert catalog.recover_running_research_jobs(
        terminal_at=JUL,
    ) == ()

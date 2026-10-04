from contextlib import closing
import json
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from core.backtest.backtest_result import BacktestResult
from core.config.app_config import AppConfig
from core.config.backtest_config import BacktestConfig
from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_retrieval import (
    IncompleteHistoricalCoverageError,
)
from core.research.backtest_research_orchestrator import (
    AuthoritativeResearchStateError,
    BacktestResearchOrchestrator,
)
from core.research.claimed_research_job_executor import (
    ClaimedResearchJobExecutor,
)
from core.research.claimed_trial_execution_inputs import (
    ClaimedTrialExecutionInputs,
)
from core.research.models.dataset import (
    PriceAdjustmentBasis,
    ProviderBindingProvenance,
)
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    ResearchJobCompletionKind,
    ResearchJobState,
    Study,
    TrialDisposition,
)
from core.research.models.research_catalog import (
    ResearchArtifactKind,
    RunAttemptState,
)
from core.research.registered_study_registration import (
    RegisteredStudyRegistrationService,
)
from core.research.registered_trial_execution_plan import (
    RegisteredTrialExecutionPlanResolver,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.research_job_queue import (
    ResearchJobQueueService,
)
from core.research.software_identity import (
    SoftwareIdentity,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)
from core.research.sqlite_research_evidence_store import (
    SQLiteResearchEvidenceStore,
)
from core.research.successor_backtest_research_coordinator import (
    SuccessorBacktestResearchCoordinator,
)
from core.research.successor_historical_retrieval import (
    SuccessorHistoricalRetrievalResult,
)
from core.research.models.universe import (
    UniverseDefinition,
    UniverseQuality,
    UniverseSnapshot,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.strategy_factory import create_strategy


INDIA = timezone(
    timedelta(hours=5, minutes=30)
)
UTC = timezone.utc

START = datetime(
    2026,
    1,
    5,
    9,
    15,
    tzinfo=INDIA,
)
END = START + timedelta(minutes=45)

REGISTERED_AT = datetime(
    2026,
    9,
    29,
    15,
    0,
    tzinfo=UTC,
)
BATCH_STARTED_AT = datetime(
    2026,
    9,
    29,
    15,
    30,
    tzinfo=UTC,
)
CLAIMED_AT = datetime(
    2026,
    9,
    29,
    16,
    0,
    tzinfo=UTC,
)
TERMINAL_AT = datetime(
    2026,
    9,
    29,
    17,
    30,
    tzinfo=UTC,
)

REVISION = (
    "de64101eb7d4ed653f5e8eaabd3ec125e7f81d32"
)
INSTRUMENT_ID = "NSE-EQ-ABC"
RISK_DECLARATION = {
    "risk_per_trade_pct": 1.0,
}


class StaticIdentityProvider:
    def resolve(self):
        return SoftwareIdentity(
            REVISION,
            True,
        )


class StaticSuccessorRetrieval:
    def __init__(
        self,
        error=None,
        on_retrieve=None,
    ):
        self.calls = []
        self.error = error
        self.on_retrieve = on_retrieve
        self.source = "provider:angelone"

    def retrieve(
        self,
        context,
        request,
        *,
        instrument_id,
        provider,
        price_adjustment_basis,
    ):
        self.calls.append(
            {
                "context": context,
                "request": request,
                "instrument_id": instrument_id,
                "provider": provider,
                "price_adjustment_basis": (
                    price_adjustment_basis
                ),
            }
        )

        if self.error is not None:
            raise self.error

        if self.on_retrieve is not None:
            self.on_retrieve()

        return SuccessorHistoricalRetrievalResult(
            candles=tuple(_candles()),
            source=self.source,
            binding_segments=(
                ProviderBindingProvenance(
                    binding_id="angelone-abc-v1",
                    provider="angelone",
                    applied_range=request,
                ),
            ),
            coverage=(request,),
            stream_usages=(),
        )


def _candles():
    values = (
        100.0,
        101.0,
        102.0,
    )

    return [
        Candle(
            timestamp=(
                START
                + timedelta(
                    minutes=15 * index
                )
            ),
            open=value,
            high=value + 1.0,
            low=value - 1.0,
            close=value,
            volume=1000.0,
        )
        for index, value in enumerate(values)
    ]


def _config():
    return BacktestConfig(
        symbol="ABC",
        timeframe="15m",
        strategy_name="sma_crossover",
        start=START,
        end=END,
        initial_capital=100000.0,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        strategy_params={
            "fast_period": 1,
            "slow_period": 2,
        },
        timezone="Asia/Kolkata",
    )


def _inputs(
    *,
    procedure_id="sma-crossover-v1",
):
    config = _config()

    return ClaimedTrialExecutionInputs(
        strategy=create_strategy(
            config
        ),
        config=config,
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=DatasetContext(
            symbol="ABC",
            timeframe="15m",
            timezone="Asia/Kolkata",
        ),
        provider="angelone",
        price_adjustment_basis=(
            PriceAdjustmentBasis.RAW
        ),
        strategy_procedure_id=procedure_id,
        risk_economic_configuration=(
            RISK_DECLARATION
        ),
        data_treatment_basis={
            "price_adjustment": "raw",
        },
    )


def _attempt_count(catalog):
    with closing(
        sqlite3.connect(
            catalog.database_path
        )
    ) as connection:
        return connection.execute(
            "SELECT COUNT(*) FROM run_attempts"
        ).fetchone()[0]


def _environment(
    tmp_path,
    *,
    execution_input_resolver,
    evidence_reuse_policy=(
        EvidenceReusePolicy.FORCE_NEW_EXECUTION
    ),
    execution_error=None,
    retrieval_error=None,
    retrieval_hook=None,
    members=(INSTRUMENT_ID,),
    claim_job=True,
):
    database = (
        tmp_path / "research.sqlite3"
    )

    attempt_ids = iter(
        (
            "attempt-claimed-job-001",
            "attempt-claimed-job-002",
            "attempt-claimed-job-003",
        )
    )

    catalog = SQLiteResearchCatalogStore(
        database,
        attempt_id_factory=(
            lambda: next(attempt_ids)
        ),
    )

    artifact_store = (
        ContentAddressedResearchArtifactStore(
            tmp_path / "artifacts"
        )
    )

    evidence_store = (
        SQLiteResearchEvidenceStore(
            database
        )
    )

    catalog.save_study(
        Study(
            study_id="study-claimed-job",
            created_at=REGISTERED_AT,
            display_title=(
                "M9.4d claimed job execution"
            ),
        )
    )

    definition = UniverseDefinition(
        name="claimed-job-universe",
        selection_spec="fixture",
    )

    snapshot = UniverseSnapshot(
        definition=definition,
        members=tuple(members),
        quality=UniverseQuality.PIT_VERIFIED,
        as_of=START,
        provenance_refs=(
            "claimed-job-source",
        ),
        effective_from=START,
        effective_to=END,
    )

    registration = (
        RegisteredStudyRegistrationService(
            catalog_store=catalog,
            artifact_store=artifact_store,
        )
    )

    population = (
        registration.register_study_revision(
            study_id="study-claimed-job",
            research_intent=(
                "exercise claimed ResearchJob"
            ),
            strategy_procedure_id=(
                "sma-crossover-v1"
            ),
            timeframe="15m",
            research_range=TimeRange(
                START,
                END,
            ),
            timezone="Asia/Kolkata",
            initial_capital=100000.0,
            risk_economic_configuration=(
                RISK_DECLARATION
            ),
            parameter_variants=(
                {
                    "fast_period": 1,
                    "slow_period": 2,
                },
            ),
            universe_definition=definition,
            universe_snapshots=(
                snapshot,
            ),
            require_point_in_time=True,
            data_treatment_basis={
                "price_adjustment": "raw",
            },
            repository_revision=REVISION,
            evidence_reuse_policy=(
                evidence_reuse_policy
            ),
            registered_at=REGISTERED_AT,
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
        started_at=BATCH_STARTED_AT,
    )

    claimed = None

    if claim_job:
        claimed = (
            catalog.claim_next_research_job(
                revision_id,
                "worker-claimed-job",
                CLAIMED_AT,
                max_running_jobs=1,
            )
        )

        assert claimed is not None

    def legacy_retrieval_must_not_run(
        **kwargs,
    ):
        raise AssertionError(
            "legacy retrieval must not run "
            "for claimed successor execution"
        )

    execution_calls = []

    def execute_candles(**kwargs):
        execution_calls.append(
            kwargs["candles"]
        )

        if execution_error is not None:
            raise execution_error

        return BacktestResult(
            trades=[],
            bar_records=[],
            session_id=(
                "runtime-claimed-job"
            ),
        )

    evidence_ids = iter(
        (
            "evidence-claimed-job-001",
            "evidence-claimed-job-002",
            "evidence-claimed-job-003",
        )
    )

    orchestrator = (
        BacktestResearchOrchestrator(
            catalog_store=catalog,
            evidence_store=evidence_store,
            artifact_store=artifact_store,
            software_identity_provider=(
                StaticIdentityProvider()
            ),
            evidence_id_factory=(
                lambda: next(evidence_ids)
            ),
            clock=lambda: TERMINAL_AT,
            retrieve_candles=(
                legacy_retrieval_must_not_run
            ),
            execute_candles=execute_candles,
        )
    )

    retrieval = StaticSuccessorRetrieval(
        error=retrieval_error,
        on_retrieve=retrieval_hook,
    )

    coordinator = (
        SuccessorBacktestResearchCoordinator(
            retrieval_service=retrieval,
            orchestrator=orchestrator,
            clock=lambda: TERMINAL_AT,
        )
    )

    plan_resolver = (
        RegisteredTrialExecutionPlanResolver(
            catalog_store=catalog,
            artifact_store=artifact_store,
        )
    )

    executor = ClaimedResearchJobExecutor(
        catalog_store=catalog,
        plan_resolver=plan_resolver,
        execution_input_resolver=(
            execution_input_resolver
        ),
        successor_coordinator=coordinator,
        clock=lambda: TERMINAL_AT,
    )

    return (
        catalog,
        population.trials[0],
        claimed,
        executor,
        retrieval,
        execution_calls,
    )


def test_claimed_job_executes_fresh_attempt_through_authoritative_path(
    tmp_path,
):
    (
        catalog,
        trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
    )

    terminal_job = executor.execute(
        claimed
    )

    assert (
        terminal_job.state
        is ResearchJobState.SUCCEEDED
    )
    assert (
        terminal_job.completion_kind
        is ResearchJobCompletionKind.EXECUTED
    )
    assert (
        terminal_job.attempt_id
        == "attempt-claimed-job-001"
    )
    assert terminal_job.reused_attempt_id is None

    assert _attempt_count(catalog) == 1

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )
    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.EXECUTED
    )

    attempt = catalog.load_run_attempt(
        "attempt-claimed-job-001"
    )
    assert attempt is not None
    assert (
        attempt.state
        is RunAttemptState.SUCCEEDED
    )
    assert attempt.evidence_id is not None
    assert attempt.result_artifact_id is not None

    assert len(retrieval.calls) == 1
    assert (
        retrieval.calls[0]["instrument_id"]
        == INSTRUMENT_ID
    )
    assert (
        retrieval.calls[0]["provider"]
        == "angelone"
    )

    assert len(execution_calls) == 1
    assert execution_calls[0] == _candles()


def test_claimed_job_input_mismatch_fails_before_attempt_or_retrieval(
    tmp_path,
):
    (
        catalog,
        trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs(
                procedure_id="wrong-procedure-v1"
            )
        ),
    )

    terminal_job = executor.execute(
        claimed
    )

    assert (
        terminal_job.state
        is ResearchJobState.FAILED
    )
    assert terminal_job.attempt_id is None
    assert (
        terminal_job.failure_classification
        == "execution_input_resolution_failed"
    )

    assert _attempt_count(catalog) == 0
    assert retrieval.calls == []
    assert execution_calls == []

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )
    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.FAILED
    )
    assert (
        persisted_trial.failure_classification
        == "execution_input_resolution_failed"
    )



def test_claimed_job_reuses_exact_accepted_execution_without_new_attempt(
    tmp_path,
):
    (
        catalog,
        trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    inputs = _inputs()

    prior = (
        executor
        .successor_coordinator
        .execute(
            strategy=inputs.strategy,
            config=inputs.config,
            runtime_context=(
                inputs.runtime_context
            ),
            dataset_context=(
                inputs.dataset_context
            ),
            instrument_id=INSTRUMENT_ID,
            provider=inputs.provider,
            price_adjustment_basis=(
                inputs.price_adjustment_basis
            ),
        )
    )

    assert (
        prior.attempt_id
        == "attempt-claimed-job-001"
    )
    assert _attempt_count(catalog) == 1
    assert len(execution_calls) == 1

    terminal_job = executor.execute(
        claimed
    )

    assert (
        terminal_job.state
        is ResearchJobState.SUCCEEDED
    )
    assert (
        terminal_job.completion_kind
        is ResearchJobCompletionKind.REUSED
    )
    assert terminal_job.attempt_id is None
    assert (
        terminal_job.reused_attempt_id
        == prior.attempt_id
    )
    assert (
        terminal_job.reused_evidence_id
        == prior.evidence_id
    )
    prior_attempt = catalog.load_run_attempt(
        prior.attempt_id
    )
    assert prior_attempt is not None
    assert prior_attempt.result_artifact_id is not None

    assert (
        terminal_job.reused_result_artifact_id
        == prior_attempt.result_artifact_id
    )

    assert _attempt_count(catalog) == 1
    assert len(execution_calls) == 1

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )
    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.REUSED
    )
    assert (
        persisted_trial.reused_attempt_id
        == prior.attempt_id
    )

    # One canonical retrieval/preparation occurred for the historical
    # execution and one for the newly claimed Trial before reuse was
    # proven. No second financial computation occurred.
    assert len(retrieval.calls) == 2



def test_claimed_job_financial_failure_is_durably_isolated(
    tmp_path,
):
    (
        catalog,
        trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
        execution_error=RuntimeError(
            "fixture financial computation failed"
        ),
    )

    terminal_job = executor.execute(
        claimed
    )

    assert (
        terminal_job.state
        is ResearchJobState.FAILED
    )
    assert (
        terminal_job.attempt_id
        == "attempt-claimed-job-001"
    )
    assert (
        terminal_job.failure_classification
        == "backtest_execution_failed"
    )
    assert (
        terminal_job.failure_message
        == "fixture financial computation failed"
    )
    assert terminal_job.completion_kind is None

    assert _attempt_count(catalog) == 1
    assert len(retrieval.calls) == 1
    assert len(execution_calls) == 1

    attempt = catalog.load_run_attempt(
        "attempt-claimed-job-001"
    )
    assert attempt is not None
    assert (
        attempt.state
        is RunAttemptState.FAILED
    )
    assert (
        attempt.failure_classification
        == "backtest_execution_failed"
    )
    assert (
        attempt.failure_message
        == "fixture financial computation failed"
    )
    assert attempt.evidence_id is not None
    assert attempt.result_artifact_id is None

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )
    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.FAILED
    )
    assert (
        persisted_trial.failure_classification
        == "backtest_execution_failed"
    )
    assert (
        persisted_trial.failure_message
        == "fixture financial computation failed"
    )



def test_failed_trial_retry_can_be_claimed_and_execute_successfully(
    tmp_path,
):
    (
        catalog,
        trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
        execution_error=RuntimeError(
            "first physical execution fails"
        ),
    )

    failed_job = executor.execute(
        claimed
    )

    assert (
        failed_job.state
        is ResearchJobState.FAILED
    )
    assert (
        failed_job.attempt_id
        == "attempt-claimed-job-001"
    )

    failed_trial = catalog.load_trial(
        trial.trial_id
    )
    assert failed_trial is not None
    assert (
        failed_trial.disposition
        is TrialDisposition.FAILED
    )
    assert failed_trial.experiment_spec_id is not None

    bound_spec_id = (
        failed_trial.experiment_spec_id
    )

    _, retry_job, retry_event = (
        catalog.retry_trial(
            trial.trial_id,
            retry_requested_at=TERMINAL_AT,
        )
    )

    assert (
        retry_job.state
        is ResearchJobState.QUEUED
    )
    assert retry_job.attempt_id is None
    assert (
        retry_event.previous_disposition
        is TrialDisposition.FAILED
    )
    assert (
        retry_event.new_disposition
        is TrialDisposition.PENDING
    )

    pending_trial = catalog.load_trial(
        trial.trial_id
    )
    assert pending_trial is not None
    assert (
        pending_trial.experiment_spec_id
        == bound_spec_id
    )

    retry_claimed = (
        catalog.claim_next_research_job(
            pending_trial.study_revision_id,
            "worker-claimed-job-retry",
            TERMINAL_AT,
            max_running_jobs=1,
        )
    )

    assert retry_claimed is not None
    assert retry_claimed.job_id == retry_job.job_id

    def successful_execute(**kwargs):
        execution_calls.append(
            kwargs["candles"]
        )
        return BacktestResult(
            trades=[],
            bar_records=[],
            session_id=(
                "runtime-claimed-job-retry"
            ),
        )

    executor.successor_coordinator.orchestrator._execute_candles = (
        successful_execute
    )

    terminal_retry_job = executor.execute(
        retry_claimed
    )

    assert (
        terminal_retry_job.state
        is ResearchJobState.SUCCEEDED
    )
    assert (
        terminal_retry_job.completion_kind
        is ResearchJobCompletionKind.EXECUTED
    )
    assert (
        terminal_retry_job.attempt_id
        == "attempt-claimed-job-002"
    )

    succeeded_trial = catalog.load_trial(
        trial.trial_id
    )
    assert succeeded_trial is not None
    assert (
        succeeded_trial.trial_id
        == trial.trial_id
    )
    assert (
        succeeded_trial.disposition
        is TrialDisposition.EXECUTED
    )
    assert (
        succeeded_trial.experiment_spec_id
        == bound_spec_id
    )

    jobs = (
        catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
    )
    assert len(jobs) == 2

    first_attempt = catalog.load_run_attempt(
        "attempt-claimed-job-001"
    )
    retry_attempt = catalog.load_run_attempt(
        "attempt-claimed-job-002"
    )

    assert first_attempt is not None
    assert retry_attempt is not None

    assert (
        first_attempt.experiment_spec_id
        == bound_spec_id
    )
    assert (
        retry_attempt.experiment_spec_id
        == bound_spec_id
    )

    assert (
        first_attempt.state
        is RunAttemptState.FAILED
    )
    assert (
        retry_attempt.state
        is RunAttemptState.SUCCEEDED
    )

    events = (
        catalog.load_trial_disposition_events(
            trial.trial_id
        )
    )

    assert [
        (
            value.previous_disposition,
            value.new_disposition,
        )
        for value in events
    ] == [
        (
            None,
            TrialDisposition.PENDING,
        ),
        (
            TrialDisposition.PENDING,
            TrialDisposition.FAILED,
        ),
        (
            TrialDisposition.FAILED,
            TrialDisposition.PENDING,
        ),
        (
            TrialDisposition.PENDING,
            TrialDisposition.EXECUTED,
        ),
    ]

    assert len(retrieval.calls) == 2
    assert len(execution_calls) == 2



def test_provider_retrieval_failure_is_classified_before_attempt(
    tmp_path,
):
    (
        catalog,
        trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
        retrieval_error=RuntimeError(
            "provider unavailable"
        ),
    )

    terminal_job = executor.execute(
        claimed
    )

    assert (
        terminal_job.state
        is ResearchJobState.FAILED
    )
    assert terminal_job.attempt_id is None
    assert (
        terminal_job.failure_classification
        == "historical_data_retrieval_failed"
    )
    assert (
        terminal_job.failure_message
        == "provider unavailable"
    )

    terminal_trial = catalog.load_trial(
        trial.trial_id
    )
    assert terminal_trial is not None
    assert (
        terminal_trial.disposition
        is TrialDisposition.FAILED
    )
    assert _attempt_count(catalog) == 0
    assert len(retrieval.calls) == 1
    assert execution_calls == []


def test_dataset_reference_persistence_failure_propagates_fail_closed(
    tmp_path,
):
    (
        catalog,
        trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
    )

    def fail_dataset_reference_persistence(
        *args,
        **kwargs,
    ):
        raise RuntimeError(
            "dataset reference persistence failed"
        )

    (
        executor.successor_coordinator
        .orchestrator.artifact_store
        .persist_dataset_reference
    ) = fail_dataset_reference_persistence

    with pytest.raises(
        AuthoritativeResearchStateError,
        match="dataset reference persistence failed",
    ):
        executor.execute(
            claimed
        )

    persisted_job = catalog.load_research_job(
        claimed.job_id
    )
    assert persisted_job is not None
    assert (
        persisted_job.state
        is ResearchJobState.RUNNING
    )
    assert persisted_job.attempt_id is None
    assert persisted_job.failure_classification is None
    assert persisted_job.failure_message is None

    terminal_trial = catalog.load_trial(
        trial.trial_id
    )
    assert terminal_trial is not None
    assert (
        terminal_trial.disposition
        is TrialDisposition.PENDING
    )

    assert _attempt_count(catalog) == 0
    assert len(retrieval.calls) == 1
    assert execution_calls == []



def test_incomplete_history_becomes_nonretryable_insufficient_trial(
    tmp_path,
):
    (
        catalog,
        trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
        retrieval_error=(
            IncompleteHistoricalCoverageError(
                [
                    TimeRange(
                        START,
                        END,
                    )
                ]
            )
        ),
    )

    terminal_job = executor.execute(
        claimed
    )

    assert (
        terminal_job.state
        is ResearchJobState.FAILED
    )
    assert terminal_job.attempt_id is None
    assert (
        terminal_job.failure_classification
        == "insufficient_history"
    )

    terminal_trial = catalog.load_trial(
        trial.trial_id
    )
    assert terminal_trial is not None
    assert (
        terminal_trial.disposition
        is TrialDisposition.INSUFFICIENT
    )
    assert (
        terminal_trial.failure_classification
        == "insufficient_history"
    )

    assert _attempt_count(catalog) == 0
    assert len(retrieval.calls) == 1
    assert execution_calls == []

    events = (
        catalog.load_trial_disposition_events(
            trial.trial_id
        )
    )
    assert (
        events[-1].previous_disposition
        is TrialDisposition.PENDING
    )
    assert (
        events[-1].new_disposition
        is TrialDisposition.INSUFFICIENT
    )
    assert (
        events[-1].reason_classification
        == "insufficient_history"
    )

    with pytest.raises(
        ValueError,
        match="not eligible for ordinary retry",
    ):
        catalog.retry_trial(
            trial.trial_id,
            retry_requested_at=TERMINAL_AT,
        )



def test_m94e_cancellation_before_retrieval_stops_without_attempt_or_execution(
    tmp_path,
):
    (
        catalog,
        trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=lambda plan: _inputs(),
    )

    catalog.request_running_research_job_cancellation(
        job_id=claimed.job_id,
        requested_at=TERMINAL_AT,
    )

    terminal_job = executor.execute(
        claimed
    )

    assert (
        terminal_job.state
        is ResearchJobState.CANCELLED
    )
    assert terminal_job.attempt_id is None
    assert (
        terminal_job.cancel_requested_at
        == TERMINAL_AT
    )
    assert retrieval.calls == []
    assert execution_calls == []
    assert _attempt_count(catalog) == 0

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.CANCELLED
    )


def test_m94e_cancellation_after_retrieval_stops_before_attempt_and_execution(
    tmp_path,
):
    holder = {}

    def request_cancellation():
        holder["catalog"].request_running_research_job_cancellation(
            job_id=holder["claimed"].job_id,
            requested_at=TERMINAL_AT,
        )

    (
        catalog,
        trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=lambda plan: _inputs(),
        retrieval_hook=request_cancellation,
    )

    holder["catalog"] = catalog
    holder["claimed"] = claimed

    terminal_job = executor.execute(
        claimed
    )

    assert len(retrieval.calls) == 1
    assert (
        terminal_job.state
        is ResearchJobState.CANCELLED
    )
    assert terminal_job.attempt_id is None
    assert execution_calls == []
    assert _attempt_count(catalog) == 0

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.CANCELLED
    )


def test_m94e_cancellation_after_reuse_resolution_stops_before_new_attempt(
    tmp_path,
):
    (
        catalog,
        trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=lambda plan: _inputs(),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    orchestrator = (
        executor.successor_coordinator.orchestrator
    )

    original_find = (
        orchestrator.find_exact_reusable_execution
    )

    calls = []

    def find_and_cancel(experiment_spec_id):
        calls.append(experiment_spec_id)

        reusable = original_find(
            experiment_spec_id
        )

        assert reusable is None

        catalog.request_running_research_job_cancellation(
            job_id=claimed.job_id,
            requested_at=TERMINAL_AT,
        )

        return None

    orchestrator.find_exact_reusable_execution = (
        find_and_cancel
    )

    terminal_job = executor.execute(
        claimed
    )

    assert len(retrieval.calls) == 1
    assert len(calls) == 1
    assert (
        terminal_job.state
        is ResearchJobState.CANCELLED
    )
    assert terminal_job.attempt_id is None
    assert execution_calls == []
    assert _attempt_count(catalog) == 0

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.CANCELLED
    )



def test_m94e_cancellation_wins_fresh_attempt_bind_race(
    tmp_path,
    monkeypatch,
):
    (
        catalog,
        trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
    )

    original_bind = (
        catalog
        .bind_trial_spec_create_attempt_for_running_job
    )

    injected = False

    def cancel_then_bind(*args, **kwargs):
        nonlocal injected

        if not injected:
            injected = True

            catalog.request_running_research_job_cancellation(
                job_id=claimed.job_id,
                requested_at=TERMINAL_AT,
            )

        return original_bind(
            *args,
            **kwargs,
        )

    monkeypatch.setattr(
        catalog,
        "bind_trial_spec_create_attempt_for_running_job",
        cancel_then_bind,
    )

    terminal_job = executor.execute(
        claimed
    )

    assert injected is True
    assert (
        terminal_job.state
        is ResearchJobState.CANCELLED
    )
    assert terminal_job.cancel_requested_at == TERMINAL_AT
    assert terminal_job.attempt_id is None
    assert terminal_job.completion_kind is None
    assert terminal_job.reused_attempt_id is None

    assert _attempt_count(catalog) == 0
    assert len(retrieval.calls) == 1
    assert execution_calls == []

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.CANCELLED
    )



def test_m94e_cancellation_wins_exact_reuse_terminalization_race(
    tmp_path,
    monkeypatch,
):
    (
        catalog,
        trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    inputs = _inputs()

    prior = (
        executor
        .successor_coordinator
        .execute(
            strategy=inputs.strategy,
            config=inputs.config,
            runtime_context=(
                inputs.runtime_context
            ),
            dataset_context=(
                inputs.dataset_context
            ),
            instrument_id=INSTRUMENT_ID,
            provider=inputs.provider,
            price_adjustment_basis=(
                inputs.price_adjustment_basis
            ),
        )
    )

    assert _attempt_count(catalog) == 1
    assert len(execution_calls) == 1

    original_complete = (
        catalog
        .complete_running_job_with_exact_reuse
    )

    injected = False

    def cancel_then_complete(*args, **kwargs):
        nonlocal injected

        if not injected:
            injected = True

            catalog.request_running_research_job_cancellation(
                job_id=claimed.job_id,
                requested_at=TERMINAL_AT,
            )

        return original_complete(
            *args,
            **kwargs,
        )

    monkeypatch.setattr(
        catalog,
        "complete_running_job_with_exact_reuse",
        cancel_then_complete,
    )

    terminal_job = executor.execute(
        claimed
    )

    assert injected is True
    assert (
        terminal_job.state
        is ResearchJobState.CANCELLED
    )
    assert terminal_job.cancel_requested_at == TERMINAL_AT
    assert terminal_job.attempt_id is None
    assert terminal_job.completion_kind is None
    assert terminal_job.reused_attempt_id is None
    assert terminal_job.reused_evidence_id is None
    assert terminal_job.reused_result_artifact_id is None

    assert _attempt_count(catalog) == 1
    assert len(execution_calls) == 1
    assert len(retrieval.calls) == 2

    prior_attempt = catalog.load_run_attempt(
        prior.attempt_id
    )

    assert prior_attempt is not None
    assert (
        prior_attempt.state
        is RunAttemptState.SUCCEEDED
    )

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.CANCELLED
    )


def _m94g1_source_dataset_reference(
    catalog,
    executor,
    prior,
):
    source_attempt = catalog.load_run_attempt(
        prior.attempt_id
    )
    assert source_attempt is not None
    assert source_attempt.evidence_id is not None

    evidence = (
        executor
        .successor_coordinator
        .orchestrator
        .evidence_store
        .load(source_attempt.evidence_id)
    )

    assert evidence is not None

    matches = []

    for reference in evidence.artifact_references:
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
            matches.append(
                (reference, artifact)
            )

    assert len(matches) == 1

    return (
        source_attempt,
        evidence,
        matches[0][0],
        matches[0][1],
    )


def test_m94g1_reuse_allows_different_acquisition_provenance(
    tmp_path,
):
    (
        catalog,
        _,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    inputs = _inputs()

    prior = (
        executor
        .successor_coordinator
        .execute(
            strategy=inputs.strategy,
            config=inputs.config,
            runtime_context=inputs.runtime_context,
            dataset_context=inputs.dataset_context,
            instrument_id=INSTRUMENT_ID,
            provider=inputs.provider,
            price_adjustment_basis=(
                inputs.price_adjustment_basis
            ),
        )
    )

    (
        _,
        _,
        source_reference,
        source_artifact,
    ) = _m94g1_source_dataset_reference(
        catalog,
        executor,
        prior,
    )

    retrieval.source = "provider:alternate-trusted"

    terminal_job = executor.execute(
        claimed
    )

    assert (
        terminal_job.completion_kind
        is ResearchJobCompletionKind.REUSED
    )
    assert (
        terminal_job.reused_attempt_id
        == prior.attempt_id
    )
    assert _attempt_count(catalog) == 1
    assert len(execution_calls) == 1
    assert source_reference.startswith(
        "artifact:sha256:"
    )
    assert (
        source_artifact.artifact_kind
        is ResearchArtifactKind.DATASET_REFERENCE
    )

    dataset_lineage = (
        catalog
        .load_research_job_reuse_dataset_lineage(
            terminal_job.job_id
        )
    )

    assert dataset_lineage is not None

    (
        requested_dataset_reference_artifact_id,
        source_dataset_reference_artifact_id,
    ) = dataset_lineage

    assert (
        source_dataset_reference_artifact_id
        == source_artifact.artifact_id
    )

    # Different acquisition provenance may produce a different
    # DatasetReference artifact while retaining the same canonical
    # DatasetIdentityV2.dataset_id.
    assert (
        requested_dataset_reference_artifact_id
        != source_dataset_reference_artifact_id
    )

    requested_artifact = catalog.load_artifact(
        requested_dataset_reference_artifact_id
    )

    assert requested_artifact is not None
    assert (
        requested_artifact.artifact_kind
        is ResearchArtifactKind.DATASET_REFERENCE
    )
    assert len(retrieval.calls) == 2


def test_m94g1_reuse_rejects_incompatible_successor_instrument(
    tmp_path,
):
    (
        catalog,
        _,
        claimed,
        executor,
        _,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    inputs = _inputs()

    prior = (
        executor
        .successor_coordinator
        .execute(
            strategy=inputs.strategy,
            config=inputs.config,
            runtime_context=inputs.runtime_context,
            dataset_context=inputs.dataset_context,
            instrument_id="NSE-EQ-DIFFERENT",
            provider=inputs.provider,
            price_adjustment_basis=(
                inputs.price_adjustment_basis
            ),
        )
    )

    terminal_job = executor.execute(
        claimed
    )

    assert (
        terminal_job.completion_kind
        is ResearchJobCompletionKind.EXECUTED
    )
    assert terminal_job.reused_attempt_id is None
    assert terminal_job.attempt_id != prior.attempt_id
    assert _attempt_count(catalog) == 2
    assert len(execution_calls) == 2
    assert (
        catalog.load_research_job_reuse_dataset_lineage(
            terminal_job.job_id
        )
        is None
    )


def test_m94g1_reuse_rejects_incompatible_price_adjustment_basis(
    tmp_path,
):
    (
        catalog,
        _,
        claimed,
        executor,
        _,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    inputs = _inputs()

    prior = (
        executor
        .successor_coordinator
        .execute(
            strategy=inputs.strategy,
            config=inputs.config,
            runtime_context=inputs.runtime_context,
            dataset_context=inputs.dataset_context,
            instrument_id=INSTRUMENT_ID,
            provider=inputs.provider,
            price_adjustment_basis=(
                PriceAdjustmentBasis.ADJUSTED
            ),
        )
    )

    terminal_job = executor.execute(
        claimed
    )

    assert (
        terminal_job.completion_kind
        is ResearchJobCompletionKind.EXECUTED
    )
    assert terminal_job.reused_attempt_id is None
    assert terminal_job.attempt_id != prior.attempt_id
    assert _attempt_count(catalog) == 2
    assert len(execution_calls) == 2


def test_m94g1_reuse_rejects_missing_source_dataset_lineage(
    tmp_path,
):
    (
        catalog,
        _,
        claimed,
        executor,
        _,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    inputs = _inputs()

    prior = (
        executor
        .successor_coordinator
        .execute(
            strategy=inputs.strategy,
            config=inputs.config,
            runtime_context=inputs.runtime_context,
            dataset_context=inputs.dataset_context,
            instrument_id=INSTRUMENT_ID,
            provider=inputs.provider,
            price_adjustment_basis=(
                inputs.price_adjustment_basis
            ),
        )
    )

    (
        source_attempt,
        evidence,
        dataset_reference,
        _,
    ) = _m94g1_source_dataset_reference(
        catalog,
        executor,
        prior,
    )

    remaining_references = tuple(
        reference
        for reference in evidence.artifact_references
        if reference != dataset_reference
    )

    with closing(
        sqlite3.connect(
            catalog.database_path
        )
    ) as connection:
        connection.execute(
            """
            UPDATE research_evidence
            SET artifact_references = ?
            WHERE evidence_id = ?
            """,
            (
                json.dumps(
                    list(remaining_references),
                    separators=(",", ":"),
                ),
                source_attempt.evidence_id,
            ),
        )
        connection.commit()

    terminal_job = executor.execute(
        claimed
    )

    assert (
        terminal_job.completion_kind
        is ResearchJobCompletionKind.EXECUTED
    )
    assert terminal_job.reused_attempt_id is None
    assert terminal_job.attempt_id != prior.attempt_id
    assert _attempt_count(catalog) == 2
    assert len(execution_calls) == 2


def test_m94g1_reuse_rejects_corrupt_source_dataset_lineage(
    tmp_path,
):
    (
        catalog,
        _,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    inputs = _inputs()

    prior = (
        executor
        .successor_coordinator
        .execute(
            strategy=inputs.strategy,
            config=inputs.config,
            runtime_context=inputs.runtime_context,
            dataset_context=inputs.dataset_context,
            instrument_id=INSTRUMENT_ID,
            provider=inputs.provider,
            price_adjustment_basis=(
                inputs.price_adjustment_basis
            ),
        )
    )

    (
        _,
        _,
        _,
        source_artifact,
    ) = _m94g1_source_dataset_reference(
        catalog,
        executor,
        prior,
    )

    artifact_store = (
        executor
        .successor_coordinator
        .orchestrator
        .artifact_store
    )

    source_path = (
        artifact_store
        .root_directory
        .joinpath(
            *source_artifact
            .relative_path
            .split("/")
        )
    )

    retrieval.source = (
        "provider:alternate-trusted"
    )

    source_path.write_bytes(
        b"corrupt-dataset-reference"
    )

    terminal_job = executor.execute(
        claimed
    )

    assert (
        terminal_job.completion_kind
        is ResearchJobCompletionKind.EXECUTED
    )
    assert terminal_job.reused_attempt_id is None
    assert terminal_job.attempt_id != prior.attempt_id
    assert _attempt_count(catalog) == 2
    assert len(execution_calls) == 2


def test_m94g2_worker_pool_stops_after_authoritative_artifact_persistence_failure(
    tmp_path,
):
    (
        catalog,
        first_trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
        members=(
            INSTRUMENT_ID,
            "NSE-EQ-XYZ",
        ),
        claim_job=False,
    )

    assert claimed is None

    revision_id = first_trial.study_revision_id

    queue = ResearchJobQueueService(
        catalog_store=catalog,
        app_config=AppConfig(
            research_max_workers=1
        ),
    )

    original_persist = (
        executor.successor_coordinator
        .orchestrator.artifact_store
        .persist_dataset_reference
    )
    persist_calls = 0

    def fail_first_dataset_reference(
        *args,
        **kwargs,
    ):
        nonlocal persist_calls
        persist_calls += 1

        if persist_calls == 1:
            raise OSError(
                "authoritative dataset reference persistence failed"
            )

        return original_persist(
            *args,
            **kwargs,
        )

    (
        executor.successor_coordinator
        .orchestrator.artifact_store
        .persist_dataset_reference
    ) = fail_first_dataset_reference

    with pytest.raises(
        AuthoritativeResearchStateError,
        match=(
            "authoritative dataset reference "
            "persistence failed"
        ),
    ):
        queue.run_worker_pool(
            revision_id,
            worker_id_factory=(
                lambda slot: f"worker-g2-{slot}"
            ),
            claimed_at_factory=lambda: CLAIMED_AT,
            execute_claimed_job=executor.execute,
        )

    snapshot = queue.snapshot(
        revision_id
    )

    assert snapshot.total_registered_trials == 2
    assert snapshot.running_jobs == 1
    assert snapshot.queued_jobs == 1
    assert snapshot.failed_jobs == 0
    assert persist_calls == 1
    assert len(retrieval.calls) == 1
    assert _attempt_count(catalog) == 0
    assert execution_calls == []


def test_m94g2_worker_pool_continues_after_ordinary_trial_failure(
    tmp_path,
):
    (
        catalog,
        first_trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
        retrieval_error=RuntimeError(
            "provider unavailable"
        ),
        members=(
            INSTRUMENT_ID,
            "NSE-EQ-XYZ",
        ),
        claim_job=False,
    )

    assert claimed is None

    revision_id = first_trial.study_revision_id

    queue = ResearchJobQueueService(
        catalog_store=catalog,
        app_config=AppConfig(
            research_max_workers=1
        ),
    )

    snapshot = queue.run_worker_pool(
        revision_id,
        worker_id_factory=(
            lambda slot: f"worker-g2-{slot}"
        ),
        claimed_at_factory=lambda: CLAIMED_AT,
        execute_claimed_job=executor.execute,
    )

    assert snapshot.total_registered_trials == 2
    assert snapshot.running_jobs == 0
    assert snapshot.queued_jobs == 0
    assert snapshot.failed_jobs == 2
    assert len(retrieval.calls) == 2
    assert _attempt_count(catalog) == 0
    assert execution_calls == []


def test_m94g2_manifest_persistence_failure_propagates_without_false_evidence(
    tmp_path,
):
    (
        catalog,
        trial,
        claimed,
        executor,
        retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda plan: _inputs()
        ),
    )

    def fail_manifest_persistence(
        *args,
        **kwargs,
    ):
        raise OSError(
            "authoritative manifest persistence failed"
        )

    (
        executor.successor_coordinator
        .orchestrator.artifact_store
        .persist_backtest_manifest
    ) = fail_manifest_persistence

    with pytest.raises(
        AuthoritativeResearchStateError,
        match="authoritative manifest persistence failed",
    ):
        executor.execute(
            claimed
        )

    persisted_job = catalog.load_research_job(
        claimed.job_id
    )

    assert persisted_job is not None
    assert (
        persisted_job.state
        is ResearchJobState.RUNNING
    )
    assert persisted_job.attempt_id is None
    assert persisted_job.failure_classification is None
    assert persisted_job.failure_message is None

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.PENDING
    )

    with closing(
        sqlite3.connect(
            catalog.database_path
        )
    ) as connection:
        evidence_count = connection.execute(
            "SELECT COUNT(*) FROM research_evidence"
        ).fetchone()[0]

    assert evidence_count == 0
    assert _attempt_count(catalog) == 0
    assert len(retrieval.calls) == 1
    assert execution_calls == []

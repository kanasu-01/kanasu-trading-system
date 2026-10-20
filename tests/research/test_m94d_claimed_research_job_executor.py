from contextlib import closing
import json
from datetime import datetime, timedelta, timezone
import sqlite3
from types import MethodType

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
from core.runtime.backtest_runtime import (
    DeterministicBacktestComputationError,
    TransientBacktestOperationalError,
    execute_backtest_candles,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.research.backtest_financial_configuration import (
    default_backtest_financial_configuration,
)
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
RISK_DECLARATION = default_backtest_financial_configuration()


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
    price_basis=PriceAdjustmentBasis.RAW,
    data_treatment=None,
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
            price_basis
        ),
        strategy_procedure_id=procedure_id,
        risk_economic_configuration=(
            RISK_DECLARATION
        ),
        data_treatment_basis=(
            data_treatment
            if data_treatment is not None
            else {
                "price_adjustment": "raw",
            }
        ),
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
    registered_data_treatment=None,
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
            data_treatment_basis=(
                registered_data_treatment
                if registered_data_treatment is not None
                else {
                    "price_adjustment": "raw",
                }
            ),
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


def test_m94k_explicit_unknown_price_adjustment_survives_registered_execution(
    tmp_path,
):
    inputs = _inputs(
        price_basis=(
            PriceAdjustmentBasis.UNKNOWN
        ),
        data_treatment={
            "price_adjustment": "unknown",
        },
    )

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
            lambda plan: inputs
        ),
        registered_data_treatment={
            "price_adjustment": "unknown",
        },
    )

    terminal_job = executor.execute(
        claimed
    )

    assert (
        terminal_job.state
        is ResearchJobState.SUCCEEDED
    )

    assert _attempt_count(catalog) == 1
    assert len(retrieval.calls) == 1

    assert (
        retrieval.calls[0][
            "price_adjustment_basis"
        ]
        is PriceAdjustmentBasis.UNKNOWN
    )

    assert len(execution_calls) == 1


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
        == "invalid_input"
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
        is TrialDisposition.INVALID
    )
    assert (
        persisted_trial.failure_classification
        == "invalid_input"
    )



def test_m94h1_retrieval_mutation_cannot_change_registered_capital(
    tmp_path,
):
    resolved_inputs = _inputs()
    registered_capital = (
        resolved_inputs.config.initial_capital
    )
    mutated_capital = registered_capital * 2

    def mutate_resolver_owned_inputs(*args, **kwargs):
        resolved_inputs.config.initial_capital = (
            mutated_capital
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
        execution_input_resolver=(
            lambda plan: resolved_inputs
        ),
        retrieval_hook=(
            mutate_resolver_owned_inputs
        ),
    )

    orchestrator = (
        executor.successor_coordinator.orchestrator
    )
    original_execute = orchestrator._execute_candles
    executed_capitals = []

    def capture_execute(**kwargs):
        executed_capitals.append(
            kwargs["config"].initial_capital
        )
        return original_execute(**kwargs)

    orchestrator._execute_candles = capture_execute

    terminal_job = executor.execute(
        claimed
    )

    assert (
        resolved_inputs.config.initial_capital
        == mutated_capital
    )
    assert (
        terminal_job.state
        is ResearchJobState.SUCCEEDED
    )
    assert executed_capitals == [
        registered_capital
    ]


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
        execution_error=(
            DeterministicBacktestComputationError(
                RuntimeError(
                    "fixture financial computation failed"
                )
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
    assert (
        terminal_job.attempt_id
        == "attempt-claimed-job-001"
    )
    assert (
        terminal_job.failure_classification
        == "deterministic_compute_failure"
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
        == "deterministic_compute_failure"
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
        == "deterministic_compute_failure"
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
        == "unknown_failure"
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


def test_m94h2_authoritative_input_resolution_failure_propagates_fail_closed(
    tmp_path,
):
    def fail_authoritative_resolution(plan):
        raise AuthoritativeResearchStateError(
            RuntimeError(
                "authoritative execution input resolution failed"
            )
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
        execution_input_resolver=(
            fail_authoritative_resolution
        ),
    )

    with pytest.raises(
        AuthoritativeResearchStateError,
        match=(
            "authoritative execution input "
            "resolution failed"
        ),
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

    assert _attempt_count(catalog) == 0
    assert retrieval.calls == []
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
        ._bind_trial_spec_create_attempt_for_running_job
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
        "_bind_trial_spec_create_attempt_for_running_job",
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
        ._complete_running_job_with_exact_reuse
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
        "_complete_running_job_with_exact_reuse",
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

    with pytest.raises(
        AuthoritativeResearchStateError,
        match=(
            "DatasetReference artifact is unavailable "
            "or corrupt"
        ),
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
    assert persisted_job.reused_attempt_id is None

    persisted_trial = catalog.load_trial(
        claimed.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.PENDING
    )
    assert persisted_trial.reused_attempt_id is None

    assert _attempt_count(catalog) == 1
    assert len(execution_calls) == 1
    assert len(retrieval.calls) == 2


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


def test_m94h2_worker_pool_stops_after_authoritative_retrieval_failure(
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
        retrieval_error=(
            AuthoritativeResearchStateError(
                RuntimeError(
                    "authoritative retrieval integrity failed"
                )
            )
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

    with pytest.raises(
        AuthoritativeResearchStateError,
        match="authoritative retrieval integrity failed",
    ):
        queue.run_worker_pool(
            revision_id,
            worker_id_factory=(
                lambda slot: f"worker-h2-retrieval-{slot}"
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
    assert len(retrieval.calls) == 1
    assert _attempt_count(catalog) == 0
    assert execution_calls == []


def test_m94h2_worker_pool_stops_after_corrupt_prepared_manifest(
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

    orchestrator = (
        executor.successor_coordinator.orchestrator
    )
    original_load = (
        orchestrator.artifact_store.load_bytes
    )
    manifest_failures = 0

    def fail_manifest_load(artifact_id):
        nonlocal manifest_failures

        artifact = catalog.load_artifact(
            artifact_id
        )

        if (
            artifact is not None
            and artifact.artifact_kind
            is ResearchArtifactKind.BACKTEST_RUN_MANIFEST
        ):
            manifest_failures += 1
            raise RuntimeError(
                "authoritative prepared manifest corrupt"
            )

        return original_load(
            artifact_id
        )

    orchestrator.artifact_store.load_bytes = (
        fail_manifest_load
    )

    with pytest.raises(
        AuthoritativeResearchStateError,
        match=(
            "manifest artifact is unavailable or corrupt"
        ),
    ):
        queue.run_worker_pool(
            revision_id,
            worker_id_factory=(
                lambda slot: f"worker-h2-manifest-{slot}"
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
    assert manifest_failures == 1
    assert len(retrieval.calls) == 1
    assert _attempt_count(catalog) == 1
    assert execution_calls == []

    running_jobs = [
        job
        for trial in catalog.list_trials_for_revision(
            revision_id
        )
        for job in catalog.list_research_jobs_for_trial(
            trial.trial_id
        )
        if job.state is ResearchJobState.RUNNING
    ]

    assert len(running_jobs) == 1
    assert running_jobs[0].attempt_id is not None

    attempt = catalog.load_run_attempt(
        running_jobs[0].attempt_id
    )

    assert attempt is not None
    assert (
        attempt.state
        is RunAttemptState.RUNNING
    )
    assert attempt.failure_classification is None
    assert attempt.failure_message is None


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

def test_m94g3_transient_operational_failure_is_durably_classified(
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
        execution_error=(
            TransientBacktestOperationalError(
                OSError(
                    "temporary execution I/O failure"
                )
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
    assert (
        terminal_job.failure_classification
        == "transient_operational_failure"
    )
    assert (
        terminal_job.failure_message
        == "temporary execution I/O failure"
    )

    attempt = catalog.load_run_attempt(
        terminal_job.attempt_id
    )
    assert attempt is not None
    assert (
        attempt.state
        is RunAttemptState.FAILED
    )
    assert (
        attempt.failure_classification
        == "transient_operational_failure"
    )

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
        == "transient_operational_failure"
    )

    assert len(retrieval.calls) == 1
    assert len(execution_calls) == 1


def test_m94g3_unknown_execution_failure_is_durably_classified(
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
            "unclassified execution failure"
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
        terminal_job.failure_classification
        == "unknown_failure"
    )
    assert (
        terminal_job.failure_message
        == "unclassified execution failure"
    )

    attempt = catalog.load_run_attempt(
        terminal_job.attempt_id
    )
    assert attempt is not None
    assert (
        attempt.state
        is RunAttemptState.FAILED
    )
    assert (
        attempt.failure_classification
        == "unknown_failure"
    )

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
        == "unknown_failure"
    )

    assert len(retrieval.calls) == 1
    assert len(execution_calls) == 1

def test_m94g4_cancellation_requested_during_financial_execution_preserves_truthful_execution_result(
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

    assert claimed is not None

    original_execute = (
        executor.successor_coordinator
        .orchestrator
        ._execute_candles
    )

    def execute_with_inflight_cancellation(
        **kwargs,
    ):
        current = catalog.load_research_job(
            claimed.job_id
        )
        assert current is not None
        assert (
            current.state
            is ResearchJobState.RUNNING
        )
        assert current.attempt_id is not None

        requested = (
            catalog
            .request_running_research_job_cancellation(
                job_id=claimed.job_id,
                requested_at=TERMINAL_AT,
            )
        )

        assert (
            requested.state
            is ResearchJobState.RUNNING
        )
        assert (
            requested.cancel_requested_at
            == TERMINAL_AT
        )
        assert requested.attempt_id is not None

        return original_execute(
            **kwargs
        )

    (
        executor.successor_coordinator
        .orchestrator
        ._execute_candles
    ) = execute_with_inflight_cancellation

    terminal_job = executor.execute(
        claimed
    )

    assert (
        terminal_job.state
        is ResearchJobState.SUCCEEDED
    )
    assert terminal_job.attempt_id is not None
    assert (
        terminal_job.cancel_requested_at
        == TERMINAL_AT
    )

    persisted_attempt = (
        catalog.load_run_attempt(
            terminal_job.attempt_id
        )
    )

    assert persisted_attempt is not None
    assert (
        persisted_attempt.state
        is RunAttemptState.SUCCEEDED
    )

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.EXECUTED
    )

    assert len(retrieval.calls) == 1
    assert len(execution_calls) == 1

def test_m94i1_registered_execution_ignores_mutated_resolver_strategy_alias(
    tmp_path,
):
    resolved_inputs = _inputs()
    mutable_alias = {
        "suppress": False,
    }

    def resolver_owned_on_new_candle(self, series):
        if mutable_alias["suppress"]:
            return None

        return type(self).on_new_candle(
            self,
            series,
        )

    resolved_inputs.strategy.on_new_candle = MethodType(
        resolver_owned_on_new_candle,
        resolved_inputs.strategy,
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
        execution_input_resolver=(
            lambda plan: resolved_inputs
        ),
    )

    orchestrator = (
        executor.successor_coordinator.orchestrator
    )

    original_load = (
        orchestrator.artifact_store.load_bytes
    )

    manifest_mutations = []

    def mutate_alias_during_manifest_verification(
        artifact_id,
    ):
        artifact = catalog.load_artifact(
            artifact_id
        )

        if (
            artifact is not None
            and artifact.artifact_kind
            is ResearchArtifactKind.BACKTEST_RUN_MANIFEST
        ):
            mutable_alias["suppress"] = True
            manifest_mutations.append(
                artifact_id
            )

        return original_load(
            artifact_id
        )

    orchestrator.artifact_store.load_bytes = (
        mutate_alias_during_manifest_verification
    )

    observed = {}

    def execute_real_engine(**kwargs):
        strategy = kwargs["strategy"]

        observed["strategy"] = strategy

        result = execute_backtest_candles(
            **kwargs
        )

        observed["signals"] = [
            record.signal
            for record in result.bar_records
        ]

        return result

    orchestrator._execute_candles = (
        execute_real_engine
    )

    terminal_job = executor.execute(
        claimed
    )

    assert mutable_alias["suppress"] is True
    assert manifest_mutations

    assert (
        terminal_job.state
        is ResearchJobState.SUCCEEDED
    )
    assert (
        terminal_job.completion_kind
        is ResearchJobCompletionKind.EXECUTED
    )

    executed_strategy = observed["strategy"]

    assert executed_strategy is not resolved_inputs.strategy
    assert type(executed_strategy) is type(
        resolved_inputs.strategy
    )
    assert "on_new_candle" not in vars(
        executed_strategy
    )

    assert observed["signals"] == [
        None,
        "BUY",
        None,
    ]

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.EXECUTED
    )

    assert len(retrieval.calls) == 1
    assert _attempt_count(catalog) == 1

def test_m94i2_corrupt_dataset_reference_blocks_supported_exact_reuse(
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

    orchestrator = (
        executor.successor_coordinator.orchestrator
    )

    evidence = orchestrator.evidence_store.load(
        prior.evidence_id
    )

    dataset_artifact_ids = []

    for reference in evidence.artifact_references:
        if not reference.startswith(
            "artifact:sha256:"
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
            dataset_artifact_ids.append(
                artifact_id
            )

    assert len(dataset_artifact_ids) == 1

    dataset_path = (
        orchestrator.artifact_store._absolute_path(
            dataset_artifact_ids[0]
        )
    )

    original_find = (
        orchestrator.find_exact_reusable_execution
    )

    corruptions = []

    def corrupt_after_preparation(
        experiment_spec_id,
    ):
        reusable = original_find(
            experiment_spec_id
        )

        assert reusable is not None

        dataset_path.write_bytes(
            b'{"corrupt":"m94i2"}'
        )
        corruptions.append(
            dataset_artifact_ids[0]
        )

        return reusable

    orchestrator.find_exact_reusable_execution = (
        corrupt_after_preparation
    )

    with pytest.raises(
        AuthoritativeResearchStateError,
        match=(
            "DatasetReference artifact is unavailable "
            "or corrupt"
        ),
    ):
        executor.execute(
            claimed
        )

    assert corruptions == [
        dataset_artifact_ids[0]
    ]

    persisted_job = catalog.load_research_job(
        claimed.job_id
    )

    assert persisted_job is not None
    assert (
        persisted_job.state
        is ResearchJobState.RUNNING
    )
    assert persisted_job.attempt_id is None
    assert persisted_job.reused_attempt_id is None

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    assert persisted_trial is not None
    assert (
        persisted_trial.disposition
        is TrialDisposition.PENDING
    )
    assert persisted_trial.reused_attempt_id is None

    assert _attempt_count(catalog) == 1
    assert len(execution_calls) == 1


@pytest.mark.parametrize(
    "manifest_error",
    (
        PermissionError(
            "m94i2 manifest permission denied"
        ),
        OSError(
            "m94i2 manifest filesystem read failed"
        ),
    ),
    ids=(
        "permission-error",
        "os-error",
    ),
)
def test_m94i2_worker_pool_stops_after_unreadable_authoritative_manifest(
    tmp_path,
    manifest_error,
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

    orchestrator = (
        executor.successor_coordinator.orchestrator
    )

    original_load = (
        orchestrator.artifact_store.load_bytes
    )

    manifest_failures = []

    def fail_manifest_load(
        artifact_id,
    ):
        artifact = catalog.load_artifact(
            artifact_id
        )

        if (
            artifact is not None
            and artifact.artifact_kind
            is ResearchArtifactKind.BACKTEST_RUN_MANIFEST
        ):
            manifest_failures.append(
                artifact_id
            )
            raise manifest_error

        return original_load(
            artifact_id
        )

    orchestrator.artifact_store.load_bytes = (
        fail_manifest_load
    )

    with pytest.raises(
        AuthoritativeResearchStateError,
        match=(
            "manifest artifact is unavailable or corrupt"
        ),
    ):
        queue.run_worker_pool(
            revision_id,
            worker_id_factory=(
                lambda slot: f"worker-i2-{slot}"
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
    assert len(manifest_failures) == 1
    assert len(retrieval.calls) == 1
    assert _attempt_count(catalog) == 1
    assert execution_calls == []

    trials = catalog.list_trials_for_revision(
        revision_id
    )

    dispositions = sorted(
        trial.disposition
        for trial in trials
        if trial.disposition is not None
    )

    assert dispositions == [
        TrialDisposition.PENDING,
        TrialDisposition.PENDING,
    ]



def test_m94m_concurrent_claimed_job_replay_executes_once(
    tmp_path,
    monkeypatch,
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

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

    assert claimed is not None

    barrier = Barrier(2)
    original_resolve = executor.plan_resolver.resolve

    def synchronized_resolve(trial_id):
        barrier.wait(timeout=10)
        return original_resolve(trial_id)

    monkeypatch.setattr(
        executor.plan_resolver,
        "resolve",
        synchronized_resolve,
    )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(executor.execute, claimed)
            for _ in range(2)
        ]

        outcomes = []
        failures = []

        for future in futures:
            try:
                outcomes.append(future.result(timeout=15))
            except Exception as error:
                failures.append(error)

    assert len(outcomes) == 1
    assert outcomes[0].state is ResearchJobState.SUCCEEDED
    assert len(failures) == 1
    assert isinstance(failures[0], ValueError)

    assert len(execution_calls) == 1
    assert _attempt_count(catalog) == 1

    job = catalog.load_research_job(claimed.job_id)
    persisted_trial = catalog.load_trial(trial.trial_id)

    assert job is not None
    assert job.state is ResearchJobState.SUCCEEDED
    assert persisted_trial is not None
    assert persisted_trial.disposition is TrialDisposition.EXECUTED


@pytest.mark.parametrize(
    "outcome",
    ("SUCCEEDED", "FAILED"),
)
def test_m94q_followup_cancel_chronology_claimed_executor(
    tmp_path,
    outcome,
):
    from datetime import timedelta

    catalog, trial, claimed, executor, retrieval, calls = (
        _environment(
            tmp_path,
            execution_input_resolver=lambda plan: _inputs(),
        )
    )

    orchestrator = (
        executor.successor_coordinator.orchestrator
    )

    original_execute = orchestrator._execute_candles
    request_time = TERMINAL_AT + timedelta(seconds=1)

    def execution_with_cancellation_request(**kwargs):
        catalog.request_running_research_job_cancellation(
            job_id=claimed.job_id,
            requested_at=request_time,
        )

        if outcome == "FAILED":
            raise ValueError(
                "m94q clock regression fixture"
            )

        return original_execute(**kwargs)

    orchestrator._execute_candles = (
        execution_with_cancellation_request
    )

    terminal_job = executor.execute(claimed)

    assert terminal_job.cancel_requested_at == request_time
    assert terminal_job.terminal_at >= request_time

    terminal_attempt = catalog.load_run_attempt(
        terminal_job.attempt_id
    )
    terminal_trial = catalog.load_trial(trial.trial_id)

    assert terminal_attempt.terminal_at >= request_time
    assert terminal_trial.disposition_at >= request_time


# M94Q-FRESH-01: accepted account cash must have an
# explanation in the authoritative execution history.
# These tests first establish the original five RED
# boundaries without modifying the production validator.

def _m94q_fresh_financial_real_result(tmp_path):
    from core.runtime.backtest_runtime import (
        execute_backtest_candles,
    )
    from core.research.reproducibility import (
        decode_stable_backtest_result_bytes,
    )

    environment = _environment(
        tmp_path,
        execution_input_resolver=lambda plan: _inputs(),
    )
    catalog, trial, claimed, executor, _, _ = environment
    orchestrator = executor.successor_coordinator.orchestrator
    orchestrator._execute_candles = execute_backtest_candles

    completed = executor.execute(claimed)
    attempt = catalog.load_run_attempt(completed.attempt_id)

    original = decode_stable_backtest_result_bytes(
        orchestrator.artifact_store.load_bytes(
            attempt.result_artifact_id
        )
    )

    return environment, orchestrator, completed, original


def _m94q_fresh_financial_flat_payload(original, *, gain):
    import copy

    result = copy.deepcopy(original)
    result["trades"] = []

    for index, record in enumerate(result["bar_records"]):
        cash = 100000.0
        if gain and index == len(result["bar_records"]) - 1:
            cash += 1000.0

        record.update(
            cash=cash,
            equity=cash,
            position_size=0.0,
            drawdown=0.0,
            execution_event=None,
            execution_price=None,
            execution_quantity=None,
            signal=None,
            state=None,
            decision_snapshot={},
        )

    result["equity_curve"] = [
        (record["timestamp"], record["equity"])
        for record in result["bar_records"]
    ]

    return result


def _m94q_fresh_financial_install(
    catalog, artifacts, attempt_id, result,
):
    import json
    import sqlite3

    from core.research.models.research_catalog import (
        ResearchArtifactKind,
    )
    from core.research.reproducibility import (
        BACKTEST_RESULT_SCHEMA,
        canonical_bytes,
    )
    from core.research.research_artifact_store import (
        research_artifact_reference,
    )

    attempt = catalog.load_run_attempt(attempt_id)
    payload = canonical_bytes(
        result,
        schema=BACKTEST_RESULT_SCHEMA,
    )

    artifact = artifacts.persist_bytes(
        payload,
        artifact_kind=ResearchArtifactKind.BACKTEST_RESULT,
        schema_id=BACKTEST_RESULT_SCHEMA,
        created_at=TERMINAL_AT,
    )
    catalog.save_artifact(artifact)

    with sqlite3.connect(catalog.database_path) as db:
        current = db.execute(
            "SELECT artifact_references "
            "FROM research_evidence WHERE evidence_id=?",
            (attempt.evidence_id,),
        ).fetchone()

        references = json.loads(current[0])
        old_reference = research_artifact_reference(
            attempt.result_artifact_id
        )
        new_reference = research_artifact_reference(
            artifact.artifact_id
        )
        references = [
            new_reference if ref == old_reference else ref
            for ref in references
        ]

        db.execute(
            "UPDATE run_attempts SET result_artifact_id=? "
            "WHERE attempt_id=?",
            (artifact.artifact_id, attempt_id),
        )
        db.execute(
            "UPDATE research_evidence SET "
            "result_fingerprint=?, artifact_references=? "
            "WHERE evidence_id=?",
            (
                artifact.artifact_id,
                json.dumps(references, separators=(",", ":")),
                attempt.evidence_id,
            ),
        )

    assert artifacts.load_bytes(artifact.artifact_id) == payload


@pytest.mark.parametrize(
    "boundary",
    [
        "direct",
        "decoder",
        "reuse",
        "aggregation",
        "registered_reuse",
    ],
)
def test_m94q_fresh_financial_cash_growth_fails_closed(
    tmp_path, boundary,
):
    from core.research.models.registered_study import (
        EvidenceReusePolicy,
    )
    from core.research.reproducibility import (
        BACKTEST_RESULT_SCHEMA,
        canonical_bytes,
        decode_stable_backtest_result_bytes,
        validate_stable_backtest_result_payload,
    )

    environment, orchestrator, completed, original = (
        _m94q_fresh_financial_real_result(tmp_path)
    )
    catalog, trial = environment[:2]

    impossible = _m94q_fresh_financial_flat_payload(
        original,
        gain=True,
    )

    assert len(impossible["bar_records"]) >= 2
    assert impossible["trades"] == []
    assert all(
        record["position_size"] == 0
        and record["execution_event"] is None
        for record in impossible["bar_records"]
    )
    assert (
        impossible["bar_records"][-1]["cash"]
        - impossible["bar_records"][0]["cash"]
        == 1000.0
    )

    if boundary == "direct":
        with pytest.raises(ValueError):
            validate_stable_backtest_result_payload(
                impossible
            )
        return

    if boundary == "decoder":
        with pytest.raises(ValueError):
            decode_stable_backtest_result_bytes(
                canonical_bytes(
                    impossible,
                    schema=BACKTEST_RESULT_SCHEMA,
                )
            )
        return

    _m94q_fresh_financial_install(
        catalog,
        orchestrator.artifact_store,
        completed.attempt_id,
        impossible,
    )

    if boundary == "reuse":
        spec = catalog.load_run_attempt(
            completed.attempt_id
        ).experiment_spec_id

        assert (
            orchestrator.find_exact_reusable_execution(spec)
            is None
        )
    elif boundary == "aggregation":
        from core.research.study_aggregation import (
            StudyAggregationError,
            StudyAggregationService,
        )

        with pytest.raises(StudyAggregationError):
            StudyAggregationService(
                catalog_store=catalog,
                artifact_store=orchestrator.artifact_store,
            ).aggregate_revision(trial.study_revision_id)
    else:
        fresh_environment = _environment(
            tmp_path,
            execution_input_resolver=lambda plan: _inputs(),
            evidence_reuse_policy=(
                EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
            ),
        )

        # A second catalog instance opens the same database.
        # The fixture must not restart at its prior attempt ID.
        fresh_environment[0]._attempt_id_factory = (
            lambda: "attempt-claimed-job-002"
        )
        new_executor = fresh_environment[3]
        # The second execution must also use a new evidence ID.
        new_executor.successor_coordinator.orchestrator._evidence_id_factory = (
            lambda: "evidence-claimed-job-002"
        )
        new_claimed = fresh_environment[2]
        outcome = new_executor.execute(new_claimed)

        assert (
            outcome.completion_kind.value != "REUSED"
        ), "Impossible account profit reused in another Trial"


def test_m94q_fresh_financial_flat_constant_cash_valid(
    tmp_path,
):
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    _, _, _, original = (
        _m94q_fresh_financial_real_result(tmp_path)
    )
    legitimate = _m94q_fresh_financial_flat_payload(
        original,
        gain=False,
    )

    assert len(legitimate["bar_records"]) >= 2
    assert (
        validate_stable_backtest_result_payload(legitimate)
        is legitimate
    )


def test_m94q_fresh_financial_real_engine_valid(
    tmp_path,
):
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    _, _, _, result = (
        _m94q_fresh_financial_real_result(tmp_path)
    )

    assert (
        validate_stable_backtest_result_payload(result)
        is result
    )


@pytest.mark.parametrize(
    "boundary",
    ("direct", "decoder"),
)
def test_m94q_fresh_financial_phantom_execution_rejected(
    tmp_path, boundary,
):
    from core.research.reproducibility import (
        BACKTEST_RESULT_SCHEMA,
        canonical_bytes,
        decode_stable_backtest_result_bytes,
        validate_stable_backtest_result_payload,
    )

    _, _, _, original = (
        _m94q_fresh_financial_real_result(tmp_path)
    )

    impossible = _m94q_fresh_financial_flat_payload(
        original,
        gain=True,
    )

    first = impossible["bar_records"][0]
    first["execution_event"] = "BUY"
    first["execution_price"] = 100.0
    first["execution_quantity"] = 1

    assert not impossible["trades"]
    assert all(
        record["position_size"] == 0
        for record in impossible["bar_records"]
    )

    if boundary == "direct":
        with pytest.raises(
            ValueError,
            match="flat account cash cannot change",
        ):
            validate_stable_backtest_result_payload(impossible)
    else:
        with pytest.raises(
            ValueError,
            match="flat account cash cannot change",
        ):
            decode_stable_backtest_result_bytes(
                canonical_bytes(
                    impossible,
                    schema=BACKTEST_RESULT_SCHEMA,
                )
            )


def _m94q_fresh_numeric_overflow_payload(original, kind):
    payload = _m94q_fresh_financial_flat_payload(
        original,
        gain=False,
    )

    if kind == "marked_equity":
        record = payload["bar_records"][-1]
        record.update(
            open=10,
            high=10,
            low=10,
            close=10,
            cash=10**308,
            equity=15 * 10**307,
            position_size=10**308,
        )
        payload["equity_curve"][-1] = (
            record["timestamp"],
            record["equity"],
        )
        return payload

    assert kind in ("gross_product", "net_difference")

    bars = payload["bar_records"]
    assert len(bars) >= 2

    trade = {
        "symbol": "ABC",
        "entry_time": bars[0]["timestamp"],
        "entry_price": 100.0,
        "exit_time": bars[-1]["timestamp"],
        "exit_price": 101.0,
        "stop_price": 99.0,
        "quantity": 1,
        "direction": "LONG",
        "exit_reason": "fixture",
        "pnl": 1.0,
        "gross_pnl": 1.0,
        "transaction_cost": 0.0,
        "pnl_pct": 1.0,
    }

    if kind == "gross_product":
        trade.update(
            entry_price=1,
            exit_price=10**200,
            quantity=10**200,
            gross_pnl=0,
            pnl=0,
        )
    else:
        trade.update(
            gross_pnl=-(10**308),
            transaction_cost=10**308,
            pnl=0,
        )

    payload["trades"].append(trade)
    return payload


@pytest.mark.parametrize("boundary", ("direct", "decoder"))
@pytest.mark.parametrize(
    "kind",
    ("gross_product", "net_difference", "marked_equity"),
)
def test_m94q_fresh_numeric_overflow_fails_closed(
    tmp_path, kind, boundary,
):
    from core.research.reproducibility import (
        BACKTEST_RESULT_SCHEMA,
        canonical_bytes,
        decode_stable_backtest_result_bytes,
        validate_stable_backtest_result_payload,
    )

    _, _, _, original = (
        _m94q_fresh_financial_real_result(tmp_path)
    )
    payload = _m94q_fresh_numeric_overflow_payload(
        original, kind,
    )

    with pytest.raises(ValueError):
        if boundary == "direct":
            validate_stable_backtest_result_payload(payload)
        else:
            decode_stable_backtest_result_bytes(
                canonical_bytes(
                    payload,
                    schema=BACKTEST_RESULT_SCHEMA,
                )
            )


def test_m94q_fresh_numeric_overflow_exact_reuse_skipped(
    tmp_path,
):
    _, orchestrator, completed, original = (
        _m94q_fresh_financial_real_result(tmp_path)
    )

    catalog = orchestrator.catalog_store
    payload = _m94q_fresh_numeric_overflow_payload(
        original, "gross_product",
    )

    _m94q_fresh_financial_install(
        catalog,
        orchestrator.artifact_store,
        completed.attempt_id,
        payload,
    )

    attempt = catalog.load_run_attempt(
        completed.attempt_id
    )

    assert orchestrator.find_exact_reusable_execution(
        attempt.experiment_spec_id
    ) is None


def test_m94q_fresh_numeric_extreme_integer_rejected(
    tmp_path,
):
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    _, _, _, original = (
        _m94q_fresh_financial_real_result(tmp_path)
    )

    payload = _m94q_fresh_financial_flat_payload(
        original, gain=False,
    )

    record = payload["bar_records"][0]
    record["cash"] = 10**400
    record["equity"] = 10**400
    payload["equity_curve"][0] = (
        record["timestamp"],
        record["equity"],
    )

    with pytest.raises(ValueError):
        validate_stable_backtest_result_payload(payload)


def test_m94q_fresh_numeric_large_finite_integer_valid(
    tmp_path,
):
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    _, _, _, original = (
        _m94q_fresh_financial_real_result(tmp_path)
    )

    payload = _m94q_fresh_financial_flat_payload(
        original, gain=False,
    )

    for index, record in enumerate(payload["bar_records"]):
        record["cash"] = 10**200
        record["equity"] = 10**200
        payload["equity_curve"][index] = (
            record["timestamp"],
            record["equity"],
        )

    assert (
        validate_stable_backtest_result_payload(payload)
        is payload
    )


@pytest.mark.parametrize("through_executor", (False, True))
def test_m94q_fresh_cancel_pre_attempt_request_wins(
    tmp_path,
    through_executor,
):
    request_at = TERMINAL_AT + timedelta(seconds=1)
    holder = {}

    def resolver(plan):
        holder["catalog"].request_running_research_job_cancellation(
            job_id=holder["job"].job_id,
            requested_at=request_at,
        )
        raise ConnectionError(
            "preparation failed after durable cancellation"
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
        execution_input_resolver=(
            resolver
            if through_executor
            else lambda plan: _inputs()
        ),
    )

    holder.update(catalog=catalog, job=claimed)

    if through_executor:
        terminal_job = executor.execute(claimed)
        terminal_trial = catalog.load_trial(trial.trial_id)
        event = catalog.load_trial_disposition_events(
            trial.trial_id
        )[-1]
    else:
        catalog.request_running_research_job_cancellation(
            job_id=claimed.job_id,
            requested_at=request_at,
        )
        terminal_trial, terminal_job, event = (
            catalog.fail_running_job_without_attempt(
                job_id=claimed.job_id,
                terminal_at=TERMINAL_AT,
                failure_classification="unknown_failure",
                failure_message="preparation failed",
            )
        )

    assert _attempt_count(catalog) == 0
    assert execution_calls == []
    assert retrieval.calls == []

    assert terminal_job.job_id == claimed.job_id
    assert terminal_job.attempt_id is None
    assert (
        terminal_job.cancel_requested_at
        == request_at
    )

    # Durable cancellation is authoritative over the
    # subsequent pre-attempt preparation failure.
    assert terminal_job.state is ResearchJobState.CANCELLED
    assert terminal_job.terminal_at >= request_at
    assert terminal_job.failure_classification is None
    assert terminal_job.failure_message is None

    assert terminal_trial is not None
    assert (
        terminal_trial.disposition
        is TrialDisposition.CANCELLED
    )
    assert terminal_trial.disposition_at >= request_at
    assert terminal_trial.failure_classification is None
    assert terminal_trial.failure_message is None

    assert event.new_disposition is TrialDisposition.CANCELLED
    assert event.causing_job_id == claimed.job_id
    assert event.occurred_at >= request_at
    assert (
        event.reason_classification
        == "running_cancellation_acknowledged"
    )

    events = catalog.load_trial_disposition_events(
        trial.trial_id
    )
    assert len(events) == 2


def test_m94q_fresh_cancel_pre_attempt_no_request_stays_failure(
    tmp_path,
):
    (
        catalog,
        trial,
        claimed,
        _executor,
        _retrieval,
        execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=lambda plan: _inputs(),
    )

    terminal_trial, terminal_job, event = (
        catalog.fail_running_job_without_attempt(
            job_id=claimed.job_id,
            terminal_at=TERMINAL_AT,
            failure_classification="unknown_failure",
            failure_message="ordinary preparation failure",
        )
    )

    assert _attempt_count(catalog) == 0
    assert execution_calls == []

    assert terminal_job.state is ResearchJobState.FAILED
    assert terminal_job.attempt_id is None
    assert terminal_job.cancel_requested_at is None
    assert terminal_job.terminal_at == TERMINAL_AT
    assert (
        terminal_job.failure_classification
        == "unknown_failure"
    )

    assert terminal_trial.disposition is TrialDisposition.FAILED
    assert terminal_trial.disposition_at == TERMINAL_AT
    assert event.new_disposition is TrialDisposition.FAILED
    assert event.occurred_at == TERMINAL_AT

    assert len(
        catalog.load_trial_disposition_events(
            trial.trial_id
        )
    ) == 2


@pytest.mark.parametrize(
    "boundary",
    ("reuse", "study"),
)
@pytest.mark.parametrize(
    "result_initial_capital,valid",
    ((100000.0, True), (200000.0, False)),
    ids=("matching_manifest", "mismatched_manifest"),
)
def test_m94q_fresh_manifest_capital_binding(
    tmp_path,
    boundary,
    result_initial_capital,
    valid,
):
    """Reuse and Study must bind result capital to immutable input."""
    from core.research.reproducibility import (
        BACKTEST_RUN_MANIFEST_SCHEMA,
        decode_canonical_bytes,
    )
    from core.research.study_aggregation import (
        StudyAggregationError,
        StudyAggregationService,
    )

    environment, orchestrator, completed, original = (
        _m94q_fresh_financial_real_result(tmp_path)
    )
    catalog, trial = environment[:2]

    attempt = catalog.load_run_attempt(completed.attempt_id)
    spec = catalog.load_experiment_spec(
        attempt.experiment_spec_id
    )
    manifest = decode_canonical_bytes(
        orchestrator.artifact_store.load_bytes(
            spec.manifest_artifact_id
        ),
        schema=BACKTEST_RUN_MANIFEST_SCHEMA,
    )
    assert manifest["initial_capital"] == 100000.0

    result = _m94q_fresh_financial_flat_payload(
        original,
        gain=False,
    )
    for record in result["bar_records"]:
        record["cash"] = result_initial_capital
        record["equity"] = result_initial_capital

    result["equity_curve"] = [
        (record["timestamp"], record["equity"])
        for record in result["bar_records"]
    ]

    _m94q_fresh_financial_install(
        catalog,
        orchestrator.artifact_store,
        completed.attempt_id,
        result,
    )

    if boundary == "reuse":
        reused = orchestrator.find_exact_reusable_execution(
            attempt.experiment_spec_id
        )
        assert (reused is not None) is valid
        return

    aggregation = StudyAggregationService(
        catalog_store=catalog,
        artifact_store=orchestrator.artifact_store,
    )

    if valid:
        assert (
            aggregation.aggregate_revision(trial.study_revision_id)
            is not None
        )
    else:
        with pytest.raises(StudyAggregationError):
            aggregation.aggregate_revision(trial.study_revision_id)

# M94Q-IND-20261019-01 PERMANENT RED REGRESSION
#
# A canonical same-bar flat-to-flat trade must still prove that
# its entry could be funded from the authoritative pre-bar cash.
# These tests intentionally fail until the production validator
# enforces the accepted long-only, unlevered M4 funding invariant.

def _m94q_independent_same_bar_payload(
    *,
    first_timestamp,
    settlement_timestamp,
    quantity,
):
    initial_cash = 100_000.0
    entry_price = 100.0
    exit_price = 101.0

    gross_pnl = (
        exit_price - entry_price
    ) * quantity

    final_cash = initial_cash + gross_pnl

    first = {
        "timestamp": first_timestamp,
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.0,
        "volume": 1_000.0,
        "strategy": "m94q-independent-same-bar",
        "state": None,
        "signal": None,
        "execution_event": None,
        "execution_price": None,
        "execution_quantity": None,
        "decision_snapshot": {},
        "equity": initial_cash,
        "cash": initial_cash,
        "position_size": 0.0,
        "drawdown": 0.0,
    }

    settlement = {
        "timestamp": settlement_timestamp,
        "open": 100.0,
        "high": 102.0,
        "low": 99.0,
        "close": 101.0,
        "volume": 1_000.0,
        "strategy": "m94q-independent-same-bar",
        "state": None,
        "signal": None,
        "execution_event": "PROTECTIVE_EXIT",
        "execution_price": exit_price,
        "execution_quantity": quantity,
        "decision_snapshot": {},
        "equity": final_cash,
        "cash": final_cash,
        "position_size": 0.0,
        "drawdown": 0.0,
    }

    trade = {
        "symbol": "RELIANCE",
        "entry_time": settlement_timestamp,
        "entry_price": entry_price,
        "exit_time": settlement_timestamp,
        "exit_price": exit_price,
        "stop_price": 98.0,
        "quantity": quantity,
        "direction": "LONG",
        "exit_reason": "STOP_LOSS",
        "gross_pnl": gross_pnl,
        "transaction_cost": 0.0,
        "pnl": gross_pnl,
        "pnl_pct": 1.0,
    }

    bars = [
        first,
        settlement,
    ]

    return {
        "trades": [trade],
        "bar_records": bars,
        "equity_curve": [
            (
                record["timestamp"],
                record["equity"],
            )
            for record in bars
        ],
    }


@pytest.mark.parametrize(
    "boundary",
    (
        "direct",
        "decoder",
        "reuse",
        "aggregation",
        "registered_reuse",
    ),
)
def test_m94q_independent_same_bar_unaffordable_entry_fails_closed(
    tmp_path,
    boundary,
):
    from core.research.models.registered_study import (
        EvidenceReusePolicy,
    )
    from core.research.reproducibility import (
        BACKTEST_RESULT_SCHEMA,
        canonical_bytes,
        decode_stable_backtest_result_bytes,
        validate_stable_backtest_result_payload,
    )

    (
        environment,
        orchestrator,
        completed,
        original,
    ) = _m94q_fresh_financial_real_result(
        tmp_path
    )

    catalog, trial = environment[:2]

    assert len(original["bar_records"]) >= 2

    timestamps = [
        original["bar_records"][0]["timestamp"],
        original["bar_records"][1]["timestamp"],
    ]

    impossible = (
        _m94q_independent_same_bar_payload(
            first_timestamp=timestamps[0],
            settlement_timestamp=timestamps[1],
            quantity=2_000,
        )
    )

    trade = impossible["trades"][0]

    assert (
        trade["entry_price"]
        * trade["quantity"]
        == 200_000.0
    )

    assert (
        impossible["bar_records"][0]["cash"]
        == 100_000.0
    )

    assert (
        trade["entry_price"]
        * trade["quantity"]
        > impossible["bar_records"][0]["cash"]
    )

    if boundary == "direct":
        with pytest.raises(
            ValueError,
            match="fund|cash|afford",
        ):
            validate_stable_backtest_result_payload(
                impossible
            )

        return

    if boundary == "decoder":
        with pytest.raises(
            ValueError,
            match="fund|cash|afford",
        ):
            decode_stable_backtest_result_bytes(
                canonical_bytes(
                    impossible,
                    schema=BACKTEST_RESULT_SCHEMA,
                )
            )

        return

    _m94q_fresh_financial_install(
        catalog,
        orchestrator.artifact_store,
        completed.attempt_id,
        impossible,
    )

    if boundary == "reuse":
        source_attempt = catalog.load_run_attempt(
            completed.attempt_id
        )

        assert (
            orchestrator.find_exact_reusable_execution(
                source_attempt.experiment_spec_id
            )
            is None
        )

        return

    if boundary == "aggregation":
        from core.research.study_aggregation import (
            StudyAggregationError,
            StudyAggregationService,
        )

        with pytest.raises(
            StudyAggregationError,
        ):
            StudyAggregationService(
                catalog_store=catalog,
                artifact_store=(
                    orchestrator.artifact_store
                ),
            ).aggregate_revision(
                trial.study_revision_id
            )

        return

    fresh_environment = _environment(
        tmp_path,
        execution_input_resolver=lambda plan: _inputs(),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        ),
    )

    fresh_environment[0]._attempt_id_factory = (
        lambda: "attempt-m94q-ind-01-fresh"
    )

    new_executor = fresh_environment[3]

    (
        new_executor
        .successor_coordinator
        .orchestrator
        ._evidence_id_factory
    ) = lambda: "evidence-m94q-ind-01-fresh"

    outcome = new_executor.execute(
        fresh_environment[2]
    )

    assert (
        outcome.completion_kind.value
        != "REUSED"
    ), (
        "unaffordable same-bar artifact was reused "
        "into another registered Trial"
    )


def test_m94q_independent_same_bar_exact_cash_affordable_control(
    tmp_path,
):
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    (
        _environment_value,
        _orchestrator,
        _completed,
        original,
    ) = _m94q_fresh_financial_real_result(
        tmp_path
    )

    assert len(original["bar_records"]) >= 2

    payload = _m94q_independent_same_bar_payload(
        first_timestamp=(
            original["bar_records"][0]["timestamp"]
        ),
        settlement_timestamp=(
            original["bar_records"][1]["timestamp"]
        ),
        quantity=1_000,
    )

    assert (
        payload["trades"][0]["entry_price"]
        * payload["trades"][0]["quantity"]
        == payload["bar_records"][0]["cash"]
    )

    assert (
        validate_stable_backtest_result_payload(
            payload
        )
        is payload
    )

# M94Q-IND-20261019-01 FEE-BOUNDARY POSITIVE CONTROL
#
# The canonical artifact exposes total round-trip transaction cost,
# not an authoritative split between entry-side and exit-side fees.
# This control therefore proves only an unambiguously affordable
# envelope: entry notional plus the entire recorded transaction cost
# fits within the authoritative pre-bar cash.

def test_m94q_independent_same_bar_fee_boundary_affordable_control(
    tmp_path,
):
    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    (
        _environment_value,
        _orchestrator,
        _completed,
        original,
    ) = _m94q_fresh_financial_real_result(
        tmp_path
    )

    assert len(original["bar_records"]) >= 2

    payload = _m94q_independent_same_bar_payload(
        first_timestamp=(
            original["bar_records"][0]["timestamp"]
        ),
        settlement_timestamp=(
            original["bar_records"][1]["timestamp"]
        ),
        quantity=999,
    )

    trade = payload["trades"][0]

    transaction_cost = 100.0

    trade["transaction_cost"] = (
        transaction_cost
    )

    trade["pnl"] = (
        trade["gross_pnl"]
        - transaction_cost
    )

    pre_bar_cash = (
        payload["bar_records"][0]["cash"]
    )

    assert (
        trade["entry_price"]
        * trade["quantity"]
        + transaction_cost
        == pre_bar_cash
    )

    final_cash = (
        pre_bar_cash
        + trade["pnl"]
    )

    payload["bar_records"][-1]["cash"] = (
        final_cash
    )

    payload["bar_records"][-1]["equity"] = (
        final_cash
    )

    payload["equity_curve"][-1] = (
        payload["bar_records"][-1]["timestamp"],
        final_cash,
    )

    assert (
        validate_stable_backtest_result_payload(
            payload
        )
        is payload
    )

# M94Q-IND-20261020-01 PERMANENT RED REGRESSION
#
# A canonical result-bearing Trial must not accept a successful
# RunAttempt whose durable ExperimentSpec identity differs from the
# immutable ExperimentSpec bound to that Trial.
#
# Permanent coverage is 2 lineages x 3 authoritative read boundaries:
# EXECUTED / REUSED crossed with core / application / HTTP.

@pytest.mark.parametrize(
    "lineage",
    ("EXECUTED", "REUSED"),
)
@pytest.mark.parametrize(
    "boundary",
    ("core", "application", "http"),
)
def test_m94q_independent_attempt_spec_mismatch_fails_closed(
    tmp_path,
    monkeypatch,
    lineage,
    boundary,
):
    import asyncio
    import sqlite3
    from dataclasses import replace

    from fastapi import FastAPI

    import api.routes.research_routes as research_routes

    from api.research_application import (
        get_research_aggregation,
    )
    from core.research.study_aggregation import (
        StudyAggregationError,
        StudyAggregationService,
    )

    (
        catalog,
        trial,
        claimed,
        executor,
        _retrieval,
        _calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=lambda _plan: _inputs(),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
            if lineage == "REUSED"
            else EvidenceReusePolicy.FORCE_NEW_EXECUTION
        ),
    )

    coordinator = executor.successor_coordinator

    # Use the real accepted M4 execution function so only durable
    # ExperimentSpec lineage is corrupted.
    coordinator.orchestrator._execute_candles = (
        execute_backtest_candles
    )

    def execute_standalone(inputs):
        return coordinator.execute(
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

    if lineage == "REUSED":
        execute_standalone(
            _inputs()
        )

    terminal = executor.execute(
        claimed
    )

    assert (
        terminal.completion_kind.value
        == lineage
    )

    source_attempt_id = (
        terminal.reused_attempt_id
        if lineage == "REUSED"
        else terminal.attempt_id
    )

    assert source_attempt_id is not None

    original_attempt = (
        catalog.load_run_attempt(
            source_attempt_id
        )
    )

    assert original_attempt is not None

    different = _inputs()

    different.config.strategy_params[
        "slow_period"
    ] = 3

    different = replace(
        different,
        strategy=create_strategy(
            different.config
        ),
    )

    alternate_execution = (
        execute_standalone(
            different
        )
    )

    alternate_attempt = (
        catalog.load_run_attempt(
            alternate_execution.attempt_id
        )
    )

    assert alternate_attempt is not None

    assert (
        alternate_attempt.experiment_spec_id
        != original_attempt.experiment_spec_id
    )

    aggregation = StudyAggregationService(
        catalog_store=catalog,
        artifact_store=(
            coordinator.orchestrator.artifact_store
        ),
    )

    baseline = aggregation.aggregate_revision(
        trial.study_revision_id
    )

    assert baseline.result_bearing_trials == 1

    # Preserve every result/evidence/job/event relationship and damage
    # only the foreign-key-valid attempt -> ExperimentSpec reference.
    with sqlite3.connect(
        catalog.database_path
    ) as connection:
        connection.execute(
            "PRAGMA foreign_keys=ON"
        )
        connection.execute(
            """
            UPDATE run_attempts
            SET experiment_spec_id = ?
            WHERE attempt_id = ?
            """,
            (
                alternate_attempt.experiment_spec_id,
                source_attempt_id,
            ),
        )

    persisted_trial = catalog.load_trial(
        trial.trial_id
    )

    damaged_attempt = catalog.load_run_attempt(
        source_attempt_id
    )

    assert persisted_trial is not None
    assert damaged_attempt is not None

    assert (
        persisted_trial.experiment_spec_id
        == original_attempt.experiment_spec_id
    )

    assert (
        damaged_attempt.experiment_spec_id
        == alternate_attempt.experiment_spec_id
    )

    config = AppConfig(
        research_database_path=str(
            catalog.database_path
        ),
        research_artifact_root=str(
            tmp_path / "artifacts"
        ),
    )

    def application():
        return get_research_aggregation(
            trial.study_revision_id,
            app_config=config,
        )

    if boundary == "core":
        with pytest.raises(
            StudyAggregationError,
            match="ExperimentSpec|lineage|exact",
        ):
            aggregation.aggregate_revision(
                trial.study_revision_id
            )
        return

    if boundary == "application":
        with pytest.raises(
            StudyAggregationError,
            match="ExperimentSpec|lineage|exact",
        ):
            application()
        return

    monkeypatch.setattr(
        research_routes,
        "get_research_aggregation_application",
        lambda _revision_id: application(),
    )

    app = FastAPI()

    app.include_router(
        research_routes.router,
        prefix="/api/research",
    )

    path = (
        "/api/research/study-revisions/"
        f"{trial.study_revision_id}/aggregation"
    )

    messages = []

    async def request():
        async def receive():
            return {
                "type": "http.request",
                "body": b"",
                "more_body": False,
            }

        async def send(message):
            messages.append(
                message
            )

        await app(
            {
                "type": "http",
                "asgi": {
                    "version": "3.0",
                },
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "root_path": "",
                "query_string": b"",
                "headers": [],
                "client": (
                    "m94q-regression",
                    1,
                ),
                "server": (
                    "m94q-regression",
                    80,
                ),
            },
            receive,
            send,
        )

    asyncio.run(
        request()
    )

    status = next(
        message["status"]
        for message in messages
        if message["type"]
        == "http.response.start"
    )

    assert status == 500


# M94Q-IND-20261019-01 STRICT TINY-OVERSPEND REGRESSION
#
# The unlevered funding rule is an exact inequality. A positive
# overspend must fail even when it is smaller than the numerical
# tolerance used for ordinary derived-value reconciliation.

def test_m94q_independent_same_bar_tiny_overspend_fails_closed(
    tmp_path,
):
    import math

    from core.research.reproducibility import (
        validate_stable_backtest_result_payload,
    )

    (
        _environment_value,
        _orchestrator,
        _completed,
        original,
    ) = _m94q_fresh_financial_real_result(
        tmp_path
    )

    assert len(
        original["bar_records"]
    ) >= 2

    payload = _m94q_independent_same_bar_payload(
        first_timestamp=(
            original["bar_records"][0]["timestamp"]
        ),
        settlement_timestamp=(
            original["bar_records"][1]["timestamp"]
        ),
        quantity=1_000,
    )

    trade = payload["trades"][0]

    pre_bar_cash = (
        payload["bar_records"][0]["cash"]
    )

    # Smallest representable increase above 100.0. With quantity
    # 1,000 this creates a positive overspend well below 1e-8.
    trade["entry_price"] = math.nextafter(
        trade["entry_price"],
        math.inf,
    )

    trade["gross_pnl"] = (
        (
            trade["exit_price"]
            - trade["entry_price"]
        )
        * trade["quantity"]
    )

    trade["pnl"] = (
        trade["gross_pnl"]
        - trade["transaction_cost"]
    )

    trade["pnl_pct"] = (
        (
            trade["exit_price"]
            - trade["entry_price"]
        )
        / trade["entry_price"]
    ) * 100.0

    final_cash = (
        pre_bar_cash
        + trade["pnl"]
    )

    settlement = payload[
        "bar_records"
    ][1]

    settlement["cash"] = final_cash
    settlement["equity"] = final_cash

    payload["equity_curve"][1] = (
        settlement["timestamp"],
        final_cash,
    )

    entry_notional = (
        trade["entry_price"]
        * trade["quantity"]
    )

    overspend = (
        entry_notional
        - pre_bar_cash
    )

    assert overspend > 0.0
    assert overspend < 1e-8

    with pytest.raises(
        ValueError,
        match="funded by pre-bar cash",
    ):
        validate_stable_backtest_result_payload(
            payload
        )
# M94Q-FRESH-20261020-03 REAL PERSISTED BOUNDARY REGRESSION
#
# The selected result of a result-bearing Trial must remain bound to the
# actual ACCEPTED ResearchEvidence of its authoritative RunAttempt.
#
# Coverage:
#   EXECUTED / REUSED
#       x core Study aggregation
#       x application aggregation
#       x real FastAPI/ASGI HTTP aggregation
#
# Corruption deliberately keeps ordinary attempt/job/event identity
# internally consistent and changes the selected result to another real
# canonical Backtest result artifact. The accepted evidence remains bound
# to the original result, so only the evidence/result authority is false.


@pytest.mark.parametrize(
    "lineage",
    ("EXECUTED", "REUSED"),
)
@pytest.mark.parametrize(
    "boundary",
    ("core", "application", "http"),
)
def test_m94q_fresh_03_result_evidence_binding_fails_closed_across_real_boundaries(
    tmp_path,
    monkeypatch,
    lineage,
    boundary,
):
    import asyncio
    import json
    import sqlite3
    from dataclasses import replace

    from fastapi import FastAPI

    import api.routes.research_routes as research_routes

    from api.research_application import (
        get_research_aggregation,
    )
    from core.research.sqlite_research_evidence_store import (
        SQLiteResearchEvidenceStore,
    )
    from core.research.study_aggregation import (
        StudyAggregationError,
        StudyAggregationService,
    )

    (
        catalog,
        trial,
        claimed,
        executor,
        _retrieval,
        _calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda _plan: _inputs()
        ),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
            if lineage == "REUSED"
            else EvidenceReusePolicy.FORCE_NEW_EXECUTION
        ),
    )

    coordinator = (
        executor.successor_coordinator
    )

    orchestrator = (
        coordinator.orchestrator
    )

    # Produce real canonical result/evidence artifacts through
    # the accepted M4 physical execution path.
    orchestrator._execute_candles = (
        execute_backtest_candles
    )

    def execute_standalone(inputs):
        return coordinator.execute(
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

    # REUSED needs an already accepted exact source.
    if lineage == "REUSED":
        execute_standalone(
            _inputs()
        )

    terminal = executor.execute(
        claimed
    )

    assert (
        terminal.completion_kind.value
        == lineage
    )

    source_attempt_id = (
        terminal.reused_attempt_id
        if lineage == "REUSED"
        else terminal.attempt_id
    )

    assert source_attempt_id is not None

    original_attempt = (
        catalog.load_run_attempt(
            source_attempt_id
        )
    )

    assert original_attempt is not None
    assert (
        original_attempt.evidence_id
        is not None
    )
    assert (
        original_attempt.result_artifact_id
        is not None
    )

    original_evidence = (
        SQLiteResearchEvidenceStore(
            catalog.database_path
        ).load(
            original_attempt.evidence_id
        )
    )

    assert original_evidence is not None
    assert (
        original_evidence.result_fingerprint
        == original_attempt.result_artifact_id
    )

    # Create another genuine canonical execution/result under a
    # deliberately different ExperimentSpec. Its result artifact is
    # valid, but it is not the result authorized by original_evidence.
    different = _inputs()

    different.config.strategy_params[
        "slow_period"
    ] = 3

    different = replace(
        different,
        strategy=create_strategy(
            different.config
        ),
    )

    alternate_execution = (
        execute_standalone(
            different
        )
    )

    alternate_attempt = (
        catalog.load_run_attempt(
            alternate_execution.attempt_id
        )
    )

    assert alternate_attempt is not None
    assert (
        alternate_attempt.result_artifact_id
        is not None
    )
    assert (
        alternate_attempt.result_artifact_id
        != original_attempt.result_artifact_id
    )
    assert (
        alternate_attempt.experiment_spec_id
        != original_attempt.experiment_spec_id
    )

    aggregation = StudyAggregationService(
        catalog_store=catalog,
        artifact_store=(
            orchestrator.artifact_store
        ),
    )

    # The uncorrupted persisted authority must aggregate.
    baseline = (
        aggregation.aggregate_revision(
            trial.study_revision_id
        )
    )

    assert (
        baseline.result_bearing_trials
        == 1
    )

    substituted_result = (
        alternate_attempt.result_artifact_id
    )

    # Preserve attempt identity, successful state, ExperimentSpec,
    # evidence ID and Trial/job/event lineage. Substitute only the
    # selected canonical result.
    #
    # For REUSED, keep the reused job/result IDs mutually consistent
    # as well, so the pre-existing reused-result lineage check cannot
    # be the reason for rejection.
    with sqlite3.connect(
        catalog.database_path
    ) as connection:
        connection.execute(
            "PRAGMA foreign_keys=ON"
        )

        connection.execute(
            """
            UPDATE run_attempts
            SET result_artifact_id = ?
            WHERE attempt_id = ?
            """,
            (
                substituted_result,
                source_attempt_id,
            ),
        )

        if lineage == "REUSED":
            connection.execute(
                """
                UPDATE research_jobs
                SET reused_result_artifact_id = ?
                WHERE job_id = ?
                """,
                (
                    substituted_result,
                    terminal.job_id,
                ),
            )

    damaged_attempt = (
        catalog.load_run_attempt(
            source_attempt_id
        )
    )

    assert damaged_attempt is not None

    # Everything except evidence/result authority remains bound.
    assert (
        damaged_attempt.experiment_spec_id
        == original_attempt.experiment_spec_id
    )
    assert (
        damaged_attempt.evidence_id
        == original_attempt.evidence_id
    )
    assert (
        damaged_attempt.result_artifact_id
        == substituted_result
    )

    persisted_evidence = (
        SQLiteResearchEvidenceStore(
            catalog.database_path
        ).load(
            damaged_attempt.evidence_id
        )
    )

    assert persisted_evidence is not None

    assert (
        persisted_evidence.result_fingerprint
        == original_attempt.result_artifact_id
    )

    assert (
        persisted_evidence.result_fingerprint
        != damaged_attempt.result_artifact_id
    )

    if lineage == "REUSED":
        damaged_job = (
            catalog.load_research_job(
                terminal.job_id
            )
        )

        assert damaged_job is not None
        assert (
            damaged_job.reused_attempt_id
            == source_attempt_id
        )
        assert (
            damaged_job.reused_evidence_id
            == damaged_attempt.evidence_id
        )
        assert (
            damaged_job.reused_result_artifact_id
            == damaged_attempt.result_artifact_id
        )

    # Exact-reuse lookup already has the accepted evidence contract.
    # The damaged source must therefore no longer be reusable.
    assert (
        orchestrator.find_exact_reusable_execution(
            original_attempt.experiment_spec_id
        )
        is None
    )

    config = AppConfig(
        research_database_path=str(
            catalog.database_path
        ),
        research_artifact_root=str(
            tmp_path / "artifacts"
        ),
    )

    def application():
        return get_research_aggregation(
            trial.study_revision_id,
            app_config=config,
        )

    if boundary == "core":
        with pytest.raises(
            StudyAggregationError,
            match=(
                "evidence|Evidence|"
                "authoritative|result"
            ),
        ):
            aggregation.aggregate_revision(
                trial.study_revision_id
            )

        return

    if boundary == "application":
        with pytest.raises(
            StudyAggregationError,
            match=(
                "evidence|Evidence|"
                "authoritative|result"
            ),
        ):
            application()

        return

    # Use the real route and ASGI stack. Only the route's application
    # function reference is rebound so this request uses the same
    # temporary persisted database rather than global configuration.
    monkeypatch.setattr(
        research_routes,
        "get_research_aggregation_application",
        lambda _revision_id: application(),
    )

    app = FastAPI()

    app.include_router(
        research_routes.router,
        prefix="/api/research",
    )

    path = (
        "/api/research/study-revisions/"
        f"{trial.study_revision_id}/aggregation"
    )

    messages = []

    async def request():
        request_sent = False

        async def receive():
            nonlocal request_sent

            if not request_sent:
                request_sent = True

                return {
                    "type": "http.request",
                    "body": b"",
                    "more_body": False,
                }

            return {
                "type": "http.disconnect",
            }

        async def send(message):
            messages.append(
                message
            )

        await app(
            {
                "type": "http",
                "asgi": {
                    "version": "3.0",
                },
                "http_version": "1.1",
                "method": "GET",
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "root_path": "",
                "query_string": b"",
                "headers": [],
                "client": (
                    "m94q-fresh-03",
                    1,
                ),
                "server": (
                    "m94q-fresh-03",
                    80,
                ),
            },
            receive,
            send,
        )

    asyncio.run(
        request()
    )

    status = next(
        message["status"]
        for message in messages
        if message["type"]
        == "http.response.start"
    )

    body = b"".join(
        message.get(
            "body",
            b"",
        )
        for message in messages
        if message["type"]
        == "http.response.body"
    )

    assert status == 500

    assert json.loads(
        body
    ) == {
        "code": "research_aggregation_failed",
        "message": (
            "Research aggregation could not be loaded"
        ),
    }

# M94Q-FRESH-20261020-04 PERMANENT CROSS-DATABASE RED REGRESSION
#
# For canonical persisted Trials, the research catalog database is the
# authoritative ResearchEvidence database. An injected evidence store from
# another SQLite database must never override contradictory canonical
# evidence.
#
# Negative coverage:
#   EXECUTED / REUSED x foreign ACCEPTED evidence vs canonical INCOMPLETE.
#
# Positive control:
#   EXECUTED / REUSED x explicit same-database ACCEPTED evidence store.


def _m94q_fresh_04_completed_trial(
    tmp_path,
    lineage,
):
    from core.research.models.registered_study import (
        EvidenceReusePolicy,
    )

    (
        catalog,
        trial,
        claimed,
        executor,
        _retrieval,
        _calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda _plan: _inputs()
        ),
        evidence_reuse_policy=(
            EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
            if lineage == "REUSED"
            else EvidenceReusePolicy.FORCE_NEW_EXECUTION
        ),
    )

    coordinator = (
        executor.successor_coordinator
    )

    orchestrator = (
        coordinator.orchestrator
    )

    orchestrator._execute_candles = (
        execute_backtest_candles
    )

    def execute_standalone(inputs):
        return coordinator.execute(
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

    if lineage == "REUSED":
        execute_standalone(
            _inputs()
        )

    terminal = executor.execute(
        claimed
    )

    assert (
        terminal.completion_kind.value
        == lineage
    )

    source_attempt_id = (
        terminal.reused_attempt_id
        if lineage == "REUSED"
        else terminal.attempt_id
    )

    assert source_attempt_id is not None

    attempt = catalog.load_run_attempt(
        source_attempt_id
    )

    assert attempt is not None
    assert attempt.evidence_id is not None
    assert (
        attempt.result_artifact_id
        is not None
    )

    return (
        catalog,
        trial,
        orchestrator,
        attempt,
    )


@pytest.mark.parametrize(
    "lineage",
    ("EXECUTED", "REUSED"),
)
def test_m94q_fresh_04_foreign_evidence_store_cannot_override_catalog_database(
    tmp_path,
    lineage,
):
    import sqlite3

    from core.research.models.research_evidence import (
        ResearchEvidenceStatus,
    )
    from core.research.sqlite_research_evidence_store import (
        SQLiteResearchEvidenceStore,
    )
    from core.research.study_aggregation import (
        StudyAggregationError,
        StudyAggregationService,
    )

    (
        catalog,
        trial,
        orchestrator,
        attempt,
    ) = _m94q_fresh_04_completed_trial(
        tmp_path,
        lineage,
    )

    canonical_store = (
        SQLiteResearchEvidenceStore(
            catalog.database_path
        )
    )

    accepted = canonical_store.load(
        attempt.evidence_id
    )

    assert accepted is not None
    assert (
        accepted.status
        is ResearchEvidenceStatus.ACCEPTED
    )

    foreign_store = (
        SQLiteResearchEvidenceStore(
            tmp_path
            / (
                "m94q-fresh-04-"
                + lineage.lower()
                + "-foreign.sqlite3"
            )
        )
    )

    foreign_store.save(
        accepted
    )

    with sqlite3.connect(
        catalog.database_path
    ) as connection:
        connection.execute(
            """
            UPDATE research_evidence
            SET status = ?
            WHERE evidence_id = ?
            """,
            (
                ResearchEvidenceStatus.INCOMPLETE.value,
                accepted.evidence_id,
            ),
        )

    canonical_after = (
        canonical_store.load(
            attempt.evidence_id
        )
    )

    foreign_after = (
        foreign_store.load(
            attempt.evidence_id
        )
    )

    assert canonical_after is not None
    assert foreign_after is not None

    assert (
        canonical_after.status
        is ResearchEvidenceStatus.INCOMPLETE
    )

    assert (
        foreign_after.status
        is ResearchEvidenceStatus.ACCEPTED
    )

    # Existing exact-reuse authority correctly follows the canonical
    # database and must reject the damaged source.
    assert (
        orchestrator.find_exact_reusable_execution(
            attempt.experiment_spec_id
        )
        is None
    )

    # Default aggregation must reject canonical INCOMPLETE evidence.
    with pytest.raises(
        StudyAggregationError,
        match=(
            "evidence|Evidence|"
            "authoritative|result"
        ),
    ):
        StudyAggregationService(
            catalog_store=catalog,
            artifact_store=(
                orchestrator.artifact_store
            ),
        ).aggregate_revision(
            trial.study_revision_id
        )

    # An explicit store for the SAME canonical database must reject too.
    with pytest.raises(
        StudyAggregationError,
        match=(
            "evidence|Evidence|"
            "authoritative|result"
        ),
    ):
        StudyAggregationService(
            catalog_store=catalog,
            artifact_store=(
                orchestrator.artifact_store
            ),
            evidence_store=canonical_store,
        ).aggregate_revision(
            trial.study_revision_id
        )

    # Critical FRESH-04 assertion:
    # a foreign ACCEPTED copy must not override the catalog database.
    with pytest.raises(
        StudyAggregationError,
        match=(
            "evidence|Evidence|"
            "authoritative|database|result"
        ),
    ):
        StudyAggregationService(
            catalog_store=catalog,
            artifact_store=(
                orchestrator.artifact_store
            ),
            evidence_store=foreign_store,
        ).aggregate_revision(
            trial.study_revision_id
        )


@pytest.mark.parametrize(
    "lineage",
    ("EXECUTED", "REUSED"),
)
def test_m94q_fresh_04_same_database_evidence_store_positive_control(
    tmp_path,
    lineage,
):
    from core.research.models.research_evidence import (
        ResearchEvidenceStatus,
    )
    from core.research.sqlite_research_evidence_store import (
        SQLiteResearchEvidenceStore,
    )
    from core.research.study_aggregation import (
        StudyAggregationService,
    )

    (
        catalog,
        trial,
        orchestrator,
        attempt,
    ) = _m94q_fresh_04_completed_trial(
        tmp_path,
        lineage,
    )

    canonical_store = (
        SQLiteResearchEvidenceStore(
            catalog.database_path
        )
    )

    evidence = canonical_store.load(
        attempt.evidence_id
    )

    assert evidence is not None
    assert (
        evidence.status
        is ResearchEvidenceStatus.ACCEPTED
    )

    aggregation = StudyAggregationService(
        catalog_store=catalog,
        artifact_store=(
            orchestrator.artifact_store
        ),
        evidence_store=canonical_store,
    ).aggregate_revision(
        trial.study_revision_id
    )

    assert (
        aggregation.result_bearing_trials
        == 1
    )

# M94Q-REVIEW-20261020-01 PERMANENT RED REGRESSION
#
# Persisted Trial identity fields are immutable registered truth.
# A row retaining its original trial_id must not be executable or
# authoritative if instrument/membership identity has diverged from
# the canonical identity frozen at registration.

_M94Q_REVIEW01_FOREIGN_INSTRUMENT = (
    "NSE-EQ-OUTSIDE-FROZEN-PLAN"
)


def _m94q_review01_corrupt_trial_instrument(
    catalog,
    trial,
):
    with closing(
        sqlite3.connect(
            catalog.database_path
        )
    ) as connection:
        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        cursor = connection.execute(
            """
            UPDATE trials
            SET instrument_id = ?
            WHERE trial_id = ?
            """,
            (
                _M94Q_REVIEW01_FOREIGN_INSTRUMENT,
                trial.trial_id,
            ),
        )

        assert cursor.rowcount == 1

        connection.commit()

    corrupted = catalog.load_trial(
        trial.trial_id
    )

    assert corrupted is not None

    # The corruption deliberately preserves the durable primary
    # identity while changing one field from which that identity was
    # canonically derived.
    assert corrupted.trial_id == trial.trial_id

    assert (
        corrupted.instrument_id
        == _M94Q_REVIEW01_FOREIGN_INSTRUMENT
    )

    assert (
        corrupted.instrument_id
        != trial.instrument_id
    )

    # Membership evidence remains the evidence registered for the
    # original instrument, creating the exact contradiction under
    # review.
    assert (
        corrupted.membership_evidence_fingerprint
        == trial.membership_evidence_fingerprint
    )

    assert (
        corrupted.membership_evidence_artifact_id
        == trial.membership_evidence_artifact_id
    )

    return corrupted


def test_m94q_review_01_registered_population_read_rejects_trial_identity_corruption(
    tmp_path,
):
    (
        catalog,
        trial,
        claimed,
        _executor,
        _retrieval,
        _execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda _plan: _inputs()
        ),
        claim_job=False,
    )

    assert claimed is None

    _m94q_review01_corrupt_trial_instrument(
        catalog,
        trial,
    )

    # Authoritative registered-population reads must validate more
    # than the surviving set of trial_id values.
    with pytest.raises(ValueError):
        catalog.list_registered_trials_for_revision(
            trial.study_revision_id
        )


def test_m94q_review_01_claimed_execution_rejects_trial_identity_corruption_before_retrieval(
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
            lambda _plan: _inputs()
        ),
    )

    assert claimed is not None

    _m94q_review01_corrupt_trial_instrument(
        catalog,
        trial,
    )

    # The immutable registered execution plan must not be reconstructed
    # from corrupted mutable Trial-row fields. Integrity failure must
    # propagate before retrieval, RunAttempt creation or financial
    # execution.
    with pytest.raises(ValueError):
        executor.execute(
            claimed
        )

    assert retrieval.calls == []
    assert execution_calls == []
    assert _attempt_count(catalog) == 0

    persisted_job = (
        catalog.load_research_job(
            claimed.job_id
        )
    )

    assert persisted_job is not None
    assert (
        persisted_job.state
        is ResearchJobState.RUNNING
    )
    assert persisted_job.attempt_id is None
    assert persisted_job.reused_attempt_id is None


@pytest.mark.parametrize(
    "lineage",
    (
        "EXECUTED",
        "REUSED",
    ),
)
def test_m94q_review_01_aggregation_rejects_result_bearing_trial_identity_corruption(
    tmp_path,
    lineage,
):
    from core.research.study_aggregation import (
        StudyAggregationError,
        StudyAggregationService,
    )

    policy = (
        EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED
        if lineage == "REUSED"
        else EvidenceReusePolicy.FORCE_NEW_EXECUTION
    )

    (
        catalog,
        trial,
        claimed,
        executor,
        _retrieval,
        _execution_calls,
    ) = _environment(
        tmp_path,
        execution_input_resolver=(
            lambda _plan: _inputs()
        ),
        evidence_reuse_policy=policy,
    )

    assert claimed is not None

    coordinator = (
        executor.successor_coordinator
    )

    # Use accepted M4 execution so aggregation starts from one valid,
    # result-bearing canonical Trial before corruption.
    coordinator.orchestrator._execute_candles = (
        execute_backtest_candles
    )

    if lineage == "REUSED":
        inputs = _inputs()

        prior = coordinator.execute(
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

        assert prior.attempt_id is not None

    terminal = executor.execute(
        claimed
    )

    assert (
        terminal.completion_kind.value
        == lineage
    )

    aggregation = StudyAggregationService(
        catalog_store=catalog,
        artifact_store=(
            coordinator.orchestrator.artifact_store
        ),
    )

    baseline = aggregation.aggregate_revision(
        trial.study_revision_id
    )

    assert baseline.result_bearing_trials == 1

    _m94q_review01_corrupt_trial_instrument(
        catalog,
        trial,
    )

    # Both EXECUTED and REUSED authoritative reads must fail closed;
    # retained trial_id/population cardinality is not enough.
    with pytest.raises(
        StudyAggregationError
    ):
        aggregation.aggregate_revision(
            trial.study_revision_id
        )

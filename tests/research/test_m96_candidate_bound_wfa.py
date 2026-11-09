from dataclasses import replace
import copy
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
import hashlib
import json
import sqlite3

import pytest

from core.backtest.backtest_engine import BacktestEngine
from core.config.backtest_config import BacktestConfig
from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_retrieval import (
    IncompleteHistoricalCoverageError,
)
from core.research.backtest_financial_configuration import (
    effective_backtest_financial_configuration,
)
from core.research.candidate_wfa_service import (
    CandidateWfaOperationalError,
    CandidateWfaService,
)
from core.research.claimed_trial_execution_inputs import ClaimedTrialExecutionInputs
from core.research.executable_compatibility import (
    ExecutableCompatibilityOperationalError,
    ExecutableCompatibilityResult,
    GitHistoricalExecutableCompatibilityChecker,
)
from core.research.models.dataset import (
    DatasetIdentityV2,
    DatasetProvenance,
    PriceAdjustmentBasis,
)
from core.research.models.dataset_reference import DatasetReference
from core.research.models.qualification import (
    CriterionOutcome,
    EvidenceValidity,
    FixedCandidateRevision,
    QualificationDecision,
    QualificationOutcome,
)
from core.research.models.research_catalog import (
    ComputationKind,
    ResearchArtifactKind,
    RunAttemptState,
)
from core.research.models.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStatus,
)
from core.research.models.qualification_policy import QualificationPolicy
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    Study,
)
from core.research.models.universe import (
    UniverseDefinition,
    UniverseQuality,
    UniverseSnapshot,
)
from core.research.models.wfa_qualification import (
    CANDIDATE_WFA_RESULT_SCHEMA_ID,
    CandidateWfaDecision,
    WfaEvidenceValidity,
    WfaQualificationOutcome,
    candidate_wfa_result_bytes,
    decode_candidate_wfa_result_bytes,
    _validate_account_metrics_against_equity,
    wfa_window_configuration_fingerprint,
    wfa_window_configuration_payload,
)
from core.research.qualification_service import QualificationService
from core.research.registered_study_registration import (
    RegisteredStudyRegistrationService,
)
from core.research.registered_trial_execution_plan import (
    RegisteredTrialExecutionPlan,
    RegisteredTrialExecutionPlanResolver,
)
from core.research.reproducibility import (
    BACKTEST_RESULT_SCHEMA,
    canonical_bytes,
    backtest_configuration_fingerprint_v2,
    build_backtest_run_manifest,
    dataset_fingerprint,
    decode_canonical_bytes,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
    research_artifact_reference,
)
from core.research.sqlite_candidate_wfa_store import SQLiteCandidateWfaStore
from core.research.sqlite_qualification_store import SQLiteQualificationStore
from core.research.sqlite_research_evidence_store import SQLiteResearchEvidenceStore
from core.research.sqlite_research_catalog_store import SQLiteResearchCatalogStore
from core.research.study_aggregation import StudyAggregationService
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.walk_forward.equity_stitcher import EquityStitcher
from core.walk_forward.metrics import WalkForwardMetrics
from core.walk_forward.result import WalkForwardResult
from core.walk_forward.runner import WalkForwardRunner
from core.strategies.strategy_factory import create_registered_research_strategy


UTC = timezone.utc
NOW = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
F = lambda ch: "sha256:" + ch * 64


def _candles(count: int) -> list[Candle]:
    start = datetime(2024, 1, 1, 9, 15, tzinfo=UTC)
    result = []
    for index in range(count):
        cycle = index % 40
        offset = cycle if cycle < 20 else 40 - cycle
        price = 100.0 + float(offset)
        result.append(
            Candle(
                timestamp=start + timedelta(minutes=15 * index),
                open=price,
                high=price + 1.0,
                low=price - 1.0,
                close=price + 0.25,
                volume=1000.0 + index,
            )
        )
    return result


def _tiny_cycle_candles(count: int) -> list[Candle]:
    start = datetime(2024, 1, 1, 9, 15, tzinfo=UTC)
    result = []
    for index in range(count):
        cycle = index % 40
        offset = cycle if cycle < 20 else 40 - cycle
        price = 100.0 + (float(offset) * 0.001)
        result.append(
            Candle(
                timestamp=start + timedelta(minutes=15 * index),
                open=price,
                high=price + 0.01,
                low=price - 0.01,
                close=price + 0.00025,
                volume=1000.0 + index,
            )
        )
    return result


class _FakeCatalog:
    def __init__(self, *, trial, experiment_spec, artifacts):
        self.trial = trial
        self.experiment_spec = experiment_spec
        self.artifacts = dict(artifacts)

    def list_registered_trials_for_revision(self, study_revision_id):
        if study_revision_id != self.trial.study_revision_id:
            raise ValueError("StudyRevision does not exist")
        return (self.trial,)

    def load_experiment_spec(self, experiment_spec_id):
        if experiment_spec_id == self.experiment_spec.experiment_spec_id:
            return self.experiment_spec
        return None

    def load_artifact(self, artifact_id):
        return self.artifacts.get(artifact_id)

    def save_artifact(self, artifact):
        existing = self.artifacts.get(artifact.artifact_id)
        if existing is not None and existing != artifact:
            raise ValueError("artifact conflict")
        self.artifacts[artifact.artifact_id] = artifact
        return artifact

    def load_dataset_reference_identity(self, artifact_id):
        artifact = self.artifacts.get(artifact_id)
        if artifact is None:
            return None
        return self.dataset_identities.get(artifact_id)


class _FakeQualificationStore:
    def __init__(
        self,
        candidate,
        decision,
        dataset_reference_artifact_id=None,
    ):
        self.candidate = candidate
        self.decision = decision
        self.dataset_reference_artifact_id = (
            dataset_reference_artifact_id
        )

    def list_current_eligible_decisions(self, study_revision_id):
        if study_revision_id != self.decision.study_revision_id:
            return ()
        return (self.decision,)

    def load_candidate_revision(self, candidate_revision_id):
        if candidate_revision_id == self.candidate.candidate_revision_id:
            return self.candidate
        return None

    def load_dataset_admission(self, decision_id):
        if decision_id != self.decision.decision_id:
            return None
        return self.dataset_reference_artifact_id


class _FakeWfaStore:
    def __init__(self):
        self.decisions = {}

    def _append_decision(self, decision):
        if decision.decision_id in self.decisions:
            raise ValueError("duplicate")
        self.decisions[decision.decision_id] = decision

    def load_decision(self, decision_id):
        return self.decisions.get(decision_id)


class _FakePlanResolver:
    def __init__(self, plan):
        self.plan = plan

    def resolve(self, trial_id):
        if trial_id != self.plan.trial_id:
            raise ValueError("unknown Trial")
        return self.plan


class _FakeRetrievalService:
    def __init__(self, candles):
        self.candles = tuple(candles)

    def retrieve(self, *args, **kwargs):
        return SimpleNamespace(candles=self.candles)


class _IncompleteRetrievalService:
    def __init__(self, missing_range):
        self.missing_range = missing_range

    def retrieve(self, *args, **kwargs):
        raise IncompleteHistoricalCoverageError([self.missing_range])


class _MutatingRetrievalService:
    def __init__(
        self,
        callback,
        *,
        candles=None,
        missing_range=None,
    ):
        self.callback = callback
        self.candles = None if candles is None else tuple(candles)
        self.missing_range = missing_range

    def retrieve(self, *args, **kwargs):
        self.callback()
        if self.missing_range is not None:
            raise IncompleteHistoricalCoverageError(
                [self.missing_range]
            )
        return SimpleNamespace(candles=self.candles)


class _MappedRetrievalService:
    def __init__(self, candles_by_instrument):
        self.candles_by_instrument = {
            key: tuple(value)
            for key, value in candles_by_instrument.items()
        }

    def retrieve(self, *args, instrument_id, **kwargs):
        return SimpleNamespace(
            candles=self.candles_by_instrument[instrument_id]
        )


class _FakeSoftwareIdentityProvider:
    def resolve(self):
        return SimpleNamespace(
            is_exact=True,
            repository_revision="current-revision",
            worktree_clean=True,
        )


class _UnavailableSoftwareIdentityProvider:
    def resolve(self):
        return SimpleNamespace(
            is_exact=False,
            repository_revision=None,
            worktree_clean=None,
        )


class _DirtySoftwareIdentityProvider:
    def resolve(self):
        return SimpleNamespace(
            is_exact=False,
            repository_revision="current-revision",
            worktree_clean=False,
        )


class _FakeCompatibilityChecker:
    def __init__(self, compatible=True):
        self.compatible = compatible

    def check(self, **kwargs):
        return ExecutableCompatibilityResult(
            compatible=self.compatible,
            reason="fixture",
        )


class _OperationalCompatibilityChecker:
    def check(self, **kwargs):
        raise ExecutableCompatibilityOperationalError(
            "fixture Git infrastructure failure"
        )


def _service_fixture(tmp_path, candle_count):
    candles = _candles(candle_count)
    requested_range = TimeRange(
        candles[0].timestamp,
        candles[-1].timestamp + timedelta(minutes=15),
    )
    context = DatasetContext("AAA", "15m", "UTC")
    runtime_context = RuntimeContext()
    config = BacktestConfig(
        symbol="AAA",
        timeframe="15m",
        strategy_name="sma_crossover",
        start=requested_range.start,
        end=requested_range.end,
        initial_capital=100000.0,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        strategy_params={"fast_period": 10, "slow_period": 30},
        timezone="UTC",
    )
    strategy = create_registered_research_strategy(
        "sma-crossover-v1",
        config,
    )
    dataset_fp = dataset_fingerprint(context, requested_range, candles)
    manifest = build_backtest_run_manifest(
        context,
        requested_range,
        dataset_fp,
        strategy,
        initial_capital=config.initial_capital,
        runtime_context=runtime_context,
    )
    configuration_fp = backtest_configuration_fingerprint_v2(manifest)

    artifact_store = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )
    manifest_artifact = artifact_store.persist_backtest_manifest(
        manifest,
        created_at=NOW,
    )
    identity = DatasetIdentityV2(
        instrument_id="instrument-1",
        requested_range=requested_range,
        timeframe="15m",
        timezone="UTC",
        price_adjustment_basis=PriceAdjustmentBasis.RAW,
        candles=candles,
    )
    reference = DatasetReference(
        identity=identity,
        provenance=DatasetProvenance(
            dataset_id=identity.dataset_id,
            instrument_id="instrument-1",
            requested_range=requested_range,
            timeframe="15m",
            timezone="UTC",
            price_adjustment_basis=PriceAdjustmentBasis.RAW,
            source="fixture",
            coverage=(requested_range,),
            retrieved_at=NOW,
        ),
    )
    dataset_artifact = artifact_store.persist_dataset_reference(
        reference,
        created_at=NOW,
    )

    trial = SimpleNamespace(
        trial_id=F("1"),
        study_revision_id=F("2"),
        experiment_spec_id=F("3"),
        parameter_configuration_fingerprint=F("4"),
    )
    candidate = FixedCandidateRevision(
        candidate_revision_id=F("5"),
        study_revision_id=trial.study_revision_id,
        trial_id=trial.trial_id,
        experiment_spec_id=trial.experiment_spec_id,
        parameter_configuration_fingerprint=(
            trial.parameter_configuration_fingerprint
        ),
        created_at=NOW,
    )
    historical_decision = QualificationDecision(
        decision_id="qualification-1",
        created_at=NOW,
        evaluator_version="m9.5-v1",
        policy_id=F("6"),
        policy_version=1,
        threshold_text="50",
        study_revision_id=trial.study_revision_id,
        trial_id=trial.trial_id,
        candidate_revision_id=candidate.candidate_revision_id,
        attempt_id="attempt-1",
        evidence_id="evidence-1",
        result_artifact_id=F("7"),
        evidence_validity=EvidenceValidity.VALID,
        criterion_outcome=CriterionOutcome.SATISFIED,
        outcome=QualificationOutcome.ELIGIBLE,
        profitable_trade_count=1,
        completed_trade_count=1,
        rate_numerator=100,
        rate_denominator=1,
        reason="fixture eligible",
    )
    evidence = ResearchEvidence(
        evidence_id="evidence-1",
        created_at=NOW,
        status=ResearchEvidenceStatus.ACCEPTED,
        dataset_context=context,
        requested_range=requested_range,
        dataset_fingerprint=dataset_fp,
        configuration_fingerprint=configuration_fp,
        result_fingerprint=F("8"),
        provenance={"computation_kind": "BACKTEST"},
        repository_revision="historical-revision",
        summary="fixture",
        artifact_references=(
            research_artifact_reference(manifest_artifact.artifact_id),
            research_artifact_reference(dataset_artifact.artifact_id),
        ),
    )
    experiment_spec = SimpleNamespace(
        experiment_spec_id=trial.experiment_spec_id,
        computation_kind=ComputationKind.BACKTEST,
        manifest_artifact_id=manifest_artifact.artifact_id,
        dataset_fingerprint=dataset_fp,
        configuration_fingerprint=configuration_fp,
        repository_revision="historical-revision",
    )
    from core.research.models.registered_study import EvidenceReusePolicy

    plan = RegisteredTrialExecutionPlan(
        trial_id=trial.trial_id,
        study_revision_id=trial.study_revision_id,
        instrument_id="instrument-1",
        strategy_procedure_id="sma-crossover-v1",
        timeframe="15m",
        research_range=requested_range,
        trial_range=requested_range,
        timezone="UTC",
        initial_capital=100000.0,
        risk_economic_configuration=(
            effective_backtest_financial_configuration(runtime_context)
        ),
        parameter_configuration={"fast_period": 10, "slow_period": 30},
        data_treatment_basis={"price_adjustment": "raw"},
        repository_revision="historical-revision",
        evidence_reuse_policy=EvidenceReusePolicy.FORCE_NEW_EXECUTION,
    )
    inputs = ClaimedTrialExecutionInputs(
        strategy=strategy,
        config=config,
        runtime_context=runtime_context,
        dataset_context=context,
        provider="provider-x",
        price_adjustment_basis=PriceAdjustmentBasis.RAW,
        strategy_procedure_id="sma-crossover-v1",
        risk_economic_configuration=(
            effective_backtest_financial_configuration(runtime_context)
        ),
        data_treatment_basis={"price_adjustment": "raw"},
    )
    catalog = _FakeCatalog(
        trial=trial,
        experiment_spec=experiment_spec,
        artifacts={
            manifest_artifact.artifact_id: manifest_artifact,
            dataset_artifact.artifact_id: dataset_artifact,
        },
    )
    catalog.dataset_identities = {
        dataset_artifact.artifact_id: identity.dataset_id,
    }
    wfa_store = _FakeWfaStore()
    service = CandidateWfaService(
        catalog_store=catalog,
        artifact_store=artifact_store,
        qualification_store=_FakeQualificationStore(
            candidate,
            historical_decision,
            dataset_reference_artifact_id=dataset_artifact.artifact_id,
        ),
        wfa_store=wfa_store,
        plan_resolver=_FakePlanResolver(plan),
        execution_input_resolver=lambda resolved: inputs,
        retrieval_service=_FakeRetrievalService(candles),
        software_identity_provider=_FakeSoftwareIdentityProvider(),
        executable_compatibility_checker=_FakeCompatibilityChecker(True),
        clock=lambda: NOW,
        decision_id_factory=lambda: "wfa-decision-1",
    )
    service._fixture_evidence = evidence
    service._load_authoritative_historical_evidence = (
        lambda **kwargs: service._fixture_evidence
    )
    return SimpleNamespace(
        service=service,
        catalog=catalog,
        artifact_store=artifact_store,
        wfa_store=wfa_store,
        historical_decision=historical_decision,
        candidate=candidate,
        evidence=evidence,
        dataset_artifact=dataset_artifact,
        candles=candles,
    )


def test_warmup_aware_478_bars_is_insufficient(tmp_path):
    fixture = _service_fixture(tmp_path, 478)

    decisions = fixture.service.evaluate_study_revision(F("2"))

    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.outcome is WfaQualificationOutcome.INSUFFICIENT
    assert decision.evidence_validity is WfaEvidenceValidity.INSUFFICIENT
    assert decision.wfa_verdict is None
    assert decision.result_artifact_id is None


def test_warmup_aware_479_bars_runs_real_singleton_wfa_and_saves_boundaries(
    tmp_path,
):
    fixture = _service_fixture(tmp_path, 479)

    decisions = fixture.service.evaluate_study_revision(F("2"))

    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.outcome in {
        WfaQualificationOutcome.ELIGIBLE,
        WfaQualificationOutcome.REJECTED,
    }
    assert decision.evidence_validity is WfaEvidenceValidity.VALID
    assert decision.wfa_verdict in {"PASS", "FAIL"}
    assert decision.result_artifact_id is not None

    artifact = fixture.catalog.load_artifact(decision.result_artifact_id)
    assert artifact.artifact_kind is ResearchArtifactKind.WFA_RESULT
    assert artifact.schema_id == CANDIDATE_WFA_RESULT_SCHEMA_ID
    payload = decode_canonical_bytes(
        fixture.artifact_store.load_bytes(decision.result_artifact_id),
        schema=CANDIDATE_WFA_RESULT_SCHEMA_ID,
    )
    assert payload["resolved_prehistory_bars"] == 29
    assert len(payload["windows"]) == 1
    window = payload["windows"][0]
    assert window["train_history"]["count"] == 29
    assert window["train_scored"]["count"] == 300
    assert window["test_history"]["count"] == 29
    assert window["test_scored"]["count"] == 150
    assert window["selected_params"] == {"fast_period": 10, "slow_period": 30}
    assert len(window["optimization_evaluations"]) == 1
    assert window["optimization_evaluations"][0]["params"] == {
        "fast_period": 10,
        "slow_period": 30,
    }


def test_dataset_identity_drift_is_invalid_not_wfa_fail(tmp_path):
    fixture = _service_fixture(tmp_path, 479)
    changed = list(fixture.candles)
    last = changed[-1]
    changed[-1] = Candle(
        timestamp=last.timestamp,
        open=last.open,
        high=last.high,
        low=last.low,
        close=last.close + 0.25,
        volume=last.volume,
    )
    fixture.service.retrieval_service = _FakeRetrievalService(changed)

    decision = fixture.service.evaluate_study_revision(F("2"))[0]

    assert decision.outcome is WfaQualificationOutcome.INVALID
    assert decision.evidence_validity is WfaEvidenceValidity.INVALID
    assert decision.wfa_verdict is None
    assert decision.result_artifact_id is None


def test_executable_core_drift_is_invalid_before_wfa(tmp_path):
    fixture = _service_fixture(tmp_path, 479)
    fixture.service.executable_compatibility_checker = (
        _FakeCompatibilityChecker(False)
    )

    decision = fixture.service.evaluate_study_revision(F("2"))[0]

    assert decision.outcome is WfaQualificationOutcome.INVALID
    assert decision.result_artifact_id is None


def test_missing_dataset_reference_identity_binding_is_invalid(tmp_path):
    fixture = _service_fixture(tmp_path, 479)
    fixture.catalog.dataset_identities.clear()

    decision = fixture.service.evaluate_study_revision(F("2"))[0]

    assert decision.outcome is WfaQualificationOutcome.INVALID
    assert decision.result_artifact_id is None


def test_matching_legacy_fingerprint_cannot_hide_successor_dataset_conflict(tmp_path):
    fixture = _service_fixture(tmp_path, 479)
    evidence = fixture.service._fixture_evidence
    original_artifact_id = fixture.dataset_artifact.artifact_id
    original_artifact = fixture.catalog.artifacts[original_artifact_id]
    original_bytes = fixture.artifact_store.load_bytes(original_artifact_id)
    from core.research.models.dataset_reference import decode_dataset_reference_bytes

    original_reference = decode_dataset_reference_bytes(original_bytes)
    conflicting_identity = DatasetIdentityV2(
        instrument_id="different-instrument",
        requested_range=original_reference.identity.requested_range,
        timeframe=original_reference.identity.timeframe,
        timezone=original_reference.identity.timezone,
        price_adjustment_basis=original_reference.identity.price_adjustment_basis,
        candles=original_reference.identity.candles,
    )
    conflicting_reference = DatasetReference(
        identity=conflicting_identity,
        provenance=DatasetProvenance(
            dataset_id=conflicting_identity.dataset_id,
            instrument_id=conflicting_identity.instrument_id,
            requested_range=conflicting_identity.requested_range,
            timeframe=conflicting_identity.timeframe,
            timezone=conflicting_identity.timezone,
            price_adjustment_basis=conflicting_identity.price_adjustment_basis,
            source="fixture-conflict",
            coverage=(conflicting_identity.requested_range,),
            retrieved_at=NOW,
        ),
    )
    conflicting_artifact = fixture.artifact_store.persist_dataset_reference(
        conflicting_reference,
        created_at=NOW,
    )
    fixture.catalog.artifacts[conflicting_artifact.artifact_id] = conflicting_artifact
    fixture.catalog.dataset_identities[conflicting_artifact.artifact_id] = (
        conflicting_identity.dataset_id
    )
    fixture.service._fixture_evidence = replace(
        evidence,
        artifact_references=tuple(
            research_artifact_reference(conflicting_artifact.artifact_id)
            if value == research_artifact_reference(original_artifact.artifact_id)
            else value
            for value in evidence.artifact_references
        ),
    )

    decision = fixture.service.evaluate_study_revision(F("2"))[0]

    assert decision.outcome is WfaQualificationOutcome.INVALID
    assert decision.result_artifact_id is None


def test_historical_configuration_mismatch_is_invalid(tmp_path):
    fixture = _service_fixture(tmp_path, 479)
    fixture.catalog.experiment_spec = replace(
        fixture.catalog.experiment_spec,
        configuration_fingerprint=F("f"),
    ) if hasattr(fixture.catalog.experiment_spec, "__dataclass_fields__") else SimpleNamespace(
        **{
            **fixture.catalog.experiment_spec.__dict__,
            "configuration_fingerprint": F("f"),
        }
    )

    decision = fixture.service.evaluate_study_revision(F("2"))[0]

    assert decision.outcome is WfaQualificationOutcome.INVALID
    assert decision.result_artifact_id is None


@pytest.mark.parametrize("count", [0, 1, 2])
def test_zero_one_many_stage_scope_is_not_single_candidate_limited(
    monkeypatch,
    count,
):
    service = CandidateWfaService.__new__(CandidateWfaService)
    trials = tuple(
        SimpleNamespace(trial_id=f"t{index}")
        for index in range(count)
    )
    decisions = tuple(
        SimpleNamespace(trial_id=trial.trial_id)
        for trial in trials
    )
    service.catalog_store = SimpleNamespace(
        list_registered_trials_for_revision=lambda revision: trials
    )
    service.qualification_store = SimpleNamespace(
        list_current_eligible_decisions=lambda revision: decisions
    )
    seen = []
    monkeypatch.setattr(
        service,
        "_evaluate_one",
        lambda decision, trial: seen.append((decision.trial_id, trial.trial_id))
        or decision.trial_id,
    )

    assert service.evaluate_study_revision("revision") == tuple(
        trial.trial_id for trial in trials
    )
    assert seen == [
        (trial.trial_id, trial.trial_id)
        for trial in trials
    ]

def test_cand010_observed_eligible_decisions_are_not_reresolved(monkeypatch):
    service = CandidateWfaService.__new__(CandidateWfaService)
    trial = SimpleNamespace(trial_id="trial-1")
    observed = SimpleNamespace(
        study_revision_id="revision-1",
        trial_id=trial.trial_id,
        candidate_revision_id=F("1"),
        outcome=QualificationOutcome.ELIGIBLE,
    )
    service.catalog_store = SimpleNamespace(
        list_registered_trials_for_revision=lambda _revision: (trial,),
    )
    service.qualification_store = SimpleNamespace(
        list_current_eligible_decisions=lambda _revision: (_ for _ in ()).throw(
            AssertionError("observed authority must not be re-resolved")
        ),
    )
    seen = []
    monkeypatch.setattr(
        service,
        "_evaluate_one",
        lambda decision, value: seen.append((decision, value)) or "ok",
    )

    assert service.evaluate_study_revision(
        "revision-1",
        observed_eligible_decisions=(observed,),
    ) == ("ok",)
    assert seen == [(observed, trial)]


def test_operational_eligibility_read_failure_creates_no_strategy_decision():
    service = CandidateWfaService.__new__(CandidateWfaService)
    service.catalog_store = SimpleNamespace(
        list_registered_trials_for_revision=lambda revision: ()
    )

    def fail(revision):
        raise sqlite3.OperationalError("database unavailable")

    service.qualification_store = SimpleNamespace(
        list_current_eligible_decisions=fail
    )

    with pytest.raises(CandidateWfaOperationalError):
        service.evaluate_study_revision("revision")


def test_git_compatibility_allows_research_only_change_and_rejects_core_change():
    outputs = iter(
        (
            SimpleNamespace(
                returncode=0,
                stdout="core/research/new_service.py\n",
                stderr="",
            ),
            SimpleNamespace(
                returncode=0,
                stdout=(
                    "core/research/new_service.py\n"
                    "core/strategies/sma_crossover_strategy.py\n"
                ),
                stderr="",
            ),
        )
    )

    def fake_runner(args, root):
        return next(outputs)

    checker = GitHistoricalExecutableCompatibilityChecker(
        git_runner=fake_runner
    )
    accepted = checker.check(
        historical_revision="old",
        current_revision="new",
    )
    rejected = checker.check(
        historical_revision="old",
        current_revision="new",
    )

    assert accepted.compatible is True
    assert rejected.compatible is False
    assert rejected.changed_paths == (
        "core/strategies/sma_crossover_strategy.py",
    )




def _real_registered_fixture(tmp_path, candle_count=479):
    database_path = tmp_path / "research.sqlite3"
    artifact_store = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )
    catalog = SQLiteResearchCatalogStore(database_path)
    qualification_store = SQLiteQualificationStore(database_path)
    wfa_store = SQLiteCandidateWfaStore(
        database_path,
        artifact_store=artifact_store,
        software_identity_provider=_FakeSoftwareIdentityProvider(),
        executable_compatibility_checker=_FakeCompatibilityChecker(True),
    )

    catalog.save_study(
        Study(
            study_id="study-1",
            created_at=NOW,
            display_title="M9.6 integration",
            archived=False,
        )
    )

    candles = _candles(candle_count)
    requested_range = TimeRange(
        candles[0].timestamp,
        candles[-1].timestamp + timedelta(minutes=15),
    )
    definition = UniverseDefinition(
        name="single instrument",
        selection_spec="fixed integration fixture",
        source_reference="fixture",
    )
    snapshot = UniverseSnapshot(
        definition=definition,
        members=("instrument-1",),
        quality=UniverseQuality.CUSTOM_FIXED,
        as_of=NOW,
        provenance_refs=("fixture",),
    )
    runtime_context = RuntimeContext()
    registration = RegisteredStudyRegistrationService(
        catalog_store=catalog,
        artifact_store=artifact_store,
    ).register_study_revision(
        study_id="study-1",
        research_intent="fixed SMA validation",
        strategy_procedure_id="sma-crossover-v1",
        timeframe="15m",
        research_range=requested_range,
        timezone="UTC",
        initial_capital=100000.0,
        risk_economic_configuration=(
            effective_backtest_financial_configuration(runtime_context)
        ),
        parameter_variants=(
            {"fast_period": 10, "slow_period": 30},
        ),
        universe_definition=definition,
        universe_snapshots=(snapshot,),
        require_point_in_time=False,
        data_treatment_basis={"price_adjustment": "raw"},
        repository_revision="historical-revision",
        evidence_reuse_policy=EvidenceReusePolicy.FORCE_NEW_EXECUTION,
        registered_at=NOW,
    )
    trial = registration.trials[0]

    context = DatasetContext("AAA", "15m", "UTC")
    config = BacktestConfig(
        symbol="AAA",
        timeframe="15m",
        strategy_name="sma_crossover",
        start=trial.membership_episode_start,
        end=trial.membership_episode_end,
        initial_capital=100000.0,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        strategy_params={"fast_period": 10, "slow_period": 30},
        timezone="UTC",
    )
    strategy = create_registered_research_strategy(
        "sma-crossover-v1",
        config,
    )
    dataset_fp = dataset_fingerprint(
        context,
        requested_range,
        candles,
    )
    manifest = build_backtest_run_manifest(
        context,
        requested_range,
        dataset_fp,
        strategy,
        initial_capital=config.initial_capital,
        runtime_context=runtime_context,
    )
    manifest_artifact = artifact_store.persist_backtest_manifest(
        manifest,
        created_at=NOW,
    )
    catalog.save_artifact(manifest_artifact)
    experiment_spec = catalog.resolve_experiment_spec(
        computation_kind=ComputationKind.BACKTEST,
        manifest_artifact_id=manifest_artifact.artifact_id,
        dataset_fingerprint=dataset_fp,
        configuration_fingerprint=(
            backtest_configuration_fingerprint_v2(manifest)
        ),
        repository_revision="historical-revision",
        created_at=NOW,
    )

    identity = DatasetIdentityV2(
        instrument_id="instrument-1",
        requested_range=requested_range,
        timeframe="15m",
        timezone="UTC",
        price_adjustment_basis=PriceAdjustmentBasis.RAW,
        candles=candles,
    )
    reference = DatasetReference(
        identity=identity,
        provenance=DatasetProvenance(
            dataset_id=identity.dataset_id,
            instrument_id="instrument-1",
            requested_range=requested_range,
            timeframe="15m",
            timezone="UTC",
            price_adjustment_basis=PriceAdjustmentBasis.RAW,
            source="fixture",
            coverage=(requested_range,),
            retrieved_at=NOW,
        ),
    )
    dataset_artifact = artifact_store.persist_dataset_reference(
        reference,
        created_at=NOW,
    )
    catalog.save_dataset_reference_artifact(
        dataset_artifact,
        reference,
    )

    historical_result = BacktestEngine(
        strategy=create_registered_research_strategy(
            "sma-crossover-v1",
            config,
        ),
        initial_capital=config.initial_capital,
        runtime_context=runtime_context,
        dataset_context=context,
    ).run(candles)
    assert historical_result.trades

    historical_result_artifact = artifact_store.persist_backtest_result(
        historical_result,
        created_at=NOW + timedelta(seconds=4),
    )
    evidence = ResearchEvidence(
        evidence_id="integration-evidence",
        created_at=NOW + timedelta(seconds=4),
        status=ResearchEvidenceStatus.ACCEPTED,
        dataset_context=context,
        requested_range=requested_range,
        dataset_fingerprint=dataset_fp,
        configuration_fingerprint=experiment_spec.configuration_fingerprint,
        result_fingerprint=historical_result_artifact.artifact_id,
        provenance={"computation_kind": "BACKTEST"},
        repository_revision="historical-revision",
        summary="integration fixture",
        artifact_references=(
            research_artifact_reference(manifest_artifact.artifact_id),
            research_artifact_reference(dataset_artifact.artifact_id),
            research_artifact_reference(
                historical_result_artifact.artifact_id
            ),
        ),
    )

    catalog.start_study_revision_batch(
        registration.revision.study_revision_id,
        NOW + timedelta(seconds=1),
    )
    job = catalog.claim_next_research_job(
        registration.revision.study_revision_id,
        "worker-1",
        NOW + timedelta(seconds=2),
        max_running_jobs=1,
    )
    assert job is not None
    bound_trial, _, attempt = (
        catalog._bind_trial_spec_create_attempt_for_running_job(
            job_id=job.job_id,
            experiment_spec_id=experiment_spec.experiment_spec_id,
            attempt_created_at=NOW + timedelta(seconds=3),
        )
    )
    assert bound_trial.experiment_spec_id == experiment_spec.experiment_spec_id

    catalog._terminalize_running_job_attempt_with_evidence(
        attempt.attempt_id,
        job_id=job.job_id,
        state=RunAttemptState.SUCCEEDED,
        terminal_at=NOW + timedelta(seconds=4),
        evidence=evidence,
        runtime_session_id=historical_result.session_id,
        result_artifact=historical_result_artifact,
    )

    verified = StudyAggregationService(
        catalog_store=catalog,
        artifact_store=artifact_store,
    ).load_verified_trial_backtest(trial.trial_id)
    assert verified.result_artifact_id == historical_result_artifact.artifact_id

    policy = QualificationPolicy(1, Decimal("0"))
    qualification_store.register_policy(policy, created_at=NOW)
    qualification_store.activate_policy(
        policy.policy_id,
        activated_at=NOW,
    )
    historical_decision = QualificationService(
        catalog_store=catalog,
        artifact_store=artifact_store,
        qualification_store=qualification_store,
    ).evaluate_selected_trial(
        trial.trial_id,
        evaluated_at=NOW + timedelta(seconds=5),
    )
    assert historical_decision.outcome is QualificationOutcome.ELIGIBLE
    assert historical_decision.result_artifact_id == historical_result_artifact.artifact_id
    assert historical_decision.evidence_id == evidence.evidence_id
    assert historical_decision.attempt_id == attempt.attempt_id

    trial = catalog.load_trial(trial.trial_id)
    assert trial is not None
    inputs = ClaimedTrialExecutionInputs(
        strategy=strategy,
        config=config,
        runtime_context=runtime_context,
        dataset_context=context,
        provider="provider-x",
        price_adjustment_basis=PriceAdjustmentBasis.RAW,
        strategy_procedure_id="sma-crossover-v1",
        risk_economic_configuration=(
            effective_backtest_financial_configuration(runtime_context)
        ),
        data_treatment_basis={"price_adjustment": "raw"},
    )
    service = CandidateWfaService(
        catalog_store=catalog,
        artifact_store=artifact_store,
        qualification_store=qualification_store,
        wfa_store=wfa_store,
        plan_resolver=RegisteredTrialExecutionPlanResolver(
            catalog_store=catalog,
            artifact_store=artifact_store,
        ),
        execution_input_resolver=lambda resolved: inputs,
        retrieval_service=_FakeRetrievalService(candles),
        software_identity_provider=_FakeSoftwareIdentityProvider(),
        executable_compatibility_checker=_FakeCompatibilityChecker(True),
        clock=lambda: NOW + timedelta(seconds=6),
        decision_id_factory=lambda: "integration-wfa-decision",
    )
    return SimpleNamespace(
        database_path=database_path,
        artifact_store=artifact_store,
        catalog=catalog,
        qualification_store=qualification_store,
        wfa_store=wfa_store,
        service=service,
        registration=registration,
        trial=trial,
        candles=candles,
        context=context,
        dataset_artifact=dataset_artifact,
        dataset_id=identity.dataset_id,
        dataset_fingerprint=dataset_fp,
        experiment_spec=experiment_spec,
        historical_result_artifact=historical_result_artifact,
        evidence=evidence,
        historical_decision=historical_decision,
    )


def _completed_real_wfa_fixture(tmp_path):
    fixture = _real_registered_fixture(tmp_path)
    decision = fixture.service.evaluate_study_revision(
        fixture.registration.revision.study_revision_id
    )[0]
    assert decision.result_artifact_id is not None
    assert decision.wfa_verdict in {"PASS", "FAIL"}
    return fixture, decision


def _register_second_real_candidate(fixture):
    catalog = fixture.catalog
    artifact_store = fixture.artifact_store
    qualification_store = fixture.qualification_store

    catalog.save_study(
        Study(
            study_id="study-2",
            created_at=NOW,
            display_title="M9.6 second registered candidate",
            archived=False,
        )
    )

    requested_range = TimeRange(
        fixture.trial.membership_episode_start,
        fixture.trial.membership_episode_end,
    )
    definition = UniverseDefinition(
        name="single instrument second candidate",
        selection_spec="fixed second integration fixture",
        source_reference="fixture-second",
    )
    snapshot = UniverseSnapshot(
        definition=definition,
        members=("instrument-1",),
        quality=UniverseQuality.CUSTOM_FIXED,
        as_of=NOW,
        provenance_refs=("fixture-second",),
    )
    runtime_context = RuntimeContext()
    registration = RegisteredStudyRegistrationService(
        catalog_store=catalog,
        artifact_store=artifact_store,
    ).register_study_revision(
        study_id="study-2",
        research_intent="second fixed SMA validation",
        strategy_procedure_id="sma-crossover-v1",
        timeframe="15m",
        research_range=requested_range,
        timezone="UTC",
        initial_capital=100000.0,
        risk_economic_configuration=(
            effective_backtest_financial_configuration(runtime_context)
        ),
        parameter_variants=(
            {"fast_period": 10, "slow_period": 30},
        ),
        universe_definition=definition,
        universe_snapshots=(snapshot,),
        require_point_in_time=False,
        data_treatment_basis={"price_adjustment": "raw"},
        repository_revision="historical-revision",
        evidence_reuse_policy=EvidenceReusePolicy.FORCE_NEW_EXECUTION,
        registered_at=NOW,
    )
    trial = registration.trials[0]

    config = BacktestConfig(
        symbol="AAA",
        timeframe="15m",
        strategy_name="sma_crossover",
        start=trial.membership_episode_start,
        end=trial.membership_episode_end,
        initial_capital=100000.0,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        strategy_params={"fast_period": 10, "slow_period": 30},
        timezone="UTC",
    )
    historical_result = BacktestEngine(
        strategy=create_registered_research_strategy(
            "sma-crossover-v1",
            config,
        ),
        initial_capital=config.initial_capital,
        runtime_context=runtime_context,
        dataset_context=fixture.context,
    ).run(fixture.candles)
    assert historical_result.trades

    historical_result_artifact = artifact_store.persist_backtest_result(
        historical_result,
        created_at=NOW + timedelta(seconds=14),
    )
    evidence = ResearchEvidence(
        evidence_id="integration-evidence-2",
        created_at=NOW + timedelta(seconds=14),
        status=ResearchEvidenceStatus.ACCEPTED,
        dataset_context=fixture.context,
        requested_range=requested_range,
        dataset_fingerprint=fixture.dataset_fingerprint,
        configuration_fingerprint=(
            fixture.experiment_spec.configuration_fingerprint
        ),
        result_fingerprint=historical_result_artifact.artifact_id,
        provenance={"computation_kind": "BACKTEST"},
        repository_revision="historical-revision",
        summary="second integration fixture",
        artifact_references=(
            research_artifact_reference(
                fixture.experiment_spec.manifest_artifact_id
            ),
            research_artifact_reference(
                fixture.dataset_artifact.artifact_id
            ),
            research_artifact_reference(
                historical_result_artifact.artifact_id
            ),
        ),
    )

    catalog.start_study_revision_batch(
        registration.revision.study_revision_id,
        NOW + timedelta(seconds=11),
    )
    job = catalog.claim_next_research_job(
        registration.revision.study_revision_id,
        "worker-2",
        NOW + timedelta(seconds=12),
        max_running_jobs=1,
    )
    assert job is not None
    _, _, attempt = catalog._bind_trial_spec_create_attempt_for_running_job(
        job_id=job.job_id,
        experiment_spec_id=fixture.experiment_spec.experiment_spec_id,
        attempt_created_at=NOW + timedelta(seconds=13),
    )
    catalog._terminalize_running_job_attempt_with_evidence(
        attempt.attempt_id,
        job_id=job.job_id,
        state=RunAttemptState.SUCCEEDED,
        terminal_at=NOW + timedelta(seconds=14),
        evidence=evidence,
        runtime_session_id=historical_result.session_id,
        result_artifact=historical_result_artifact,
    )

    historical_decision = QualificationService(
        catalog_store=catalog,
        artifact_store=artifact_store,
        qualification_store=qualification_store,
    ).evaluate_selected_trial(
        trial.trial_id,
        evaluated_at=NOW + timedelta(seconds=15),
    )
    assert historical_decision.outcome is QualificationOutcome.ELIGIBLE
    candidate = qualification_store.load_candidate_revision(
        historical_decision.candidate_revision_id
    )
    assert candidate is not None

    return SimpleNamespace(
        registration=registration,
        trial=trial,
        historical_decision=historical_decision,
        candidate=candidate,
    )



def _load_completed_wfa_payload(fixture, decision):
    return decode_candidate_wfa_result_bytes(
        fixture.artifact_store.load_bytes(
            decision.result_artifact_id
        )
    )


def _persist_wfa_payload(fixture, payload, *, created_at):
    raw = canonical_bytes(
        payload,
        schema=CANDIDATE_WFA_RESULT_SCHEMA_ID,
    )
    # This helper is used only where the payload should remain a valid
    # candidate-WFA document. Invalid-decoder tests encode directly.
    decode_candidate_wfa_result_bytes(raw)
    artifact = fixture.artifact_store.persist_bytes(
        raw,
        artifact_kind=ResearchArtifactKind.WFA_RESULT,
        schema_id=CANDIDATE_WFA_RESULT_SCHEMA_ID,
        created_at=created_at,
    )
    fixture.catalog.save_artifact(artifact)
    return artifact


def _opposite_m5_payload(payload):
    payload = copy.deepcopy(payload)
    make_pass = payload["verdict"] == "FAIL"

    for window in payload["windows"]:
        metrics = window["test_metrics"]
        metrics["account_return_pct"] = 1.0 if make_pass else -1.0
        metrics["account_pnl"] = 1000.0 if make_pass else -1000.0
        metrics["max_equity_drawdown_pct"] = 0.0 if make_pass else 1.0
        metrics["profitable"] = make_pass

    aggregate = WalkForwardMetrics.aggregate(
        [window["test_metrics"] for window in payload["windows"]]
    )
    aggregate["avg_optimization_stability"] = round(
        sum(
            window["optimization_stability_score"]
            for window in payload["windows"]
        )
        / len(payload["windows"]),
        4,
    )
    payload["aggregated_metrics"] = aggregate

    replay_windows = []
    target = 101000.0 if make_pass else 99000.0
    for window in payload["windows"]:
        timestamps = [
            point[0]
            for point in window["oos_equity_curve"]
        ]
        if len(timestamps) == 1:
            equities = [target]
        else:
            equities = [
                100000.0
                + (target - 100000.0) * index / (len(timestamps) - 1)
                for index in range(len(timestamps))
            ]
        window["oos_equity_curve"] = list(
            zip(timestamps, equities)
        )
        replay_windows.append(
            SimpleNamespace(
                window_index=window["window_index"],
                backtest_result=SimpleNamespace(
                    equity_curve=window["oos_equity_curve"]
                ),
            )
        )

    (
        stitched_curve,
        exact_stitched_curve,
    ) = EquityStitcher.stitch_with_exact(replay_windows)
    payload["stitched_equity_curve"] = stitched_curve
    payload["stitched_equity_metrics"] = (
        WalkForwardMetrics.compute_stitched_equity_metrics(
            exact_stitched_curve
        )
    )
    payload["verdict"] = "PASS" if make_pass else "FAIL"
    return payload

def test_real_registered_lineage_to_real_singleton_wfa_integration(tmp_path):
    fixture = _real_registered_fixture(tmp_path)

    decisions = fixture.service.evaluate_study_revision(
        fixture.registration.revision.study_revision_id
    )

    assert len(decisions) == 1
    decision = decisions[0]
    assert decision.evidence_validity is WfaEvidenceValidity.VALID
    assert decision.outcome in {
        WfaQualificationOutcome.ELIGIBLE,
        WfaQualificationOutcome.REJECTED,
    }
    assert fixture.wfa_store.load_decision(decision.decision_id) == decision
    artifact = fixture.catalog.load_artifact(decision.result_artifact_id)
    assert artifact is not None
    assert artifact.artifact_kind is ResearchArtifactKind.WFA_RESULT


@pytest.mark.parametrize("candle_count", [779, 1000])
def test_real_m5_longer_results_preserve_exact_verdict_precision(
    tmp_path,
    candle_count,
):
    fixture = _real_registered_fixture(
        tmp_path / str(candle_count),
        candle_count=candle_count,
    )

    decision = fixture.service.evaluate_study_revision(
        fixture.registration.revision.study_revision_id
    )[0]

    assert decision.evidence_validity is WfaEvidenceValidity.VALID
    assert decision.wfa_verdict == "FAIL"
    assert decision.outcome is WfaQualificationOutcome.REJECTED
    payload = _load_completed_wfa_payload(fixture, decision)
    assert payload["verdict"] == "FAIL"


def test_foreign_evidence_store_cannot_override_authoritative_database(tmp_path):
    fixture = _real_registered_fixture(tmp_path)
    foreign_evidence = replace(
        fixture.evidence,
        status=ResearchEvidenceStatus.ACCEPTED,
    )
    fixture.service.evidence_store = SimpleNamespace(
        load=lambda evidence_id: foreign_evidence
    )

    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            "UPDATE research_evidence SET status = 'FAILED' WHERE evidence_id = ?",
            (fixture.evidence.evidence_id,),
        )
        connection.commit()

    decision = fixture.service.evaluate_study_revision(
        fixture.registration.revision.study_revision_id
    )[0]

    assert decision.outcome is WfaQualificationOutcome.INVALID
    assert decision.result_artifact_id is None


def test_historical_decision_result_mismatch_is_invalid(tmp_path):
    fixture = _real_registered_fixture(tmp_path)

    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            """
            UPDATE qualification_decisions
            SET result_artifact_id = ?
            WHERE decision_id = ?
            """,
            (F("9"), fixture.historical_decision.decision_id),
        )
        connection.commit()

    decision = fixture.service.evaluate_study_revision(
        fixture.registration.revision.study_revision_id
    )[0]

    assert decision.outcome is WfaQualificationOutcome.INVALID
    assert decision.result_artifact_id is None


def _seed_minimal_wfa_lineage(path):
    # Seed only the rows needed by SQLiteCandidateWfaStore lineage checks.
    policy = QualificationPolicy(1, Decimal("50"))
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            "INSERT INTO studies VALUES (?, ?, ?, ?)",
            ("study-1", NOW.isoformat(), "fixture", 0),
        )
        connection.execute(
            """
            INSERT INTO research_artifacts
            (artifact_id, artifact_kind, schema_id, relative_path, byte_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (F("a"), "STUDY_REVISION_PLAN", "plan", "sha256/aa/a.json", 1, NOW.isoformat()),
        )
        connection.execute(
            """
            INSERT INTO study_revisions
            (study_revision_id, identity_schema, study_id, revision_number,
             plan_artifact_id, repository_revision, evidence_reuse_policy,
             registered_at, initial_batch_started_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (F("2"), "revision", "study-1", 1, F("a"), "rev", "FORCE_NEW_EXECUTION", NOW.isoformat(), None),
        )
        connection.execute(
            """
            INSERT INTO research_artifacts
            (artifact_id, artifact_kind, schema_id, relative_path, byte_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (F("b"), "TRIAL_MEMBERSHIP_EVIDENCE", "membership", "sha256/bb/b.json", 1, NOW.isoformat()),
        )
        connection.execute(
            """
            INSERT INTO experiment_specs
            (experiment_spec_id, identity_schema, computation_kind, manifest_artifact_id,
             dataset_fingerprint, configuration_fingerprint, repository_revision, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (F("3"), "spec", "BACKTEST", F("a"), F("c"), F("d"), "rev", NOW.isoformat()),
        )
        connection.execute(
            """
            INSERT INTO trials
            (trial_id, identity_schema, study_revision_id, instrument_id,
             membership_episode_start, membership_episode_end,
             membership_evidence_fingerprint, membership_evidence_artifact_id,
             parameter_configuration_fingerprint, registered_at, experiment_spec_id,
             disposition, disposition_at, reused_attempt_id,
             failure_classification, failure_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (F("1"), "trial", F("2"), "instrument-1", NOW.isoformat(), (NOW + timedelta(days=1)).isoformat(), F("b"), F("b"), F("4"), NOW.isoformat(), F("3"), "EXECUTED", NOW.isoformat(), None, None, None),
        )
        connection.execute(
            """
            INSERT INTO fixed_candidate_revisions
            (candidate_revision_id, study_revision_id, trial_id, experiment_spec_id,
             parameter_configuration_fingerprint, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (F("5"), F("2"), F("1"), F("3"), F("4"), NOW.isoformat()),
        )
        connection.execute(
            "INSERT INTO qualification_policies VALUES (?, ?, ?, ?)",
            (policy.policy_id, 1, "50", NOW.isoformat()),
        )
        connection.execute(
            "INSERT INTO qualification_policy_activations (policy_id, activated_at) VALUES (?, ?)",
            (policy.policy_id, NOW.isoformat()),
        )
        connection.execute(
            """
            INSERT INTO qualification_decisions
            (decision_id, created_at, evaluator_version, policy_id, policy_version,
             threshold_text, study_revision_id, trial_id, candidate_revision_id,
             attempt_id, evidence_id, result_artifact_id, evidence_validity,
             criterion_outcome, outcome, profitable_trade_count,
             completed_trade_count, rate_numerator, rate_denominator, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("qualification-1", NOW.isoformat(), "m9.5-v1", policy.policy_id, 1, "50", F("2"), F("1"), F("5"), None, None, None, "VALID", "SATISFIED", "ELIGIBLE", 1, 1, 100, 1, "eligible"),
        )
        connection.commit()


def test_candidate_wfa_store_has_no_public_append_decision_api(tmp_path):
    fixture = _real_registered_fixture(tmp_path)
    assert not hasattr(fixture.wfa_store, "append_decision")


def test_sqlite_wfa_decision_enforces_append_only_historical_lineage(tmp_path):
    path = tmp_path / "research.sqlite3"
    artifact_store = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )
    store = SQLiteCandidateWfaStore(
        path,
        artifact_store=artifact_store,
    )
    _seed_minimal_wfa_lineage(path)
    decision = CandidateWfaDecision(
        decision_id="wfa-1",
        created_at=NOW,
        evaluator_version="m9.6-v1",
        study_revision_id=F("2"),
        trial_id=F("1"),
        candidate_revision_id=F("5"),
        historical_qualification_decision_id="qualification-1",
        evaluator_repository_revision=None,
        wfa_configuration_fingerprint=F("e"),
        evidence_validity=WfaEvidenceValidity.INVALID,
        outcome=WfaQualificationOutcome.INVALID,
        reason="fixture invalid",
    )

    store._append_decision(decision)
    assert store.load_decision("wfa-1") == decision
    assert store.load_current_decision(F("5")) == decision

    with pytest.raises(ValueError, match="append-only"):
        store._append_decision(decision)


def test_sqlite_wfa_decision_rejects_wrong_result_artifact_kind(tmp_path):
    fixture, valid_decision = _completed_real_wfa_fixture(tmp_path)

    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """
            INSERT INTO research_artifacts
            (artifact_id, artifact_kind, schema_id, relative_path, byte_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                F("e"),
                "BACKTEST_RESULT",
                "wrong-schema",
                "sha256/ee/e.json",
                1,
                NOW.isoformat(),
            ),
        )
        connection.commit()

    decision = replace(
        valid_decision,
        decision_id="wfa-wrong-result-kind",
        result_artifact_id=F("e"),
        reason="wrong result artifact kind",
    )

    with pytest.raises(ValueError, match="wrong artifact kind/schema"):
        fixture.wfa_store._append_decision(decision)


def test_sqlite_wfa_decision_rejects_missing_physical_result_bytes(tmp_path):
    fixture, valid_decision = _completed_real_wfa_fixture(tmp_path)

    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """
            INSERT INTO research_artifacts
            (artifact_id, artifact_kind, schema_id, relative_path, byte_count, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                F("e"),
                ResearchArtifactKind.WFA_RESULT.value,
                CANDIDATE_WFA_RESULT_SCHEMA_ID,
                "sha256/ee/e.json",
                1,
                NOW.isoformat(),
            ),
        )
        connection.commit()

    decision = replace(
        valid_decision,
        decision_id="wfa-missing-result-bytes",
        result_artifact_id=F("e"),
        reason="missing result bytes",
    )

    with pytest.raises(ValueError, match="bytes are unavailable or invalid"):
        fixture.wfa_store._append_decision(decision)


def test_sqlite_wfa_decision_rejects_corrupt_result_bytes(tmp_path):
    fixture, valid_decision = _completed_real_wfa_fixture(tmp_path)
    artifact = fixture.catalog.load_artifact(
        valid_decision.result_artifact_id
    )
    assert artifact is not None
    result_path = fixture.artifact_store.root_directory.joinpath(
        *artifact.relative_path.split("/")
    )
    result_path.write_bytes(b"corrupt")

    decision = replace(
        valid_decision,
        decision_id="wfa-corrupt-result-bytes",
        reason="corrupt result bytes",
    )

    with pytest.raises(ValueError, match="bytes are unavailable or invalid"):
        fixture.wfa_store._append_decision(decision)


def test_sqlite_wfa_decision_rejects_result_from_another_candidate(tmp_path):
    fixture, first_decision = _completed_real_wfa_fixture(tmp_path)
    second = _register_second_real_candidate(fixture)

    decision = CandidateWfaDecision(
        decision_id="wfa-cross-candidate-result",
        created_at=NOW + timedelta(seconds=16),
        evaluator_version="m9.6-v1",
        study_revision_id=second.historical_decision.study_revision_id,
        trial_id=second.historical_decision.trial_id,
        candidate_revision_id=second.candidate.candidate_revision_id,
        historical_qualification_decision_id=(
            second.historical_decision.decision_id
        ),
        evaluator_repository_revision=(
            first_decision.evaluator_repository_revision
        ),
        dataset_reference_artifact_id=(
            first_decision.dataset_reference_artifact_id
        ),
        dataset_id=first_decision.dataset_id,
        dataset_fingerprint=first_decision.dataset_fingerprint,
        wfa_configuration_fingerprint=(
            first_decision.wfa_configuration_fingerprint
        ),
        result_artifact_id=first_decision.result_artifact_id,
        evidence_validity=WfaEvidenceValidity.VALID,
        wfa_verdict=first_decision.wfa_verdict,
        outcome=first_decision.outcome,
        reason="cross-candidate result",
    )

    with pytest.raises(ValueError, match="result artifact authority mismatch"):
        fixture.wfa_store._append_decision(decision)


def test_internal_wfa_writer_rejects_changed_registered_strategy_parameters(
    tmp_path,
):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    payload = _load_completed_wfa_payload(fixture, decision)
    payload["strategy_parameters"] = {
        "fast_period": 20,
        "slow_period": 50,
    }
    for window in payload["windows"]:
        window["selected_params"] = dict(payload["strategy_parameters"])
        window["optimization_evaluations"][0]["params"] = dict(
            payload["strategy_parameters"]
        )

    artifact = _persist_wfa_payload(
        fixture,
        payload,
        created_at=NOW + timedelta(seconds=20),
    )
    changed = replace(
        decision,
        decision_id="wfa-changed-registered-parameters",
        result_artifact_id=artifact.artifact_id,
        reason="changed registered parameters",
    )

    with pytest.raises(
        ValueError,
        match="authority mismatch: strategy_parameters",
    ):
        fixture.wfa_store._append_decision(changed)


def test_internal_wfa_writer_rejects_unrelated_legacy_dataset_fingerprint(
    tmp_path,
):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    payload = _load_completed_wfa_payload(fixture, decision)
    payload["dataset_fingerprint"] = F("f")
    artifact = _persist_wfa_payload(
        fixture,
        payload,
        created_at=NOW + timedelta(seconds=21),
    )
    changed = replace(
        decision,
        decision_id="wfa-unrelated-legacy-dataset",
        dataset_fingerprint=F("f"),
        result_artifact_id=artifact.artifact_id,
        reason="unrelated legacy dataset fingerprint",
    )

    with pytest.raises(ValueError):
        fixture.wfa_store._append_decision(changed)


def test_internal_wfa_writer_rejects_different_dataset_reference_candles(
    tmp_path,
):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    candles = list(fixture.candles)
    candles[0] = replace(
        candles[0],
        close=candles[0].close + 0.1,
    )
    requested_range = TimeRange(
        fixture.trial.membership_episode_start,
        fixture.trial.membership_episode_end,
    )
    identity = DatasetIdentityV2(
        instrument_id=fixture.trial.instrument_id,
        requested_range=requested_range,
        timeframe="15m",
        timezone="UTC",
        price_adjustment_basis=PriceAdjustmentBasis.RAW,
        candles=candles,
    )
    reference = DatasetReference(
        identity=identity,
        provenance=DatasetProvenance(
            dataset_id=identity.dataset_id,
            instrument_id=identity.instrument_id,
            requested_range=identity.requested_range,
            timeframe=identity.timeframe,
            timezone=identity.timezone,
            price_adjustment_basis=identity.price_adjustment_basis,
            source="different-valid-fixture",
            coverage=(identity.requested_range,),
            retrieved_at=NOW,
        ),
    )
    dataset_artifact = fixture.artifact_store.persist_dataset_reference(
        reference,
        created_at=NOW + timedelta(seconds=22),
    )
    fixture.catalog.save_dataset_reference_artifact(
        dataset_artifact,
        reference,
    )

    payload = _load_completed_wfa_payload(fixture, decision)
    payload["source_dataset_reference_artifact_id"] = (
        dataset_artifact.artifact_id
    )
    payload["source_dataset_id"] = identity.dataset_id
    result_artifact = _persist_wfa_payload(
        fixture,
        payload,
        created_at=NOW + timedelta(seconds=22),
    )
    changed = replace(
        decision,
        decision_id="wfa-different-dataset-reference",
        dataset_reference_artifact_id=dataset_artifact.artifact_id,
        dataset_id=identity.dataset_id,
        result_artifact_id=result_artifact.artifact_id,
        reason="different DatasetReference candles",
    )

    with pytest.raises(ValueError):
        fixture.wfa_store._append_decision(changed)


def test_internal_wfa_writer_rejects_shifted_window_timestamps(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    payload = _load_completed_wfa_payload(fixture, decision)
    shift = timedelta(days=400)

    for window in payload["windows"]:
        for field_name in (
            "train_history",
            "train_scored",
            "test_history",
            "test_scored",
        ):
            bounds = window[field_name]
            if bounds["first_timestamp"] is not None:
                bounds["first_timestamp"] += shift
                bounds["last_timestamp"] += shift
        window["oos_equity_curve"] = [
            (timestamp + shift, equity)
            for timestamp, equity in window["oos_equity_curve"]
        ]

    payload["stitched_equity_curve"] = [
        (timestamp + shift, equity)
        for timestamp, equity in payload["stitched_equity_curve"]
    ]
    artifact = _persist_wfa_payload(
        fixture,
        payload,
        created_at=NOW + timedelta(seconds=23),
    )
    changed = replace(
        decision,
        decision_id="wfa-shifted-window-timestamps",
        result_artifact_id=artifact.artifact_id,
        reason="shifted window timestamps",
    )

    with pytest.raises(
        ValueError,
        match="result windows do not match admitted M5 generation",
    ):
        fixture.wfa_store._append_decision(changed)


def test_internal_wfa_writer_rejects_false_zero_prehistory(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    payload = _load_completed_wfa_payload(fixture, decision)
    payload["resolved_prehistory_bars"] = 0
    for window in payload["windows"]:
        window["train_history"] = {
            "count": 0,
            "first_timestamp": None,
            "last_timestamp": None,
        }
        window["test_history"] = {
            "count": 0,
            "first_timestamp": None,
            "last_timestamp": None,
        }

    artifact = _persist_wfa_payload(
        fixture,
        payload,
        created_at=NOW + timedelta(seconds=24),
    )
    changed = replace(
        decision,
        decision_id="wfa-false-zero-prehistory",
        result_artifact_id=artifact.artifact_id,
        reason="false zero prehistory",
    )

    with pytest.raises(
        ValueError,
        match="result windows do not match admitted M5 generation",
    ):
        fixture.wfa_store._append_decision(changed)


def test_internal_wfa_writer_rejects_missing_historical_result_file(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    fixture.artifact_store._absolute_path(
        fixture.historical_result_artifact.artifact_id
    ).unlink()
    changed = replace(
        decision,
        decision_id="wfa-missing-historical-result-file",
        reason="historical result file removed",
    )

    with pytest.raises(
        ValueError,
        match="requires currently verified historical Backtest admission",
    ):
        fixture.wfa_store._append_decision(changed)


def test_internal_wfa_writer_rejects_missing_historical_evidence_references(
    tmp_path,
):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            "UPDATE research_evidence SET artifact_references = '[]' "
            "WHERE evidence_id = ?",
            (fixture.evidence.evidence_id,),
        )
        connection.commit()

    changed = replace(
        decision,
        decision_id="wfa-missing-historical-evidence-references",
        reason="historical evidence references removed",
    )

    with pytest.raises(
        ValueError,
        match="requires currently verified historical Backtest admission",
    ):
        fixture.wfa_store._append_decision(changed)


def test_candidate_wfa_decoder_rejects_unsupported_result_evidence(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    valid = _load_completed_wfa_payload(fixture, decision)

    cases = (
        "string_capital",
        "string_optimizer_score",
        "empty_test_metrics",
        "empty_stitched_equity",
        "zero_scored_window",
        "trade_count_mismatch",
        "equity_metric_mismatch",
        "wrong_opening_capital",
        "impossible_profitable_rate",
        "negative_transaction_cost",
        "contradictory_mean_net_pnl",
        "contradictory_verdict",
    )

    for case in cases:
        payload = copy.deepcopy(valid)
        if case == "string_capital":
            payload["initial_capital"] = "100000"
        elif case == "string_optimizer_score":
            payload["windows"][0]["optimization_evaluations"][0][
                "score"
            ] = "1.0"
        elif case == "empty_test_metrics":
            payload["windows"][0]["test_metrics"] = {}
        elif case == "empty_stitched_equity":
            payload["stitched_equity_curve"] = []
        elif case == "zero_scored_window":
            payload["windows"][0]["test_scored"] = {
                "count": 0,
                "first_timestamp": None,
                "last_timestamp": None,
            }
        elif case == "trade_count_mismatch":
            payload["windows"][0]["trade_count"] += 100
        elif case == "equity_metric_mismatch":
            payload["windows"][0]["test_metrics"]["account_return_pct"] += 1.0
            payload["windows"][0]["test_metrics"]["profitable"] = (
                payload["windows"][0]["test_metrics"]["account_return_pct"] > 0
            )
        elif case == "wrong_opening_capital":
            timestamp, equity = payload["windows"][0]["oos_equity_curve"][0]
            payload["windows"][0]["oos_equity_curve"][0] = (
                timestamp,
                equity + 100000.0,
            )
        elif case == "impossible_profitable_rate":
            payload["windows"][0]["test_metrics"][
                "net_profitable_trade_rate_pct"
            ] = 12345.0
        elif case == "negative_transaction_cost":
            payload["windows"][0]["test_metrics"][
                "completed_trade_transaction_cost_total"
            ] = -1.0
        elif case == "contradictory_mean_net_pnl":
            payload["windows"][0]["test_metrics"][
                "mean_net_pnl_per_completed_trade"
            ] += 123.0
        elif case == "contradictory_verdict":
            payload["verdict"] = (
                "FAIL" if payload["verdict"] == "PASS" else "PASS"
            )
        else:  # pragma: no cover - tuple above is closed
            raise AssertionError(case)

        raw = canonical_bytes(
            payload,
            schema=CANDIDATE_WFA_RESULT_SCHEMA_ID,
        )
        with pytest.raises((TypeError, ValueError)):
            decode_candidate_wfa_result_bytes(raw)




def test_internal_wfa_writer_rejects_same_result_with_different_current_attempt(
    tmp_path,
):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    replacement_attempt = "replacement-attempt"
    with sqlite3.connect(fixture.database_path) as connection:
        causing_job_id = connection.execute(
            """
            SELECT causing_job_id
            FROM trial_disposition_events
            WHERE trial_id = ?
            ORDER BY sequence_number DESC
            LIMIT 1
            """,
            (fixture.trial.trial_id,),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO run_attempts (
                attempt_id,
                experiment_spec_id,
                state,
                created_at,
                terminal_at,
                runtime_session_id,
                result_artifact_id,
                evidence_id,
                failure_classification,
                failure_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                replacement_attempt,
                fixture.experiment_spec.experiment_spec_id,
                "SUCCEEDED",
                (NOW + timedelta(seconds=40)).isoformat(),
                (NOW + timedelta(seconds=41)).isoformat(),
                "replacement-session",
                fixture.historical_result_artifact.artifact_id,
                fixture.evidence.evidence_id,
                None,
                None,
            ),
        )
        connection.execute(
            """
            UPDATE research_jobs
            SET attempt_id = ?
            WHERE job_id = ?
            """,
            (replacement_attempt, causing_job_id),
        )
        connection.commit()

    changed = replace(
        decision,
        decision_id="wfa-current-attempt-changed",
        created_at=NOW + timedelta(seconds=42),
        reason="current attempt changed with identical result",
    )
    with pytest.raises(ValueError, match="current RunAttempt lineage"):
        fixture.wfa_store._append_decision(changed)


def test_internal_wfa_writer_rejects_historical_manifest_strategy_drift(
    tmp_path,
):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    requested_range = TimeRange(
        fixture.trial.membership_episode_start,
        fixture.trial.membership_episode_end,
    )
    runtime_context = RuntimeContext()
    drift_config = BacktestConfig(
        symbol="AAA",
        timeframe="15m",
        strategy_name="sma_crossover",
        start=requested_range.start,
        end=requested_range.end,
        initial_capital=100000.0,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        strategy_params={"fast_period": 20, "slow_period": 30},
        timezone="UTC",
    )
    drift_strategy = create_registered_research_strategy(
        "sma-crossover-v1",
        drift_config,
    )
    drift_manifest = build_backtest_run_manifest(
        fixture.context,
        requested_range,
        fixture.dataset_fingerprint,
        drift_strategy,
        initial_capital=drift_config.initial_capital,
        runtime_context=runtime_context,
    )
    drift_manifest_artifact = fixture.artifact_store.persist_backtest_manifest(
        drift_manifest,
        created_at=NOW + timedelta(seconds=43),
    )
    fixture.catalog.save_artifact(drift_manifest_artifact)
    drift_configuration_fingerprint = (
        backtest_configuration_fingerprint_v2(
            drift_manifest
        )
    )
    references = (
        research_artifact_reference(drift_manifest_artifact.artifact_id),
        research_artifact_reference(fixture.dataset_artifact.artifact_id),
        research_artifact_reference(
            fixture.historical_result_artifact.artifact_id
        ),
    )
    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            """
            UPDATE experiment_specs
            SET manifest_artifact_id = ?,
                configuration_fingerprint = ?
            WHERE experiment_spec_id = ?
            """,
            (
                drift_manifest_artifact.artifact_id,
                drift_configuration_fingerprint,
                fixture.experiment_spec.experiment_spec_id,
            ),
        )
        connection.execute(
            """
            UPDATE research_evidence
            SET configuration_fingerprint = ?,
                artifact_references = ?
            WHERE evidence_id = ?
            """,
            (
                drift_configuration_fingerprint,
                SQLiteResearchEvidenceStore._encode_sequence(
                    references
                ),
                fixture.evidence.evidence_id,
            ),
        )
        connection.commit()

    changed = replace(
        decision,
        decision_id="wfa-historical-manifest-strategy-drift",
        created_at=NOW + timedelta(seconds=44),
        reason="historical manifest strategy drift",
    )
    with pytest.raises(ValueError, match="registered Trial setup"):
        fixture.wfa_store._append_decision(changed)


def test_internal_wfa_writer_requires_current_historical_eligibility(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    newer_policy = QualificationPolicy(2, Decimal("0"))
    fixture.qualification_store.register_policy(
        newer_policy,
        created_at=NOW + timedelta(seconds=30),
    )
    fixture.qualification_store.activate_policy(
        newer_policy.policy_id,
        activated_at=NOW + timedelta(seconds=31),
    )

    changed = replace(
        decision,
        decision_id="wfa-stale-historical-eligibility",
        created_at=NOW + timedelta(seconds=32),
        reason="stale historical eligibility",
    )
    with pytest.raises(ValueError, match="no longer current"):
        fixture.wfa_store._append_decision(changed)


def test_cand010_internal_wfa_writer_rejects_same_policy_supersession(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    newer = replace(
        fixture.historical_decision,
        decision_id="qualification-newer-same-policy",
        created_at=NOW + timedelta(seconds=32),
        reason="newer same-policy qualification generation",
    )
    fixture.qualification_store.append_decision(newer)

    changed = replace(
        decision,
        decision_id="wfa-stale-same-policy-qualification",
        created_at=NOW + timedelta(seconds=33),
        reason="stale same-policy historical eligibility",
    )
    with pytest.raises(ValueError, match="no longer current"):
        fixture.wfa_store._append_decision(changed)


def test_internal_wfa_writer_requires_approved_window_configuration(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    unsupported = wfa_window_configuration_payload(
        in_sample_bars=200,
        out_sample_bars=150,
        step_bars=150,
        mode="rolling",
    )
    changed = replace(
        decision,
        decision_id="wfa-unapproved-window-configuration",
        created_at=NOW + timedelta(seconds=33),
        wfa_configuration_fingerprint=(
            wfa_window_configuration_fingerprint(**unsupported)
        ),
        reason="unapproved window configuration",
    )

    with pytest.raises(ValueError, match="approved M9.6"):
        fixture.wfa_store._append_decision(changed)


def test_internal_wfa_writer_binds_evaluator_to_trusted_software_identity(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    payload = _load_completed_wfa_payload(fixture, decision)
    payload["evaluator_repository_revision"] = "invented-revision"
    artifact = _persist_wfa_payload(
        fixture,
        payload,
        created_at=NOW + timedelta(seconds=34),
    )
    changed = replace(
        decision,
        decision_id="wfa-invented-evaluator-revision",
        created_at=NOW + timedelta(seconds=34),
        evaluator_repository_revision="invented-revision",
        result_artifact_id=artifact.artifact_id,
        reason="invented evaluator revision",
    )

    with pytest.raises(ValueError, match="trusted current software identity"):
        fixture.wfa_store._append_decision(changed)


def test_historical_qualification_freezes_exact_dataset_reference_admission(tmp_path):
    fixture = _real_registered_fixture(tmp_path)
    with sqlite3.connect(fixture.database_path) as connection:
        row = connection.execute(
            """
            SELECT dataset_reference_artifact_id
            FROM qualification_dataset_admissions
            WHERE decision_id = ?
            """,
            (fixture.historical_decision.decision_id,),
        ).fetchone()
    assert row == (fixture.dataset_artifact.artifact_id,)


def test_internal_wfa_writer_requires_original_admitted_dataset_reference(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    retained = (
        research_artifact_reference(
            fixture.experiment_spec.manifest_artifact_id
        ),
        research_artifact_reference(
            fixture.historical_result_artifact.artifact_id
        ),
    )
    encoded = SQLiteResearchEvidenceStore._encode_sequence(retained)
    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            """
            UPDATE research_evidence
            SET artifact_references = ?
            WHERE evidence_id = ?
            """,
            (encoded, fixture.evidence.evidence_id),
        )
        connection.commit()

    changed = replace(
        decision,
        decision_id="wfa-missing-original-dataset-reference",
        created_at=NOW + timedelta(seconds=35),
        reason="original DatasetReference removed",
    )
    with pytest.raises(ValueError, match="frozen at qualification admission"):
        fixture.wfa_store._append_decision(changed)



def test_internal_writer_rejects_equivalent_dataset_reference_replacement(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    original_bytes = fixture.artifact_store.load_bytes(
        fixture.dataset_artifact.artifact_id
    )
    from core.research.models.dataset_reference import decode_dataset_reference_bytes
    original_reference = decode_dataset_reference_bytes(original_bytes)
    replacement = DatasetReference(
        identity=original_reference.identity,
        provenance=replace(
            original_reference.provenance,
            source="replacement-source",
            retrieved_at=NOW + timedelta(seconds=80),
        ),
    )
    replacement_artifact = fixture.artifact_store.persist_dataset_reference(
        replacement,
        created_at=NOW + timedelta(seconds=80),
    )
    fixture.catalog.save_dataset_reference_artifact(
        replacement_artifact,
        replacement,
    )

    mutated_references = tuple(
        research_artifact_reference(replacement_artifact.artifact_id)
        if value == research_artifact_reference(
            fixture.dataset_artifact.artifact_id
        )
        else value
        for value in fixture.evidence.artifact_references
    )
    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            """
            UPDATE research_evidence
            SET artifact_references = ?
            WHERE evidence_id = ?
            """,
            (
                SQLiteResearchEvidenceStore._encode_sequence(
                    mutated_references
                ),
                fixture.evidence.evidence_id,
            ),
        )
        connection.commit()

    changed = replace(
        decision,
        decision_id="wfa-equivalent-dataset-reference-replacement",
        created_at=NOW + timedelta(seconds=81),
        dataset_reference_artifact_id=replacement_artifact.artifact_id,
        dataset_id=replacement.identity.dataset_id,
        reason="equivalent DatasetReference replacement",
    )
    with pytest.raises(ValueError, match="historically admitted DatasetReference"):
        fixture.wfa_store._append_decision(changed)

def test_git_operational_failure_creates_no_strategy_decision(tmp_path):
    fixture = _real_registered_fixture(tmp_path)
    fixture.service.executable_compatibility_checker = (
        _OperationalCompatibilityChecker()
    )

    with pytest.raises(
        CandidateWfaOperationalError,
        match="failed operationally",
    ):
        fixture.service.evaluate_study_revision(
            fixture.registration.revision.study_revision_id
        )

    candidate = fixture.qualification_store.load_candidate_revision(
        fixture.historical_decision.candidate_revision_id
    )
    assert candidate is not None
    assert (
        fixture.wfa_store.load_current_decision(
            candidate.candidate_revision_id
        )
        is None
    )


def test_two_genuine_candidates_preserve_both_existing_m5_verdicts(
    tmp_path,
):
    fixture, first_decision = _completed_real_wfa_fixture(tmp_path)
    second = _register_second_real_candidate(fixture)

    payload = _opposite_m5_payload(
        _load_completed_wfa_payload(fixture, first_decision)
    )
    payload["study_revision_id"] = (
        second.historical_decision.study_revision_id
    )
    payload["trial_id"] = second.historical_decision.trial_id
    payload["candidate_revision_id"] = second.candidate.candidate_revision_id
    payload["historical_qualification_decision_id"] = (
        second.historical_decision.decision_id
    )

    artifact = _persist_wfa_payload(
        fixture,
        payload,
        created_at=NOW + timedelta(seconds=23),
    )
    opposite_outcome = (
        WfaQualificationOutcome.ELIGIBLE
        if payload["verdict"] == "PASS"
        else WfaQualificationOutcome.REJECTED
    )
    second_decision = CandidateWfaDecision(
        decision_id="wfa-second-independent-outcome",
        created_at=NOW + timedelta(seconds=23),
        evaluator_version="m9.6-v1",
        study_revision_id=second.historical_decision.study_revision_id,
        trial_id=second.historical_decision.trial_id,
        candidate_revision_id=second.candidate.candidate_revision_id,
        historical_qualification_decision_id=(
            second.historical_decision.decision_id
        ),
        evaluator_repository_revision=(
            first_decision.evaluator_repository_revision
        ),
        dataset_reference_artifact_id=(
            first_decision.dataset_reference_artifact_id
        ),
        dataset_id=first_decision.dataset_id,
        dataset_fingerprint=first_decision.dataset_fingerprint,
        wfa_configuration_fingerprint=(
            first_decision.wfa_configuration_fingerprint
        ),
        result_artifact_id=artifact.artifact_id,
        evidence_validity=WfaEvidenceValidity.VALID,
        wfa_verdict=payload["verdict"],
        outcome=opposite_outcome,
        reason="independent second candidate outcome",
    )
    fixture.wfa_store._append_decision(second_decision)

    assert {
        first_decision.wfa_verdict,
        second_decision.wfa_verdict,
    } == {"PASS", "FAIL"}
    assert first_decision.outcome is not second_decision.outcome
    assert (
        fixture.wfa_store.load_decision(second_decision.decision_id)
        == second_decision
    )


def test_current_eligible_query_filters_after_latest_current_policy_decision(tmp_path):
    path = tmp_path / "research.sqlite3"
    store = SQLiteQualificationStore(path)
    policy = QualificationPolicy(1, Decimal("50"))
    store.register_policy(policy, created_at=NOW)
    store.activate_policy(policy.policy_id, activated_at=NOW)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        common = (
            NOW.isoformat(),
            "m9.5-v1",
            policy.policy_id,
            policy.version,
            str(policy.net_profitable_trade_rate_threshold_pct),
            F("2"), F("1"), F("5"), None, None, None,
        )
        connection.execute(
            """
            INSERT INTO qualification_decisions
            (decision_id, created_at, evaluator_version, policy_id, policy_version,
             threshold_text, study_revision_id, trial_id, candidate_revision_id,
             attempt_id, evidence_id, result_artifact_id, evidence_validity,
             criterion_outcome, outcome, profitable_trade_count,
             completed_trade_count, rate_numerator, rate_denominator, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("old-eligible", *common, "VALID", "SATISFIED", "ELIGIBLE", 1, 1, 100, 1, "old"),
        )
        connection.execute(
            """
            INSERT INTO qualification_decisions
            (decision_id, created_at, evaluator_version, policy_id, policy_version,
             threshold_text, study_revision_id, trial_id, candidate_revision_id,
             attempt_id, evidence_id, result_artifact_id, evidence_validity,
             criterion_outcome, outcome, profitable_trade_count,
             completed_trade_count, rate_numerator, rate_denominator, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("new-rejected", *common, "VALID", "NOT_SATISFIED", "REJECTED", 0, 1, 0, 1, "new"),
        )
        connection.commit()

    assert store.list_current_eligible_decisions(F("2")) == ()


def test_current_eligible_query_distinguishes_no_active_policy(tmp_path):
    store = SQLiteQualificationStore(tmp_path / "research.sqlite3")

    with pytest.raises(RuntimeError, match="no active QualificationPolicy"):
        store.list_current_eligible_decisions(F("2"))


def test_newer_active_policy_makes_old_eligibility_noncurrent(tmp_path):
    path = tmp_path / "research.sqlite3"
    store = SQLiteQualificationStore(path)
    policy_1 = QualificationPolicy(1, Decimal("50"))
    policy_2 = QualificationPolicy(2, Decimal("60"))
    store.register_policy(policy_1, created_at=NOW)
    store.activate_policy(policy_1.policy_id, activated_at=NOW)
    store.register_policy(policy_2, created_at=NOW + timedelta(microseconds=1))
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        connection.execute(
            """
            INSERT INTO qualification_decisions
            (decision_id, created_at, evaluator_version, policy_id, policy_version,
             threshold_text, study_revision_id, trial_id, candidate_revision_id,
             attempt_id, evidence_id, result_artifact_id, evidence_validity,
             criterion_outcome, outcome, profitable_trade_count,
             completed_trade_count, rate_numerator, rate_denominator, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "policy-1-eligible", NOW.isoformat(), "m9.5-v1",
                policy_1.policy_id, policy_1.version,
                str(policy_1.net_profitable_trade_rate_threshold_pct),
                F("2"), F("1"), F("5"), None, None, None, "VALID",
                "SATISFIED", "ELIGIBLE", 1, 1, 100, 1, "old policy",
            ),
        )
        connection.commit()
    store.activate_policy(
        policy_2.policy_id,
        activated_at=NOW + timedelta(seconds=1),
    )

    assert store.list_current_eligible_decisions(F("2")) == ()


def test_wfa_decision_model_rejects_fabricated_eligible_without_pass_result():
    with pytest.raises(ValueError, match="ELIGIBLE requires VALID PASS"):
        CandidateWfaDecision(
            decision_id="wfa-invalid-cross-field",
            created_at=NOW,
            evaluator_version="m9.6-v1",
            study_revision_id=F("2"),
            trial_id=F("1"),
            candidate_revision_id=F("5"),
            historical_qualification_decision_id="qualification-1",
            evaluator_repository_revision="rev",
            dataset_reference_artifact_id=F("a"),
            dataset_id=F("b"),
            dataset_fingerprint=F("c"),
            wfa_configuration_fingerprint=F("d"),
            evidence_validity=WfaEvidenceValidity.VALID,
            outcome=WfaQualificationOutcome.ELIGIBLE,
            reason="invalid fixture",
        )



def test_wrapped_sqlite_input_failure_is_operational_without_decision(tmp_path):
    fixture = _service_fixture(tmp_path, 479)

    def fail(_plan):
        try:
            raise sqlite3.OperationalError("database unavailable")
        except sqlite3.OperationalError as error:
            raise ValueError("wrapped input failure") from error

    fixture.service.execution_input_resolver = fail

    with pytest.raises(CandidateWfaOperationalError, match="executable authority"):
        fixture.service.evaluate_study_revision(F("2"))

    assert fixture.wfa_store.decisions == {}


def test_unexpected_dataset_admission_failure_is_operational_without_decision(tmp_path):
    fixture = _service_fixture(tmp_path, 479)

    def fail(_decision_id):
        raise RuntimeError("unexpected admission infrastructure failure")

    fixture.service.qualification_store.load_dataset_admission = fail

    with pytest.raises(
        CandidateWfaOperationalError,
        match="DatasetReference admission",
    ):
        fixture.service.evaluate_study_revision(F("2"))

    assert fixture.wfa_store.decisions == {}


def test_unexpected_dataset_reference_read_failure_is_operational_without_decision(
    tmp_path,
):
    fixture = _service_fixture(tmp_path, 479)
    original = fixture.catalog.load_artifact

    def fail(artifact_id):
        if artifact_id == fixture.dataset_artifact.artifact_id:
            raise RuntimeError("unexpected DatasetReference catalog failure")
        return original(artifact_id)

    fixture.catalog.load_artifact = fail

    with pytest.raises(
        CandidateWfaOperationalError,
        match="DatasetReference could not be read reliably",
    ):
        fixture.service.evaluate_study_revision(F("2"))

    assert fixture.wfa_store.decisions == {}


def test_unexpected_wfa_runner_failure_is_operational_without_decision(
    tmp_path,
    monkeypatch,
):
    fixture = _service_fixture(tmp_path, 479)

    def fail(*_args, **_kwargs):
        raise RuntimeError("unexpected WFA engine failure")

    monkeypatch.setattr(WalkForwardRunner, "run", fail)

    with pytest.raises(
        CandidateWfaOperationalError,
        match="WFA execution failed operationally",
    ):
        fixture.service.evaluate_study_revision(F("2"))

    assert fixture.wfa_store.decisions == {}


def test_wrapped_dataset_reference_value_error_with_sqlite_cause_is_operational(
    tmp_path,
):
    fixture = _service_fixture(tmp_path, 479)
    original = fixture.catalog.load_artifact

    def fail(artifact_id):
        if artifact_id == fixture.dataset_artifact.artifact_id:
            try:
                raise sqlite3.OperationalError("database unavailable")
            except sqlite3.OperationalError as error:
                raise ValueError("wrapped DatasetReference lookup failure") from error
        return original(artifact_id)

    fixture.catalog.load_artifact = fail

    with pytest.raises(
        CandidateWfaOperationalError,
        match="DatasetReference could not be read reliably",
    ):
        fixture.service.evaluate_study_revision(F("2"))

    assert fixture.wfa_store.decisions == {}


def test_dataset_reference_content_identity_mismatch_is_invalid(tmp_path):
    fixture = _service_fixture(tmp_path, 479)
    artifact_path = fixture.artifact_store._absolute_path(
        fixture.dataset_artifact.artifact_id
    )
    artifact_path.write_bytes(b"corrupted DatasetReference bytes")

    decision = fixture.service.evaluate_study_revision(F("2"))[0]

    assert decision.outcome is WfaQualificationOutcome.INVALID
    assert decision.evidence_validity is WfaEvidenceValidity.INVALID
    assert decision.result_artifact_id is None


def test_deterministic_retrieval_value_error_is_invalid_not_operational(tmp_path):
    fixture = _service_fixture(tmp_path, 479)

    class InvalidRetrieval:
        def retrieve(self, *args, **kwargs):
            raise ValueError("contradictory provider candles")

    fixture.service.retrieval_service = InvalidRetrieval()

    decision = fixture.service.evaluate_study_revision(F("2"))[0]

    assert decision.outcome is WfaQualificationOutcome.INVALID
    assert decision.evidence_validity is WfaEvidenceValidity.INVALID
    assert decision.wfa_verdict is None
    assert decision.result_artifact_id is None


def test_nonfinite_wfa_result_is_invalid_not_operational(tmp_path, monkeypatch):
    fixture = _service_fixture(tmp_path, 479)
    original_run = WalkForwardRunner.run

    def invalid_result(self, *args, **kwargs):
        result = original_run(self, *args, **kwargs)
        return replace(
            result,
            aggregated_metrics={
                **result.aggregated_metrics,
                "nonfinite_fixture": float("nan"),
            },
        )

    monkeypatch.setattr(WalkForwardRunner, "run", invalid_result)

    decision = fixture.service.evaluate_study_revision(F("2"))[0]

    assert decision.outcome is WfaQualificationOutcome.INVALID
    assert decision.evidence_validity is WfaEvidenceValidity.INVALID
    assert decision.wfa_verdict is None
    assert decision.result_artifact_id is None


def test_existing_wfa_verdict_maps_exactly_to_stage_outcome():
    assert (
        CandidateWfaService._qualification_outcome_for_verdict("PASS")
        is WfaQualificationOutcome.ELIGIBLE
    )
    assert (
        CandidateWfaService._qualification_outcome_for_verdict("FAIL")
        is WfaQualificationOutcome.REJECTED
    )
    with pytest.raises(ValueError, match="unsupported WFA verdict"):
        CandidateWfaService._qualification_outcome_for_verdict("UNKNOWN")


def test_multiple_eligible_strategies_keep_independent_results():
    service = CandidateWfaService.__new__(CandidateWfaService)
    trials = (
        SimpleNamespace(trial_id="trial-a"),
        SimpleNamespace(trial_id="trial-b"),
    )
    historical = (
        SimpleNamespace(trial_id="trial-a"),
        SimpleNamespace(trial_id="trial-b"),
    )
    service.catalog_store = SimpleNamespace(
        list_registered_trials_for_revision=lambda _revision: trials
    )
    service.qualification_store = SimpleNamespace(
        list_current_eligible_decisions=lambda _revision: historical
    )
    outcomes = {
        "trial-a": WfaQualificationOutcome.ELIGIBLE,
        "trial-b": WfaQualificationOutcome.REJECTED,
    }

    def evaluate_one(historical_decision, trial):
        assert historical_decision.trial_id == trial.trial_id
        return outcomes[trial.trial_id]

    service._evaluate_one = evaluate_one

    assert service.evaluate_study_revision("study-revision") == (
        WfaQualificationOutcome.ELIGIBLE,
        WfaQualificationOutcome.REJECTED,
    )


def test_v7_sql_rejects_valid_eligible_row_with_null_verdict(tmp_path):
    path = tmp_path / "research.sqlite3"
    SQLiteCandidateWfaStore(
        path,
        artifact_store=ContentAddressedResearchArtifactStore(
            tmp_path / "artifacts"
        ),
    )

    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO candidate_wfa_decisions (
                    decision_id,
                    created_at,
                    evaluator_version,
                    study_revision_id,
                    trial_id,
                    candidate_revision_id,
                    historical_qualification_decision_id,
                    evaluator_repository_revision,
                    dataset_reference_artifact_id,
                    dataset_id,
                    dataset_fingerprint,
                    wfa_configuration_fingerprint,
                    result_artifact_id,
                    evidence_validity,
                    wfa_verdict,
                    outcome,
                    reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "sql-null-verdict",
                    NOW.isoformat(),
                    "m9.6-v1",
                    F("2"),
                    F("1"),
                    F("5"),
                    "qualification-1",
                    "current",
                    F("a"),
                    F("b"),
                    F("c"),
                    F("d"),
                    F("e"),
                    "VALID",
                    None,
                    "ELIGIBLE",
                    "must fail SQL cross-field guard",
                ),
            )


def test_genuine_v6_with_qualification_history_migrates_to_v7(tmp_path):
    from core.research import research_schema

    path = tmp_path / "research-v6.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute(research_schema._CREATE_RESEARCH_EVIDENCE_TABLE)
        for statements in (
            research_schema._CREATE_V1_CATALOG_TABLES,
            research_schema._CREATE_V2_TABLES,
            research_schema._CREATE_V3_TABLES,
            research_schema._CREATE_V4_TABLES,
            research_schema._CREATE_V5_TABLES,
            research_schema._CREATE_V6_TABLES,
        ):
            for statement in statements:
                connection.execute(statement)
        for statement in research_schema._CREATE_V2_INDEXES:
            connection.execute(statement)
        connection.execute("PRAGMA user_version = 6")
        connection.commit()

    _seed_minimal_wfa_lineage(path)

    with sqlite3.connect(path) as connection:
        before_candidate = connection.execute(
            "SELECT * FROM fixed_candidate_revisions WHERE candidate_revision_id = ?",
            (F("5"),),
        ).fetchone()
        before_decision = connection.execute(
            "SELECT * FROM qualification_decisions WHERE decision_id = ?",
            ("qualification-1",),
        ).fetchone()

    SQLiteCandidateWfaStore(
        path,
        artifact_store=ContentAddressedResearchArtifactStore(
            tmp_path / "artifacts"
        ),
    )

    with sqlite3.connect(path) as connection:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 8
        after_candidate = connection.execute(
            "SELECT * FROM fixed_candidate_revisions WHERE candidate_revision_id = ?",
            (F("5"),),
        ).fetchone()
        after_decision = connection.execute(
            "SELECT * FROM qualification_decisions WHERE decision_id = ?",
            ("qualification-1",),
        ).fetchone()
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'candidate_wfa_decisions'"
        ).fetchone()

    assert after_candidate == before_candidate
    assert after_decision == before_decision
    assert table == ("candidate_wfa_decisions",)


# ---------------------------------------------------------------------------
# CAND-007 pre-freeze adversarial controls.
# These remain within the approved M9.6 contract: no new economic gate.
# ---------------------------------------------------------------------------


def test_zero_to_positive_epsilon_cannot_change_m5_profitability_boundary():
    curve = [
        (NOW, 100000.0),
        (NOW + timedelta(minutes=15), 100000.0),
    ]
    metrics = {
        "account_pnl": 1e-9,
        "account_return_pct": 1e-9,
        "max_equity_drawdown_pct": 0.0,
    }
    with pytest.raises(ValueError, match="persisted OOS equity curve"):
        _validate_account_metrics_against_equity(
            metrics,
            curve,
            initial_capital=100000.0,
            field_name="flat-window",
        )


def test_genuine_flat_oos_window_remains_valid_and_nonprofitable():
    curve = [
        (NOW, 100000.0),
        (NOW + timedelta(minutes=15), 100000.0),
    ]
    metrics = {
        "account_pnl": 0.0,
        "account_return_pct": 0.0,
        "max_equity_drawdown_pct": 0.0,
    }
    _validate_account_metrics_against_equity(
        metrics,
        curve,
        initial_capital=100000.0,
        field_name="flat-window",
    )
    assert (metrics["account_return_pct"] > 0) is False

def test_positive_instrument_return_may_be_net_losing_after_costs(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    payload = _load_completed_wfa_payload(fixture, decision)
    window = payload["windows"][0]
    metrics = window["test_metrics"]

    metrics["completed_trade_count"] = 1
    metrics["net_profitable_trade_count"] = 0
    metrics["net_losing_trade_count"] = 1
    metrics["net_breakeven_trade_count"] = 0
    metrics["net_profitable_trade_rate_pct"] = 0.0
    metrics["mean_positive_instrument_return_pct"] = 1.0
    metrics["mean_negative_instrument_return_pct"] = 0.0
    metrics["mean_instrument_return_pct"] = 1.0
    metrics["gross_realized_pnl"] = 1.0
    metrics["net_realized_pnl"] = -1.0
    metrics["mean_net_pnl_per_completed_trade"] = -1.0
    metrics["completed_trade_transaction_cost_total"] = 2.0
    window["trade_count"] = 1

    raw = canonical_bytes(
        payload,
        schema=CANDIDATE_WFA_RESULT_SCHEMA_ID,
    )
    decoded = decode_candidate_wfa_result_bytes(raw)
    assert decoded["windows"][0]["test_metrics"][
        "mean_positive_instrument_return_pct"
    ] == 1.0
    assert decoded["windows"][0]["test_metrics"]["net_realized_pnl"] == -1.0


@pytest.mark.parametrize(
    ("profitable", "losing", "breakeven", "net_realized", "message"),
    [
        (0, 1, 0, 100.0, "must be negative"),
        (1, 0, 0, -100.0, "must be positive"),
        (0, 0, 1, 1.0, "must be zero"),
    ],
)
def test_impossible_net_total_signs_are_rejected(
    tmp_path,
    profitable,
    losing,
    breakeven,
    net_realized,
    message,
):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    payload = _load_completed_wfa_payload(fixture, decision)
    window = payload["windows"][0]
    metrics = window["test_metrics"]
    completed = profitable + losing + breakeven

    metrics["completed_trade_count"] = completed
    metrics["net_profitable_trade_count"] = profitable
    metrics["net_losing_trade_count"] = losing
    metrics["net_breakeven_trade_count"] = breakeven
    metrics["net_profitable_trade_rate_pct"] = (
        profitable / completed * 100 if completed else 0.0
    )
    metrics["mean_positive_instrument_return_pct"] = (
        1.0 if profitable else 0.0
    )
    metrics["mean_negative_instrument_return_pct"] = (
        -1.0 if losing else 0.0
    )
    metrics["mean_instrument_return_pct"] = 0.0
    metrics["gross_realized_pnl"] = net_realized
    metrics["net_realized_pnl"] = net_realized
    metrics["mean_net_pnl_per_completed_trade"] = (
        net_realized / completed if completed else 0.0
    )
    metrics["completed_trade_transaction_cost_total"] = 0.0
    window["trade_count"] = completed

    raw = canonical_bytes(
        payload,
        schema=CANDIDATE_WFA_RESULT_SCHEMA_ID,
    )
    with pytest.raises(ValueError, match=message):
        decode_candidate_wfa_result_bytes(raw)


@pytest.mark.parametrize("net_realized", [-100.0, 0.0, 100.0])
def test_mixed_winners_and_losers_may_have_any_net_total_sign(
    tmp_path,
    net_realized,
):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    payload = _load_completed_wfa_payload(fixture, decision)
    window = payload["windows"][0]
    metrics = window["test_metrics"]

    metrics["completed_trade_count"] = 2
    metrics["net_profitable_trade_count"] = 1
    metrics["net_losing_trade_count"] = 1
    metrics["net_breakeven_trade_count"] = 0
    metrics["net_profitable_trade_rate_pct"] = 50.0
    metrics["mean_positive_instrument_return_pct"] = 1.0
    metrics["mean_negative_instrument_return_pct"] = -1.0
    metrics["mean_instrument_return_pct"] = 0.0
    metrics["gross_realized_pnl"] = net_realized
    metrics["net_realized_pnl"] = net_realized
    metrics["mean_net_pnl_per_completed_trade"] = net_realized / 2
    metrics["completed_trade_transaction_cost_total"] = 0.0
    window["trade_count"] = 2

    raw = canonical_bytes(
        payload,
        schema=CANDIDATE_WFA_RESULT_SCHEMA_ID,
    )
    decoded = decode_candidate_wfa_result_bytes(raw)
    assert decoded["windows"][0]["test_metrics"]["net_realized_pnl"] == net_realized


def test_unavailable_software_identity_is_operational_without_decision(tmp_path):
    fixture = _real_registered_fixture(tmp_path)
    fixture.service.software_identity_provider = (
        _UnavailableSoftwareIdentityProvider()
    )

    with pytest.raises(
        CandidateWfaOperationalError,
        match="unavailable operationally",
    ):
        fixture.service.evaluate_study_revision(
            fixture.registration.revision.study_revision_id
        )

    candidate = fixture.qualification_store.load_candidate_revision(
        fixture.historical_decision.candidate_revision_id
    )
    assert candidate is not None
    assert fixture.wfa_store.load_current_decision(
        candidate.candidate_revision_id
    ) is None


def test_dirty_software_identity_is_deterministic_invalidity(tmp_path):
    fixture = _real_registered_fixture(tmp_path)
    fixture.service.software_identity_provider = _DirtySoftwareIdentityProvider()

    decision = fixture.service.evaluate_study_revision(
        fixture.registration.revision.study_revision_id
    )[0]

    assert decision.evidence_validity is WfaEvidenceValidity.INVALID
    assert decision.outcome is WfaQualificationOutcome.INVALID
    assert "worktree" in decision.reason


def test_internal_writer_dirty_software_identity_is_deterministic_invalidity(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    fixture.wfa_store.software_identity_provider = _DirtySoftwareIdentityProvider()
    changed = replace(
        decision,
        decision_id="wfa-dirty-software-identity",
        created_at=NOW + timedelta(seconds=69),
        reason="dirty software identity",
    )

    with pytest.raises(ValueError, match="worktree is not clean"):
        fixture.wfa_store._append_decision(changed)

    assert fixture.wfa_store.load_decision(changed.decision_id) is None


def test_internal_writer_unavailable_software_identity_is_operational(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    fixture.wfa_store.software_identity_provider = (
        _UnavailableSoftwareIdentityProvider()
    )
    changed = replace(
        decision,
        decision_id="wfa-unavailable-software-identity",
        created_at=NOW + timedelta(seconds=70),
        reason="unavailable software identity",
    )

    with pytest.raises(RuntimeError, match="unavailable operationally"):
        fixture.wfa_store._append_decision(changed)

    assert fixture.wfa_store.load_decision(changed.decision_id) is None


def test_insufficient_rejects_missing_frozen_dataset_admission(tmp_path):
    fixture = _real_registered_fixture(tmp_path, candle_count=478)
    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            "DELETE FROM qualification_dataset_admissions WHERE decision_id = ?",
            (fixture.historical_decision.decision_id,),
        )
        connection.commit()

    decision = fixture.service.evaluate_study_revision(
        fixture.registration.revision.study_revision_id
    )[0]
    assert decision.outcome is WfaQualificationOutcome.INVALID


def test_incomplete_retrieval_rejects_missing_frozen_dataset_admission(tmp_path):
    fixture = _real_registered_fixture(tmp_path, candle_count=479)
    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            "DELETE FROM qualification_dataset_admissions WHERE decision_id = ?",
            (fixture.historical_decision.decision_id,),
        )
        connection.commit()
    fixture.service.retrieval_service = _IncompleteRetrievalService(
        TimeRange(
            fixture.trial.membership_episode_start,
            fixture.trial.membership_episode_end,
        )
    )

    decision = fixture.service.evaluate_study_revision(
        fixture.registration.revision.study_revision_id
    )[0]
    assert decision.outcome is WfaQualificationOutcome.INVALID


def test_insufficient_rejects_replaced_current_dataset_reference(tmp_path):
    fixture = _real_registered_fixture(tmp_path, candle_count=478)
    replacement_reference = DatasetReference(
        identity=DatasetIdentityV2(
            instrument_id=fixture.trial.instrument_id,
            requested_range=TimeRange(
                fixture.trial.membership_episode_start,
                fixture.trial.membership_episode_end,
            ),
            timeframe="15m",
            timezone="UTC",
            price_adjustment_basis=PriceAdjustmentBasis.RAW,
            candles=fixture.candles,
        ),
        provenance=DatasetProvenance(
            dataset_id=fixture.dataset_id,
            instrument_id=fixture.trial.instrument_id,
            requested_range=TimeRange(
                fixture.trial.membership_episode_start,
                fixture.trial.membership_episode_end,
            ),
            timeframe="15m",
            timezone="UTC",
            price_adjustment_basis=PriceAdjustmentBasis.RAW,
            source="replacement-provenance",
            coverage=(TimeRange(
                fixture.trial.membership_episode_start,
                fixture.trial.membership_episode_end,
            ),),
            retrieved_at=NOW + timedelta(seconds=30),
        ),
    )
    replacement_artifact = fixture.artifact_store.persist_dataset_reference(
        replacement_reference,
        created_at=NOW + timedelta(seconds=30),
    )
    fixture.catalog.save_dataset_reference_artifact(
        replacement_artifact,
        replacement_reference,
    )
    references = list(fixture.evidence.artifact_references)
    references[1] = research_artifact_reference(
        replacement_artifact.artifact_id
    )
    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            "UPDATE research_evidence SET artifact_references = ? WHERE evidence_id = ?",
            (json.dumps(references, separators=(",", ":")), fixture.evidence.evidence_id),
        )
        connection.commit()

    decision = fixture.service.evaluate_study_revision(
        fixture.registration.revision.study_revision_id
    )[0]
    assert decision.outcome is WfaQualificationOutcome.INVALID




def test_incomplete_retrieval_rejects_frozen_source_fingerprint_contradiction(
    tmp_path,
):
    fixture = _real_registered_fixture(tmp_path, candle_count=479)
    changed_candles = list(fixture.candles)
    changed_candles[0] = replace(
        changed_candles[0],
        volume=changed_candles[0].volume + 1.0,
    )
    requested_range = TimeRange(
        fixture.trial.membership_episode_start,
        fixture.trial.membership_episode_end,
    )
    changed_identity = DatasetIdentityV2(
        instrument_id=fixture.trial.instrument_id,
        requested_range=requested_range,
        timeframe="15m",
        timezone="UTC",
        price_adjustment_basis=PriceAdjustmentBasis.RAW,
        candles=changed_candles,
    )
    changed_reference = DatasetReference(
        identity=changed_identity,
        provenance=DatasetProvenance(
            dataset_id=changed_identity.dataset_id,
            instrument_id=fixture.trial.instrument_id,
            requested_range=requested_range,
            timeframe="15m",
            timezone="UTC",
            price_adjustment_basis=PriceAdjustmentBasis.RAW,
            source="changed-source-fixture",
            coverage=(requested_range,),
            retrieved_at=NOW + timedelta(seconds=80),
        ),
    )
    changed_artifact = fixture.artifact_store.persist_dataset_reference(
        changed_reference,
        created_at=NOW + timedelta(seconds=80),
    )
    fixture.catalog.save_dataset_reference_artifact(
        changed_artifact,
        changed_reference,
    )
    references = list(fixture.evidence.artifact_references)
    original_reference = research_artifact_reference(
        fixture.dataset_artifact.artifact_id
    )
    references[references.index(original_reference)] = (
        research_artifact_reference(changed_artifact.artifact_id)
    )
    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            "UPDATE research_evidence SET artifact_references = ? "
            "WHERE evidence_id = ?",
            (
                json.dumps(references, separators=(",", ":")),
                fixture.evidence.evidence_id,
            ),
        )
        connection.commit()

    latest = QualificationService(
        catalog_store=fixture.catalog,
        artifact_store=fixture.artifact_store,
        qualification_store=fixture.qualification_store,
    ).evaluate_selected_trial(
        fixture.trial.trial_id,
        evaluated_at=NOW + timedelta(seconds=81),
    )
    assert latest.outcome is QualificationOutcome.ELIGIBLE
    assert fixture.qualification_store.load_dataset_admission(
        latest.decision_id
    ) == changed_artifact.artifact_id

    fixture.service.retrieval_service = _IncompleteRetrievalService(
        requested_range
    )
    decision = fixture.service.evaluate_study_revision(
        fixture.registration.revision.study_revision_id
    )[0]

    assert decision.outcome is WfaQualificationOutcome.INVALID
    assert decision.result_artifact_id is None


@pytest.mark.parametrize("route", ["short", "incomplete"])
@pytest.mark.parametrize("mutation", ["delete", "corrupt"])
def test_insufficient_persistence_rechecks_physical_dataset_reference(
    tmp_path,
    route,
    mutation,
):
    fixture = _real_registered_fixture(
        tmp_path,
        candle_count=478 if route == "short" else 479,
    )
    artifact = fixture.catalog.load_artifact(
        fixture.dataset_artifact.artifact_id
    )
    assert artifact is not None
    artifact_path = fixture.artifact_store.root_directory.joinpath(
        *artifact.relative_path.split("/")
    )

    def mutate():
        if mutation == "delete":
            artifact_path.unlink()
        else:
            artifact_path.write_bytes(b"{}")

    requested_range = TimeRange(
        fixture.trial.membership_episode_start,
        fixture.trial.membership_episode_end,
    )
    fixture.service.retrieval_service = _MutatingRetrievalService(
        mutate,
        candles=fixture.candles if route == "short" else None,
        missing_range=(
            requested_range if route == "incomplete" else None
        ),
    )

    with pytest.raises(
        CandidateWfaOperationalError,
        match="durably persisted",
    ):
        fixture.service.evaluate_study_revision(
            fixture.registration.revision.study_revision_id
        )

    assert fixture.wfa_store.load_current_decision(
        fixture.historical_decision.candidate_revision_id
    ) is None


def _mutate_current_historical_authority(fixture, mutation):
    with sqlite3.connect(fixture.database_path) as connection:
        if mutation == "replacement-attempt":
            causing_job_id = connection.execute(
                """
                SELECT causing_job_id
                FROM trial_disposition_events
                WHERE trial_id = ?
                ORDER BY sequence_number DESC
                LIMIT 1
                """,
                (fixture.trial.trial_id,),
            ).fetchone()[0]
            replacement_attempt = "insufficient-replacement-attempt"
            connection.execute(
                """
                INSERT INTO run_attempts (
                    attempt_id,
                    experiment_spec_id,
                    state,
                    created_at,
                    terminal_at,
                    runtime_session_id,
                    result_artifact_id,
                    evidence_id,
                    failure_classification,
                    failure_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    replacement_attempt,
                    fixture.experiment_spec.experiment_spec_id,
                    "SUCCEEDED",
                    (NOW + timedelta(seconds=82)).isoformat(),
                    (NOW + timedelta(seconds=83)).isoformat(),
                    "insufficient-replacement-session",
                    fixture.historical_result_artifact.artifact_id,
                    fixture.evidence.evidence_id,
                    None,
                    None,
                ),
            )
            connection.execute(
                "UPDATE research_jobs SET attempt_id = ? WHERE job_id = ?",
                (replacement_attempt, causing_job_id),
            )
        elif mutation == "attempt-evidence-id":
            connection.execute(
                "UPDATE run_attempts SET evidence_id = ? WHERE attempt_id = ?",
                (
                    "changed-insufficient-evidence",
                    fixture.historical_decision.attempt_id,
                ),
            )
        elif mutation == "rejected-evidence":
            connection.execute(
                "UPDATE research_evidence SET status = 'REJECTED' "
                "WHERE evidence_id = ?",
                (fixture.historical_decision.evidence_id,),
            )
        else:
            raise AssertionError(f"unknown mutation: {mutation}")
        connection.commit()


@pytest.mark.parametrize("route", ["short", "incomplete"])
@pytest.mark.parametrize(
    "mutation",
    ["replacement-attempt", "attempt-evidence-id", "rejected-evidence"],
)
def test_insufficient_persistence_rechecks_current_historical_lineage(
    tmp_path,
    route,
    mutation,
):
    fixture = _real_registered_fixture(
        tmp_path,
        candle_count=478 if route == "short" else 479,
    )
    requested_range = TimeRange(
        fixture.trial.membership_episode_start,
        fixture.trial.membership_episode_end,
    )
    fixture.service.retrieval_service = _MutatingRetrievalService(
        lambda: _mutate_current_historical_authority(
            fixture,
            mutation,
        ),
        candles=fixture.candles if route == "short" else None,
        missing_range=(
            requested_range if route == "incomplete" else None
        ),
    )

    with pytest.raises(
        CandidateWfaOperationalError,
        match="durably persisted",
    ):
        fixture.service.evaluate_study_revision(
            fixture.registration.revision.study_revision_id
        )

    assert fixture.wfa_store.load_current_decision(
        fixture.historical_decision.candidate_revision_id
    ) is None


def test_wfa_metric_decoder_rejects_impossible_zero_cost_gross_net_order(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    payload = _load_completed_wfa_payload(fixture, decision)
    metrics = payload["windows"][0]["test_metrics"]
    metrics["gross_realized_pnl"] = -1e-9
    metrics["net_realized_pnl"] = 1e-9
    metrics["mean_net_pnl_per_completed_trade"] = (
        metrics["net_realized_pnl"] / metrics["completed_trade_count"]
        if metrics["completed_trade_count"]
        else 0.0
    )
    metrics["completed_trade_transaction_cost_total"] = 0.0

    raw = canonical_bytes(
        payload,
        schema=CANDIDATE_WFA_RESULT_SCHEMA_ID,
    )
    with pytest.raises(ValueError, match="zero transaction cost"):
        decode_candidate_wfa_result_bytes(raw)


def test_internal_writer_rejects_missing_active_policy_record(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            "DELETE FROM qualification_policies WHERE policy_id = ?",
            (fixture.historical_decision.policy_id,),
        )
        connection.commit()

    changed = replace(
        decision,
        decision_id="wfa-missing-active-policy-record",
        created_at=NOW + timedelta(seconds=71),
        reason="missing active policy record",
    )
    with pytest.raises(ValueError, match="valid active historical qualification policy"):
        fixture.wfa_store._append_decision(changed)


def test_internal_writer_rejects_contradictory_active_policy_record(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            """
            UPDATE qualification_policies
            SET threshold_text = '1'
            WHERE policy_id = ?
            """,
            (fixture.historical_decision.policy_id,),
        )
        connection.commit()

    changed = replace(
        decision,
        decision_id="wfa-contradictory-active-policy-record",
        created_at=NOW + timedelta(seconds=72),
        reason="contradictory active policy record",
    )
    with pytest.raises(ValueError, match="policy identity is inconsistent"):
        fixture.wfa_store._append_decision(changed)


def test_internal_writer_accepts_equivalent_decimal_policy_text(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            """
            UPDATE qualification_policies
            SET threshold_text = '0.0'
            WHERE policy_id = ?
            """,
            (fixture.historical_decision.policy_id,),
        )
        connection.commit()

    changed = replace(
        decision,
        decision_id="wfa-equivalent-decimal-policy-text",
        created_at=NOW + timedelta(seconds=73),
        reason="equivalent Decimal policy text",
    )
    fixture.wfa_store._append_decision(changed)
    assert fixture.wfa_store.load_decision(changed.decision_id) == changed



def test_wfa_metric_decoder_rejects_overall_instrument_mean_outside_component_means(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    payload = _load_completed_wfa_payload(fixture, decision)
    metrics = payload["windows"][0]["test_metrics"]
    metrics["mean_positive_instrument_return_pct"] = 1.0
    metrics["mean_negative_instrument_return_pct"] = 0.0
    metrics["mean_instrument_return_pct"] = 2.0
    raw = canonical_bytes(payload, schema=CANDIDATE_WFA_RESULT_SCHEMA_ID)
    with pytest.raises(ValueError, match="between the stored negative and positive"):
        decode_candidate_wfa_result_bytes(raw)


def test_wfa_metric_decoder_accepts_mixed_instrument_mean_between_component_means(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    payload = _load_completed_wfa_payload(fixture, decision)
    metrics = payload["windows"][0]["test_metrics"]
    metrics["mean_positive_instrument_return_pct"] = 2.0
    metrics["mean_negative_instrument_return_pct"] = -1.0
    metrics["mean_instrument_return_pct"] = 0.25
    raw = canonical_bytes(payload, schema=CANDIDATE_WFA_RESULT_SCHEMA_ID)
    decoded = decode_candidate_wfa_result_bytes(raw)
    assert decoded["windows"][0]["test_metrics"]["mean_instrument_return_pct"] == 0.25


def test_persistence_verifier_runs_after_begin_immediate(tmp_path, monkeypatch):
    fixture = _real_registered_fixture(tmp_path, candle_count=478)
    original = StudyAggregationService.load_verified_trial_backtest
    lock_states = []

    def wrapped(verifier, trial_id):
        try:
            with sqlite3.connect(fixture.database_path, timeout=0) as contender:
                contender.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as error:
            assert "locked" in str(error).lower()
            lock_states.append("locked")
        else:
            contender.rollback()
            lock_states.append("unlocked")
        return original(verifier, trial_id)

    monkeypatch.setattr(
        StudyAggregationService,
        "load_verified_trial_backtest",
        wrapped,
    )

    decision = fixture.service.evaluate_study_revision(
        fixture.registration.revision.study_revision_id
    )[0]

    assert decision.outcome is WfaQualificationOutcome.INSUFFICIENT
    # Service preflight is intentionally outside the write transaction;
    # the persistence-time canonical verifier must run under BEGIN IMMEDIATE.
    assert lock_states[-1] == "locked"
    assert "unlocked" in lock_states[:-1]


def test_persistence_verifier_does_not_reinitialize_evidence_schema_under_lock(
    tmp_path,
    monkeypatch,
):
    fixture = _real_registered_fixture(tmp_path, candle_count=478)
    decision = fixture.service.evaluate_study_revision(
        fixture.registration.revision.study_revision_id
    )[0]
    assert decision.outcome is WfaQualificationOutcome.INSUFFICIENT

    def forbidden_schema_initialization(_store):
        raise AssertionError(
            "persistence-time evidence reads must not initialize schema"
        )

    monkeypatch.setattr(
        SQLiteResearchEvidenceStore,
        "_initialize_schema",
        forbidden_schema_initialization,
    )

    changed = replace(
        decision,
        decision_id="wfa-no-nested-evidence-schema-init",
        created_at=NOW + timedelta(seconds=94),
        reason="reserved verifier reuses initialized evidence reader",
    )
    fixture.wfa_store._append_decision(changed)


def test_reserved_evidence_reader_remains_live_not_cached(tmp_path):
    fixture = _real_registered_fixture(tmp_path, candle_count=478)
    decision = fixture.service.evaluate_study_revision(
        fixture.registration.revision.study_revision_id
    )[0]
    historical = fixture.qualification_store.load_current_decision(
        decision.trial_id
    )
    assert historical is not None
    assert historical.evidence_id is not None

    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            "UPDATE research_evidence SET status = 'FAILED' WHERE evidence_id = ?",
            (historical.evidence_id,),
        )
        connection.commit()

    changed = replace(
        decision,
        decision_id="wfa-live-reserved-evidence-reader",
        created_at=NOW + timedelta(seconds=95),
        reason="reserved verifier must read current evidence",
    )
    with pytest.raises(
        ValueError,
        match="currently verified historical Backtest",
    ):
        fixture.wfa_store._append_decision(changed)


def test_internal_writer_rejects_malformed_candidate_revision_authority(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            """
            UPDATE fixed_candidate_revisions
            SET created_at = 'not-a-timestamp'
            WHERE candidate_revision_id = ?
            """,
            (decision.candidate_revision_id,),
        )
        connection.commit()

    changed = replace(
        decision,
        decision_id="wfa-malformed-candidate-revision-authority",
        created_at=NOW + timedelta(seconds=91),
        reason="malformed CandidateRevision authority",
    )
    with pytest.raises(ValueError, match="CandidateRevision authority is malformed"):
        fixture.wfa_store._append_decision(changed)


def test_insufficient_writer_rejects_malformed_dataset_artifact_metadata(tmp_path):
    fixture = _real_registered_fixture(tmp_path, candle_count=478)
    decision = fixture.service.evaluate_study_revision(
        fixture.registration.revision.study_revision_id
    )[0]
    assert decision.outcome is WfaQualificationOutcome.INSUFFICIENT

    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            """
            UPDATE research_artifacts
            SET created_at = 'not-a-timestamp'
            WHERE artifact_id = ?
            """,
            (decision.dataset_reference_artifact_id,),
        )
        connection.commit()

    changed = replace(
        decision,
        decision_id="wfa-malformed-dataset-artifact-authority",
        created_at=NOW + timedelta(seconds=92),
        reason="malformed DatasetReference artifact authority",
    )
    with pytest.raises(ValueError, match="DatasetReference artifact metadata is malformed"):
        fixture.wfa_store._append_decision(changed)


def test_completed_writer_rejects_malformed_wfa_result_artifact_metadata(tmp_path):
    fixture, decision = _completed_real_wfa_fixture(tmp_path)
    with sqlite3.connect(fixture.database_path) as connection:
        connection.execute(
            """
            UPDATE research_artifacts
            SET relative_path = '../invalid'
            WHERE artifact_id = ?
            """,
            (decision.result_artifact_id,),
        )
        connection.commit()

    changed = replace(
        decision,
        decision_id="wfa-malformed-result-artifact-authority",
        created_at=NOW + timedelta(seconds=93),
        reason="malformed WFA result artifact authority",
    )
    with pytest.raises(ValueError, match="result artifact metadata is malformed"):
        fixture.wfa_store._append_decision(changed)


def test_outer_historical_evidence_value_error_with_sqlite_cause_is_operational(tmp_path):
    fixture = _service_fixture(tmp_path, 479)

    def fail(**_kwargs):
        try:
            raise sqlite3.OperationalError("database unavailable")
        except sqlite3.OperationalError as error:
            raise ValueError("wrapped historical evidence failure") from error

    fixture.service._load_authoritative_historical_evidence = fail

    with pytest.raises(
        CandidateWfaOperationalError,
        match="result/evidence authority could not be reliably verified",
    ):
        fixture.service.evaluate_study_revision(F("2"))

    assert fixture.wfa_store.decisions == {}


def test_outer_historical_evidence_plain_value_error_is_invalid(tmp_path):
    fixture = _service_fixture(tmp_path, 479)

    def fail(**_kwargs):
        raise ValueError("deterministic historical contradiction")

    fixture.service._load_authoritative_historical_evidence = fail

    decision = fixture.service.evaluate_study_revision(F("2"))[0]

    assert decision.outcome is WfaQualificationOutcome.INVALID
    assert decision.evidence_validity is WfaEvidenceValidity.INVALID
    assert decision.result_artifact_id is None

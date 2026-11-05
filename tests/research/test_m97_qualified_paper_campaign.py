from dataclasses import replace
from datetime import datetime, timedelta, timezone
from threading import Event, RLock
from types import SimpleNamespace
import sqlite3

import pytest

import api.main as api_main_module
import api.paper_trading_application as paper_app_module
import api.qualified_paper_campaign_application as qualified_app_module
from api.paper_trading_application import PaperTradingApplication
from api.qualified_paper_campaign_application import (
    QualifiedPaperCampaignApplication,
    prepare_qualified_paper_trading,
)
from core.broker.angelone_config import AngelOneConfig
from core.config.app_config import AppConfig
from core.config.backtest_config import BacktestConfig
from core.config.paper_data_source import PaperDataSource
from core.config.walk_forward_config import WALK_FORWARD_CONFIG
from core.entities.instrument import Instrument
from core.market_data.historical_coverage import TimeRange
from core.market_data.instrument_registry import StaticInstrumentRegistry
from core.market_data.provider_instrument_binding import ProviderInstrumentBinding
from core.paper_trading.paper_trading_session import PaperTradingSession
from core.research.backtest_financial_configuration import (
    effective_backtest_financial_configuration,
)
from core.research.claimed_trial_execution_inputs import ClaimedTrialExecutionInputs
from core.research.models.dataset import PriceAdjustmentBasis
from core.research.models.paper_campaign import (
    PaperCampaign,
    PaperCampaignHistory,
    PaperCampaignSession,
    PaperCampaignSessionState,
)
from core.research.models.qualification import (
    FixedCandidateRevision,
    QualificationOutcome,
)
from core.research.models.registered_study import EvidenceReusePolicy
from core.research.models.research_catalog import (
    ComputationKind,
    ResearchArtifactKind,
)
from core.research.models.wfa_qualification import (
    CANDIDATE_WFA_EVALUATOR_VERSION,
    CANDIDATE_WFA_RESULT_SCHEMA_ID,
    CandidateWfaDecision,
    WfaEvidenceValidity,
    WfaQualificationOutcome,
    candidate_wfa_result_bytes,
    wfa_window_configuration_fingerprint,
    wfa_window_configuration_payload,
)
from core.research.qualified_paper_campaign_service import (
    QualifiedPaperAdmissionError,
    QualifiedPaperCampaignService,
    QualifiedPaperOperationalError,
)
from core.research.registered_trial_execution_plan import (
    RegisteredTrialExecutionPlan,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.sqlite_paper_campaign_store import SQLitePaperCampaignStore
from core.runtime.dataset_context import DatasetContext
from core.runtime.paper_runtime import PreparedLivePaperRun
from core.runtime.runtime_context import RuntimeContext
from core.strategies.strategy_factory import create_registered_research_strategy
from core.walk_forward.equity_stitcher import EquityStitcher
from core.walk_forward.metrics import WalkForwardMetrics


INDIA = timezone(timedelta(hours=5, minutes=30))
NOW = datetime(2026, 11, 5, 10, 0, tzinfo=INDIA)
HISTORICAL_START = datetime(2024, 1, 1, 9, 15, tzinfo=INDIA)


def fp(char: str) -> str:
    return "sha256:" + char * 64


def _metric_payload(*, profitable_key: bool) -> dict:
    values = {
        "completed_trade_count": 1,
        "net_profitable_trade_count": 1,
        "net_losing_trade_count": 0,
        "net_breakeven_trade_count": 0,
        "net_profitable_trade_rate_pct": 100.0,
        "mean_positive_instrument_return_pct": 1.0,
        "mean_negative_instrument_return_pct": 0.0,
        "mean_instrument_return_pct": 1.0,
        "gross_realized_pnl": 1000.0,
        "net_realized_pnl": 1000.0,
        "mean_net_pnl_per_completed_trade": 1000.0,
        "completed_trade_transaction_cost_total": 0.0,
        "account_pnl": 1000.0,
        "account_return_pct": 1.0,
        "max_equity_drawdown_pct": 0.0,
    }
    if profitable_key:
        values["profitable"] = True
    return values


def _canonical_wfa_bytes(
    *,
    candidate,
    plan,
    historical_decision_id: str,
    dataset_reference_artifact_id: str,
    dataset_id: str,
    dataset_fingerprint: str,
    evaluator_repository_revision: str,
) -> tuple[bytes, str]:
    config = wfa_window_configuration_payload(
        in_sample_bars=WALK_FORWARD_CONFIG.in_sample_bars,
        out_sample_bars=WALK_FORWARD_CONFIG.out_sample_bars,
        step_bars=WALK_FORWARD_CONFIG.step_bars,
        mode=WALK_FORWARD_CONFIG.mode,
    )
    config_fingerprint = wfa_window_configuration_fingerprint(**config)

    prehistory = 29
    train_start = HISTORICAL_START + timedelta(minutes=15 * prehistory)
    train = tuple(
        SimpleNamespace(timestamp=train_start + timedelta(minutes=15 * index))
        for index in range(config["in_sample_bars"])
    )
    train_history = tuple(
        SimpleNamespace(
            timestamp=HISTORICAL_START + timedelta(minutes=15 * index)
        )
        for index in range(prehistory)
    )
    test_start = train[-1].timestamp + timedelta(minutes=15)
    test = tuple(
        SimpleNamespace(timestamp=test_start + timedelta(minutes=15 * index))
        for index in range(config["out_sample_bars"])
    )
    test_history = train[-prehistory:]

    equity_curve = [
        (
            value.timestamp,
            100000.0 + (1000.0 * index / (len(test) - 1)),
        )
        for index, value in enumerate(test)
    ]
    test_metrics = _metric_payload(profitable_key=True)
    optimizer_metrics = _metric_payload(profitable_key=False)
    evaluation_score = 1.0
    returned_window = SimpleNamespace(
        window_index=0,
        best_params=dict(plan.parameter_configuration),
        optimization_result=SimpleNamespace(
            best_params=dict(plan.parameter_configuration),
            evaluations=(
                SimpleNamespace(
                    params=dict(plan.parameter_configuration),
                    score=evaluation_score,
                    metrics=optimizer_metrics,
                ),
            ),
        ),
        optimization_stability_score=(
            WalkForwardMetrics.optimization_stability_score(
                [evaluation_score]
            )
        ),
        test_metrics=test_metrics,
        trade_count=1,
        backtest_result=SimpleNamespace(equity_curve=equity_curve),
    )
    expected_window = SimpleNamespace(
        window_index=0,
        train_history_bars=train_history,
        train_bars=train,
        test_history_bars=test_history,
        test_bars=test,
    )
    stitched, exact_stitched = EquityStitcher.stitch_with_exact(
        [returned_window]
    )
    aggregated = WalkForwardMetrics.aggregate([test_metrics])
    aggregated["avg_optimization_stability"] = 1.0
    result = SimpleNamespace(
        windows=(returned_window,),
        aggregated_metrics=aggregated,
        stitched_equity_curve=stitched,
        stitched_equity_metrics=(
            WalkForwardMetrics.compute_stitched_equity_metrics(
                exact_stitched
            )
        ),
        verdict="PASS",
    )

    payload = candidate_wfa_result_bytes(
        study_revision_id=candidate.study_revision_id,
        trial_id=candidate.trial_id,
        candidate_revision_id=candidate.candidate_revision_id,
        historical_qualification_decision_id=historical_decision_id,
        historical_experiment_spec_id=candidate.experiment_spec_id,
        source_dataset_reference_artifact_id=dataset_reference_artifact_id,
        source_dataset_id=dataset_id,
        dataset_fingerprint=dataset_fingerprint,
        requested_range=plan.trial_range,
        instrument_id=plan.instrument_id,
        timeframe=plan.timeframe,
        timezone=plan.timezone,
        strategy_procedure_id=plan.strategy_procedure_id,
        strategy_parameters=plan.parameter_configuration,
        initial_capital=plan.initial_capital,
        risk_economic_configuration=plan.risk_economic_configuration,
        data_treatment_basis=plan.data_treatment_basis,
        wfa_configuration=config,
        wfa_configuration_fingerprint=config_fingerprint,
        resolved_prehistory_bars=prehistory,
        expected_windows=(expected_window,),
        result=result,
        evaluator_repository_revision=evaluator_repository_revision,
    )
    return payload, config_fingerprint


class MutableQualificationStore:
    def __init__(self, candidate, current_decision):
        self.candidate = candidate
        self.current_decision = current_decision
        self.raise_on_candidate = None

    def load_candidate_revision(self, _candidate_revision_id):
        if self.raise_on_candidate is not None:
            raise self.raise_on_candidate
        return self.candidate

    def load_current_decision(self, _trial_id):
        return self.current_decision


class MutableWfaStore:
    def __init__(self, current_decision):
        self.current_decision = current_decision

    def load_current_decision(self, _candidate_revision_id):
        return self.current_decision


class CatalogStore:
    def __init__(self, *, trial, experiment_spec, artifact):
        self.trial = trial
        self.experiment_spec = experiment_spec
        self.artifact = artifact

    def load_trial(self, _trial_id):
        return self.trial

    def load_experiment_spec(self, _spec_id):
        return self.experiment_spec

    def load_artifact(self, artifact_id):
        if artifact_id == self.artifact.artifact_id:
            return self.artifact
        return None


class Resolver:
    def __init__(self, plan):
        self.plan = plan
        self.failure = None

    def resolve(self, _trial_id):
        if self.failure is not None:
            raise self.failure
        return self.plan


class SoftwareIdentityProvider:
    def __init__(self, *, clean=True, revision="current-revision"):
        self.clean = clean
        self.revision = revision

    def resolve(self):
        return SimpleNamespace(
            repository_revision=self.revision,
            worktree_clean=self.clean,
        )


class CompatibilityChecker:
    def __init__(self, compatible=True):
        self.compatible = compatible

    def check(self, **_kwargs):
        return SimpleNamespace(compatible=self.compatible)


class MemoryCampaignStore:
    """Small service-unit double; SQLite durability has separate real-store tests."""

    def __init__(self):
        self.campaigns = {}
        self.sessions = {}

    def create_campaign(self, campaign):
        self.campaigns[campaign.campaign_id] = campaign
        return campaign

    def load_campaign(self, campaign_id):
        return self.campaigns.get(campaign_id)

    def register_session(self, session):
        if any(
            value.state
            in {
                PaperCampaignSessionState.CREATED,
                PaperCampaignSessionState.RUNNING,
            }
            for value in self.sessions.values()
        ):
            raise ValueError("a durable qualified Paper session is already active")
        self.sessions[session.session_id] = session

    def load_session(self, session_id):
        return self.sessions.get(session_id)

    def load_active_session(self):
        return next(
            (
                value
                for value in self.sessions.values()
                if value.state
                in {
                    PaperCampaignSessionState.CREATED,
                    PaperCampaignSessionState.RUNNING,
                }
            ),
            None,
        )

    def mark_running_if_created(self, session_id, *, started_at):
        current = self.sessions[session_id]
        if current.state is PaperCampaignSessionState.CREATED:
            current = replace(
                current,
                state=PaperCampaignSessionState.RUNNING,
                started_at=started_at,
            )
            self.sessions[session_id] = current
        return current

    def terminalize_session(
        self,
        session_id,
        *,
        state,
        terminal_at,
        terminal_snapshot_json,
        failure_type,
        failure_message,
    ):
        current = self.sessions[session_id]
        if current.state is PaperCampaignSessionState.INTERRUPTED:
            raise ValueError("interrupted Paper campaign session cannot be rewritten")
        if current.state in {
            PaperCampaignSessionState.STOPPED,
            PaperCampaignSessionState.FAILED,
        }:
            if (
                current.state is not state
                or current.terminal_snapshot_json != terminal_snapshot_json
                or current.failure_type != failure_type
                or current.failure_message != failure_message
            ):
                raise ValueError("terminal Paper campaign evidence is append-only")
            return current
        terminal = replace(
            current,
            state=state,
            terminal_at=terminal_at,
            terminal_snapshot_json=terminal_snapshot_json,
            failure_type=failure_type,
            failure_message=failure_message,
        )
        self.sessions[session_id] = terminal
        return terminal

    def recover_incomplete_sessions(self, *, terminal_at):
        recovered = 0
        for key, current in tuple(self.sessions.items()):
            if current.state not in {
                PaperCampaignSessionState.CREATED,
                PaperCampaignSessionState.RUNNING,
            }:
                continue
            effective_terminal = max(
                value
                for value in (terminal_at, current.created_at, current.started_at)
                if value is not None
            )
            self.sessions[key] = replace(
                current,
                state=PaperCampaignSessionState.INTERRUPTED,
                terminal_at=effective_terminal,
                terminal_snapshot_json=None,
                failure_type="ApplicationRestart",
                failure_message=(
                    "prior process ended before a terminal Paper snapshot "
                    "was durably recorded"
                ),
            )
            recovered += 1
        return recovered

    def load_history(self, campaign_id):
        campaign = self.campaigns.get(campaign_id)
        if campaign is None:
            return None
        return PaperCampaignHistory(
            campaign=campaign,
            sessions=tuple(
                value
                for value in self.sessions.values()
                if value.campaign_id == campaign_id
            ),
        )


def service_fixture(tmp_path):
    runtime_context = RuntimeContext(risk_per_trade_pct=1.0)
    risk = effective_backtest_financial_configuration(runtime_context)
    trial_range = TimeRange(
        HISTORICAL_START,
        HISTORICAL_START + timedelta(minutes=15 * 479),
    )
    plan = RegisteredTrialExecutionPlan(
        trial_id=fp("3"),
        study_revision_id=fp("2"),
        instrument_id="instrument-reliance",
        strategy_procedure_id="sma-crossover-v1",
        timeframe="15m",
        research_range=trial_range,
        trial_range=trial_range,
        timezone="Asia/Kolkata",
        initial_capital=100000.0,
        risk_economic_configuration=risk,
        parameter_configuration={"fast_period": 10, "slow_period": 30},
        data_treatment_basis={"price_adjustment": "raw"},
        repository_revision="historical-revision",
        evidence_reuse_policy=EvidenceReusePolicy.FORCE_NEW_EXECUTION,
    )
    config = BacktestConfig(
        symbol="RELIANCE",
        timeframe=plan.timeframe,
        strategy_name="sma_crossover",
        start=plan.trial_range.start,
        end=plan.trial_range.end,
        initial_capital=plan.initial_capital,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        strategy_params=dict(plan.parameter_configuration),
        timezone=plan.timezone,
    )
    inputs = ClaimedTrialExecutionInputs(
        strategy=create_registered_research_strategy(
            plan.strategy_procedure_id,
            config,
        ),
        config=config,
        runtime_context=runtime_context,
        dataset_context=DatasetContext(
            symbol="RELIANCE",
            timeframe=plan.timeframe,
            timezone=plan.timezone,
        ),
        provider="angelone",
        price_adjustment_basis=PriceAdjustmentBasis.RAW,
        strategy_procedure_id=plan.strategy_procedure_id,
        risk_economic_configuration=risk,
        data_treatment_basis=plan.data_treatment_basis,
    )
    candidate = FixedCandidateRevision(
        candidate_revision_id=fp("1"),
        study_revision_id=plan.study_revision_id,
        trial_id=plan.trial_id,
        experiment_spec_id=fp("4"),
        parameter_configuration_fingerprint=fp("5"),
        created_at=NOW - timedelta(days=1),
    )
    historical = SimpleNamespace(
        decision_id="historical-decision-1",
        outcome=QualificationOutcome.ELIGIBLE,
        candidate_revision_id=candidate.candidate_revision_id,
    )
    dataset_reference_artifact_id = fp("6")
    dataset_id = fp("7")
    dataset_fingerprint = fp("8")
    payload, wfa_config_fingerprint = _canonical_wfa_bytes(
        candidate=candidate,
        plan=plan,
        historical_decision_id=historical.decision_id,
        dataset_reference_artifact_id=dataset_reference_artifact_id,
        dataset_id=dataset_id,
        dataset_fingerprint=dataset_fingerprint,
        evaluator_repository_revision="current-revision",
    )
    artifact_store = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )
    artifact = artifact_store.persist_bytes(
        payload,
        artifact_kind=ResearchArtifactKind.WFA_RESULT,
        schema_id=CANDIDATE_WFA_RESULT_SCHEMA_ID,
        created_at=NOW - timedelta(hours=1),
    )
    wfa = CandidateWfaDecision(
        decision_id="wfa-decision-1",
        created_at=NOW - timedelta(minutes=30),
        evaluator_version=CANDIDATE_WFA_EVALUATOR_VERSION,
        study_revision_id=candidate.study_revision_id,
        trial_id=candidate.trial_id,
        candidate_revision_id=candidate.candidate_revision_id,
        historical_qualification_decision_id=historical.decision_id,
        evaluator_repository_revision="current-revision",
        dataset_reference_artifact_id=dataset_reference_artifact_id,
        dataset_id=dataset_id,
        dataset_fingerprint=dataset_fingerprint,
        wfa_configuration_fingerprint=wfa_config_fingerprint,
        result_artifact_id=artifact.artifact_id,
        evidence_validity=WfaEvidenceValidity.VALID,
        wfa_verdict="PASS",
        outcome=WfaQualificationOutcome.ELIGIBLE,
        reason="fixture PASS",
    )
    trial = SimpleNamespace(
        trial_id=candidate.trial_id,
        study_revision_id=candidate.study_revision_id,
        experiment_spec_id=candidate.experiment_spec_id,
        parameter_configuration_fingerprint=(
            candidate.parameter_configuration_fingerprint
        ),
    )
    experiment_spec = SimpleNamespace(
        computation_kind=ComputationKind.BACKTEST,
        experiment_spec_id=candidate.experiment_spec_id,
        repository_revision=plan.repository_revision,
    )
    qualification = MutableQualificationStore(candidate, historical)
    wfa_store = MutableWfaStore(wfa)
    campaign_store = MemoryCampaignStore()
    resolver = Resolver(plan)
    registry = StaticInstrumentRegistry(
        instruments=(
            Instrument(
                instrument_id=plan.instrument_id,
                symbol="RELIANCE",
            ),
        ),
        provider_bindings=(
            ProviderInstrumentBinding(
                binding_id="angelone-reliance-v1",
                instrument_id=plan.instrument_id,
                provider="angelone",
                provider_instrument_id="2885",
                provider_exchange="NSE",
                provider_symbol="RELIANCE",
            ),
        ),
    )
    service = QualifiedPaperCampaignService(
        catalog_store=CatalogStore(
            trial=trial,
            experiment_spec=experiment_spec,
            artifact=artifact,
        ),
        artifact_store=artifact_store,
        qualification_store=qualification,
        wfa_store=wfa_store,
        campaign_store=campaign_store,
        plan_resolver=resolver,
        execution_input_resolver=lambda _plan: inputs,
        software_identity_provider=SoftwareIdentityProvider(),
        executable_compatibility_checker=CompatibilityChecker(),
        instrument_registry=registry,
        clock=lambda: NOW,
        campaign_id_factory=lambda: "campaign-1",
    )
    return SimpleNamespace(
        service=service,
        candidate=candidate,
        historical=historical,
        wfa=wfa,
        campaign_store=campaign_store,
        qualification=qualification,
        wfa_store=wfa_store,
        inputs=inputs,
        plan=plan,
        resolver=resolver,
        registry=registry,
        artifact_store=artifact_store,
    )


def test_campaign_uses_real_registered_input_and_canonical_wfa_validation(tmp_path):
    fixture = service_fixture(tmp_path)
    campaign = fixture.service.create_campaign(
        fixture.candidate.candidate_revision_id
    )

    assert campaign.candidate_revision_id == fixture.candidate.candidate_revision_id
    assert campaign.wfa_decision_id == fixture.wfa.decision_id
    assert campaign.configuration_fingerprint.startswith("sha256:")
    assert campaign.created_repository_revision == "current-revision"


def test_campaign_requires_current_wfa_pass(tmp_path):
    fixture = service_fixture(tmp_path)
    fixture.wfa_store.current_decision = replace(
        fixture.wfa,
        decision_id="wfa-decision-rejected",
        wfa_verdict="FAIL",
        outcome=WfaQualificationOutcome.REJECTED,
    )

    with pytest.raises(QualifiedPaperAdmissionError, match="WFA eligible"):
        fixture.service.create_campaign(fixture.candidate.candidate_revision_id)


def test_campaign_requires_same_current_historical_decision(tmp_path):
    fixture = service_fixture(tmp_path)
    fixture.qualification.current_decision = SimpleNamespace(
        decision_id="historical-decision-new",
        outcome=QualificationOutcome.ELIGIBLE,
        candidate_revision_id=fixture.candidate.candidate_revision_id,
    )

    with pytest.raises(QualifiedPaperAdmissionError, match="historical"):
        fixture.service.create_campaign(fixture.candidate.candidate_revision_id)


def test_missing_or_wrong_wfa_artifact_blocks_admission(tmp_path):
    fixture = service_fixture(tmp_path)
    artifact = fixture.service.catalog_store.artifact
    artifact_path = fixture.artifact_store.root_directory.joinpath(
        *artifact.relative_path.split("/")
    )
    artifact_path.unlink()

    with pytest.raises(QualifiedPaperAdmissionError, match="artifact bytes"):
        fixture.service.create_campaign(fixture.candidate.candidate_revision_id)

    fixture = service_fixture(tmp_path / "wrong-kind")
    fixture.service.catalog_store.artifact = replace(
        fixture.service.catalog_store.artifact,
        artifact_kind=ResearchArtifactKind.BACKTEST_RESULT,
    )
    with pytest.raises(QualifiedPaperAdmissionError, match="kind or schema"):
        fixture.service.create_campaign(fixture.candidate.candidate_revision_id)


def test_operational_resolver_oserror_stays_operational(tmp_path):
    fixture = service_fixture(tmp_path)
    fixture.resolver.failure = OSError("disk unavailable")

    with pytest.raises(QualifiedPaperOperationalError, match="reliably"):
        fixture.service.create_campaign(fixture.candidate.candidate_revision_id)


def test_deterministic_resolver_value_error_is_admission_failure(tmp_path):
    fixture = service_fixture(tmp_path)
    fixture.resolver.failure = ValueError("contradictory registered plan")

    with pytest.raises(QualifiedPaperAdmissionError, match="plan"):
        fixture.service.create_campaign(fixture.candidate.candidate_revision_id)


def test_dirty_or_incompatible_executable_fails_closed(tmp_path):
    fixture = service_fixture(tmp_path)
    fixture.service.software_identity_provider = SoftwareIdentityProvider(clean=False)
    with pytest.raises(QualifiedPaperAdmissionError, match="not clean"):
        fixture.service.create_campaign(fixture.candidate.candidate_revision_id)

    fixture.service.software_identity_provider = SoftwareIdentityProvider()
    fixture.service.executable_compatibility_checker = CompatibilityChecker(False)
    with pytest.raises(QualifiedPaperAdmissionError, match="executable core"):
        fixture.service.create_campaign(fixture.candidate.candidate_revision_id)


def test_qualified_mvp_rejects_non_ist_candidate_time_semantics(tmp_path):
    fixture = service_fixture(tmp_path)
    bad_context = DatasetContext("RELIANCE", "15m", "UTC")
    bad_config = replace(fixture.inputs.config, timezone="UTC")
    fixture.service.execution_input_resolver = lambda _plan: ClaimedTrialExecutionInputs(
        strategy=create_registered_research_strategy(
            fixture.plan.strategy_procedure_id,
            bad_config,
        ),
        config=bad_config,
        runtime_context=fixture.inputs.runtime_context,
        dataset_context=bad_context,
        provider="angelone",
        price_adjustment_basis=PriceAdjustmentBasis.RAW,
        strategy_procedure_id=fixture.plan.strategy_procedure_id,
        risk_economic_configuration=fixture.inputs.risk_economic_configuration,
        data_treatment_basis=fixture.inputs.data_treatment_basis,
    )

    with pytest.raises(QualifiedPaperAdmissionError):
        fixture.service.create_campaign(fixture.candidate.candidate_revision_id)


def test_qualified_mvp_rejects_uncertified_timeframe_and_provider(tmp_path):
    fixture = service_fixture(tmp_path)
    bad_plan = replace(fixture.plan, timeframe="1d")
    fixture.resolver.plan = bad_plan
    with pytest.raises(QualifiedPaperAdmissionError):
        fixture.service.create_campaign(fixture.candidate.candidate_revision_id)

    fixture = service_fixture(tmp_path / "provider")
    fixture.service.execution_input_resolver = lambda _plan: replace(
        fixture.inputs,
        provider="another-provider",
    )
    with pytest.raises(QualifiedPaperAdmissionError, match="AngelOne"):
        fixture.service.create_campaign(fixture.candidate.candidate_revision_id)


def test_configuration_fingerprint_changes_without_mutating_mappingproxy(tmp_path):
    fixture = service_fixture(tmp_path)
    first = fixture.service._configuration_fingerprint(
        candidate=fixture.candidate,
        wfa_decision=fixture.wfa,
        plan=fixture.plan,
        inputs=fixture.inputs,
    )
    changed_risk = dict(fixture.inputs.risk_economic_configuration)
    changed_risk["risk_per_trade_pct"] = (
        float(changed_risk["risk_per_trade_pct"]) + 0.25
    )
    changed_inputs = ClaimedTrialExecutionInputs(
        strategy=fixture.inputs.strategy,
        config=fixture.inputs.config,
        runtime_context=fixture.inputs.runtime_context,
        dataset_context=fixture.inputs.dataset_context,
        provider=fixture.inputs.provider,
        price_adjustment_basis=fixture.inputs.price_adjustment_basis,
        strategy_procedure_id=fixture.inputs.strategy_procedure_id,
        risk_economic_configuration=changed_risk,
        data_treatment_basis=fixture.inputs.data_treatment_basis,
    )
    second = fixture.service._configuration_fingerprint(
        candidate=fixture.candidate,
        wfa_decision=fixture.wfa,
        plan=fixture.plan,
        inputs=changed_inputs,
    )

    assert first != second
    assert fixture.inputs.risk_economic_configuration["risk_per_trade_pct"] == 1.0


def test_session_rechecks_same_wfa_decision_and_exact_live_binding(tmp_path):
    fixture = service_fixture(tmp_path)
    campaign = fixture.service.create_campaign(fixture.candidate.candidate_revision_id)
    authority = fixture.service.prepare_session(campaign.campaign_id)
    assert authority.live_binding.binding_id == "angelone-reliance-v1"

    fixture.wfa_store.current_decision = replace(
        fixture.wfa,
        decision_id="wfa-decision-new",
    )
    with pytest.raises(QualifiedPaperAdmissionError, match="no longer matches"):
        fixture.service.prepare_session(campaign.campaign_id)


def test_missing_live_binding_blocks_preparation(tmp_path):
    fixture = service_fixture(tmp_path)
    campaign = fixture.service.create_campaign(fixture.candidate.candidate_revision_id)
    fixture.service.instrument_registry = StaticInstrumentRegistry(
        instruments=fixture.registry.instruments,
        provider_bindings=(),
    )

    with pytest.raises(QualifiedPaperAdmissionError, match="missing or ambiguous"):
        fixture.service.prepare_session(campaign.campaign_id)


def _paper_campaign() -> PaperCampaign:
    return PaperCampaign(
        campaign_id="campaign-sqlite",
        created_at=NOW,
        candidate_revision_id=fp("1"),
        wfa_decision_id="wfa-sqlite",
        study_revision_id=fp("2"),
        trial_id=fp("3"),
        experiment_spec_id=fp("4"),
        parameter_configuration_fingerprint=fp("5"),
        configuration_fingerprint=fp("6"),
        created_repository_revision="current-revision",
    )


def _artifact_row(connection, artifact_id, kind):
    digest = artifact_id.removeprefix("sha256:")
    connection.execute(
        """
        INSERT INTO research_artifacts (
            artifact_id, artifact_kind, schema_id, relative_path,
            byte_count, created_at
        ) VALUES (?, ?, ?, ?, 0, ?)
        """,
        (
            artifact_id,
            kind,
            "fixture.v1",
            f"sha256/{digest[:2]}/{digest}.json",
            NOW.isoformat(),
        ),
    )


def _seed_campaign_parent_rows(path, campaign):
    store = SQLitePaperCampaignStore(path)
    del store
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        plan_artifact = fp("7")
        manifest_artifact = fp("8")
        membership_artifact = fp("9")
        backtest_result_artifact = fp("a")
        dataset_artifact = fp("b")
        wfa_result_artifact = fp("c")
        for artifact_id, kind in (
            (plan_artifact, "STUDY_REVISION_PLAN"),
            (manifest_artifact, "BACKTEST_RUN_MANIFEST"),
            (membership_artifact, "TRIAL_MEMBERSHIP_EVIDENCE"),
            (backtest_result_artifact, "BACKTEST_RESULT"),
            (dataset_artifact, "DATASET_REFERENCE"),
            (wfa_result_artifact, "WFA_RESULT"),
        ):
            _artifact_row(connection, artifact_id, kind)
        connection.execute(
            "INSERT INTO studies VALUES (?, ?, ?, ?)",
            ("study-sqlite", NOW.isoformat(), "fixture", 0),
        )
        connection.execute(
            """
            INSERT INTO study_revisions (
                study_revision_id, identity_schema, study_id, revision_number,
                plan_artifact_id, repository_revision, evidence_reuse_policy,
                registered_at, initial_batch_started_at
            ) VALUES (?, 'fixture.v1', 'study-sqlite', 1, ?, ?,
                      'FORCE_NEW_EXECUTION', ?, NULL)
            """,
            (
                campaign.study_revision_id,
                plan_artifact,
                "historical-revision",
                NOW.isoformat(),
            ),
        )
        connection.execute(
            """
            INSERT INTO experiment_specs (
                experiment_spec_id, identity_schema, computation_kind,
                manifest_artifact_id, dataset_fingerprint,
                configuration_fingerprint, repository_revision, created_at
            ) VALUES (?, 'kanasu.experiment-spec.v1', 'BACKTEST', ?, ?, ?, ?, ?)
            """,
            (
                campaign.experiment_spec_id,
                manifest_artifact,
                fp("d"),
                fp("e"),
                "historical-revision",
                NOW.isoformat(),
            ),
        )
        connection.execute(
            """
            INSERT INTO trials (
                trial_id, identity_schema, study_revision_id, instrument_id,
                membership_episode_start, membership_episode_end,
                membership_evidence_fingerprint, membership_evidence_artifact_id,
                parameter_configuration_fingerprint, registered_at,
                experiment_spec_id, disposition, disposition_at,
                reused_attempt_id, failure_classification, failure_message
            ) VALUES (?, 'fixture.v1', ?, 'instrument-reliance', ?, ?, ?, ?, ?, ?,
                      ?, 'EXECUTED', ?, NULL, NULL, NULL)
            """,
            (
                campaign.trial_id,
                campaign.study_revision_id,
                (NOW - timedelta(days=10)).isoformat(),
                (NOW - timedelta(days=1)).isoformat(),
                membership_artifact,
                membership_artifact,
                campaign.parameter_configuration_fingerprint,
                NOW.isoformat(),
                campaign.experiment_spec_id,
                NOW.isoformat(),
            ),
        )
        connection.execute(
            """
            INSERT INTO fixed_candidate_revisions (
                candidate_revision_id, study_revision_id, trial_id,
                experiment_spec_id, parameter_configuration_fingerprint,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                campaign.candidate_revision_id,
                campaign.study_revision_id,
                campaign.trial_id,
                campaign.experiment_spec_id,
                campaign.parameter_configuration_fingerprint,
                NOW.isoformat(),
            ),
        )
        policy_id = fp("f")
        connection.execute(
            "INSERT INTO qualification_policies VALUES (?, 1, '0', ?)",
            (policy_id, NOW.isoformat()),
        )
        connection.execute(
            "INSERT INTO qualification_policy_activations (policy_id, activated_at) VALUES (?, ?)",
            (policy_id, NOW.isoformat()),
        )
        connection.execute(
            """
            INSERT INTO qualification_decisions (
                decision_id, created_at, evaluator_version, policy_id,
                policy_version, threshold_text, study_revision_id, trial_id,
                candidate_revision_id, attempt_id, evidence_id,
                result_artifact_id, evidence_validity, criterion_outcome,
                outcome, profitable_trade_count, completed_trade_count,
                rate_numerator, rate_denominator, reason
            ) VALUES ('historical-sqlite', ?, 'fixture', ?, 1, '0', ?, ?, ?,
                      NULL, NULL, ?, 'VALID', 'SATISFIED', 'ELIGIBLE',
                      1, 1, 100, 1, 'fixture')
            """,
            (
                NOW.isoformat(),
                policy_id,
                campaign.study_revision_id,
                campaign.trial_id,
                campaign.candidate_revision_id,
                backtest_result_artifact,
            ),
        )
        connection.execute(
            """
            INSERT INTO candidate_wfa_decisions (
                decision_id, created_at, evaluator_version,
                study_revision_id, trial_id, candidate_revision_id,
                historical_qualification_decision_id,
                evaluator_repository_revision,
                dataset_reference_artifact_id, dataset_id, dataset_fingerprint,
                wfa_configuration_fingerprint, result_artifact_id,
                evidence_validity, wfa_verdict, outcome, reason
            ) VALUES (?, ?, 'fixture', ?, ?, ?, 'historical-sqlite',
                      'current-revision', ?, ?, ?, ?, ?,
                      'VALID', 'PASS', 'ELIGIBLE', 'fixture')
            """,
            (
                campaign.wfa_decision_id,
                NOW.isoformat(),
                campaign.study_revision_id,
                campaign.trial_id,
                campaign.candidate_revision_id,
                dataset_artifact,
                fp("0"),
                fp("1"),
                fp("2"),
                wfa_result_artifact,
            ),
        )
        connection.commit()


def _durable_session(campaign, *, session_id="paper-sqlite-1"):
    return PaperCampaignSession(
        session_id=session_id,
        campaign_id=campaign.campaign_id,
        created_at=NOW + timedelta(seconds=1),
        evaluator_repository_revision="current-revision",
        live_binding_id="angelone-reliance-v1",
        live_provider="angelone",
        live_provider_instrument_id="2885",
        live_provider_symbol="RELIANCE",
        state=PaperCampaignSessionState.CREATED,
    )


def test_sqlite_campaign_session_survives_reopen_and_restart_recovery(tmp_path):
    path = tmp_path / "research.sqlite3"
    campaign = _paper_campaign()
    _seed_campaign_parent_rows(path, campaign)
    store = SQLitePaperCampaignStore(path)
    store.create_campaign(campaign)
    session = _durable_session(campaign)
    store.register_session(session)
    store.mark_running_if_created(
        session.session_id,
        started_at=NOW + timedelta(seconds=2),
    )

    reopened = SQLitePaperCampaignStore(path)
    assert reopened.load_campaign(campaign.campaign_id) == campaign
    assert reopened.load_session(session.session_id).state is PaperCampaignSessionState.RUNNING
    assert reopened.recover_incomplete_sessions(terminal_at=NOW) == 1
    interrupted = SQLitePaperCampaignStore(path).load_session(session.session_id)
    assert interrupted.state is PaperCampaignSessionState.INTERRUPTED
    assert interrupted.terminal_snapshot_json is None
    assert interrupted.terminal_at == NOW + timedelta(seconds=2)


def test_sqlite_failed_empty_message_is_terminal_not_interrupted(tmp_path):
    path = tmp_path / "research.sqlite3"
    campaign = _paper_campaign()
    _seed_campaign_parent_rows(path, campaign)
    store = SQLitePaperCampaignStore(path)
    store.create_campaign(campaign)
    session = _durable_session(campaign)
    store.register_session(session)
    terminal = store.terminalize_session(
        session.session_id,
        state=PaperCampaignSessionState.FAILED,
        terminal_at=NOW + timedelta(seconds=3),
        terminal_snapshot_json='{"status":"FAILED"}',
        failure_type="TimeoutError",
        failure_message="",
    )

    assert terminal.state is PaperCampaignSessionState.FAILED
    assert terminal.failure_message == ""
    assert SQLitePaperCampaignStore(path).recover_incomplete_sessions(
        terminal_at=NOW + timedelta(minutes=1)
    ) == 0
    assert SQLitePaperCampaignStore(path).load_session(session.session_id) == terminal


def test_sqlite_terminal_evidence_is_append_only(tmp_path):
    path = tmp_path / "research.sqlite3"
    campaign = _paper_campaign()
    _seed_campaign_parent_rows(path, campaign)
    store = SQLitePaperCampaignStore(path)
    store.create_campaign(campaign)
    session = _durable_session(campaign)
    store.register_session(session)
    stopped = store.terminalize_session(
        session.session_id,
        state=PaperCampaignSessionState.STOPPED,
        terminal_at=NOW + timedelta(seconds=3),
        terminal_snapshot_json='{"status":"STOPPED"}',
        failure_type=None,
        failure_message=None,
    )
    repeated = store.terminalize_session(
        session.session_id,
        state=PaperCampaignSessionState.STOPPED,
        terminal_at=NOW + timedelta(seconds=3),
        terminal_snapshot_json='{"status":"STOPPED"}',
        failure_type=None,
        failure_message=None,
    )
    assert repeated == stopped
    with pytest.raises(ValueError, match="append-only"):
        store.terminalize_session(
            session.session_id,
            state=PaperCampaignSessionState.STOPPED,
            terminal_at=NOW + timedelta(seconds=4),
            terminal_snapshot_json='{"status":"STOPPED"}',
            failure_type=None,
            failure_message=None,
        )
    with pytest.raises(ValueError, match="append-only"):
        store.terminalize_session(
            session.session_id,
            state=PaperCampaignSessionState.FAILED,
            terminal_at=NOW + timedelta(seconds=5),
            terminal_snapshot_json='{"status":"FAILED"}',
            failure_type="RuntimeError",
            failure_message="changed",
        )


def test_sqlite_allows_only_one_active_session_and_freezes_start_time(tmp_path):
    path = tmp_path / "research.sqlite3"
    campaign = _paper_campaign()
    _seed_campaign_parent_rows(path, campaign)
    store = SQLitePaperCampaignStore(path)
    store.create_campaign(campaign)
    first = _durable_session(campaign, session_id="paper-active-1")
    store.register_session(first)
    started_at = NOW + timedelta(seconds=2)
    running = store.mark_running_if_created(
        first.session_id,
        started_at=started_at,
    )
    assert running.state is PaperCampaignSessionState.RUNNING
    assert store.mark_running_if_created(
        first.session_id,
        started_at=started_at,
    ) == running
    with pytest.raises(ValueError, match="start evidence is immutable"):
        store.mark_running_if_created(
            first.session_id,
            started_at=started_at + timedelta(seconds=1),
        )
    with pytest.raises(ValueError, match="already active"):
        store.register_session(
            replace(
                _durable_session(campaign, session_id="paper-active-2"),
                created_at=NOW + timedelta(seconds=3),
            )
        )


def test_api_startup_recovers_real_sqlite_paper_session(tmp_path, monkeypatch):
    path = tmp_path / "research.sqlite3"
    campaign = _paper_campaign()
    _seed_campaign_parent_rows(path, campaign)
    store = SQLitePaperCampaignStore(path)
    store.create_campaign(campaign)
    session = _durable_session(campaign)
    store.register_session(session)

    monkeypatch.setattr(
        api_main_module,
        "load_app_config",
        lambda: AppConfig(research_database_path=str(path)),
    )
    assert api_main_module.recover_stale_paper_campaign_sessions() == 1
    assert SQLitePaperCampaignStore(path).load_session(session.session_id).state is (
        PaperCampaignSessionState.INTERRUPTED
    )


class FakeRuntime:
    def __init__(self):
        self.started = True
        self.stopped = False

    def wait_until_started(self, timeout_seconds):
        return self.started

    def stop(self):
        self.stopped = True


def prepared_session(session_id="paper-session-1"):
    session = PaperTradingSession(
        session_id=session_id,
        strategy_name="fixture",
        symbol="RELIANCE",
        initial_capital=100000.0,
    )
    return PreparedLivePaperRun(
        session=session,
        runtime=FakeRuntime(),
        state_lock=RLock(),
        session_end=NOW + timedelta(hours=1),
        now=lambda: NOW,
        clock_interval_seconds=0.01,
    )


def test_start_prepared_registers_before_worker_and_terminalizes_after(monkeypatch):
    events = []
    prepared = prepared_session()

    def execute(value):
        events.append("execute")
        value.session.start()
        value.session.stop()

    monkeypatch.setattr(
        paper_app_module,
        "execute_prepared_live_paper_trading",
        execute,
    )
    application = PaperTradingApplication(
        lambda _request: prepared,
        worker_join_timeout_seconds=1.0,
    )
    application.start_prepared(
        prepared,
        before_start_callback=lambda _value: events.append("registered"),
        terminal_callback=lambda snapshot: events.append(snapshot.status),
    )
    application._current_handle.worker.join(timeout=1.0)
    assert events == ["registered", "execute", "STOPPED"]


def test_terminal_callback_failure_is_never_reported_as_durable_success(monkeypatch):
    prepared = prepared_session()

    def execute(value):
        value.session.start()
        value.session.stop()

    monkeypatch.setattr(
        paper_app_module,
        "execute_prepared_live_paper_trading",
        execute,
    )
    application = PaperTradingApplication(lambda _request: prepared)
    try:
        response = application.start_prepared(
            prepared,
            terminal_callback=lambda _snapshot: (_ for _ in ()).throw(
                RuntimeError("database unavailable")
            ),
        )
    except RuntimeError as error:
        assert "persistence callback" in str(error)
    else:
        assert response.status in {"CREATED", "RUNNING"}
        application._current_handle.worker.join(timeout=1.0)
        with pytest.raises(RuntimeError, match="persistence callback"):
            application.status()


@pytest.mark.parametrize("runtime_outcome", ["STOPPED", "FAILED"])
def test_terminal_persistence_failure_is_not_reclassified_as_worker_start_failure(
    monkeypatch,
    runtime_outcome,
):
    prepared = prepared_session(
        f"paper-terminal-persistence-{runtime_outcome.lower()}"
    )
    authority = SimpleNamespace()
    calls = []

    class InlineThread:
        def __init__(self, *, target, args, name, daemon):
            self._target = target
            self._args = args
            self._alive = False

        def start(self):
            self._alive = True
            try:
                self._target(*self._args)
            finally:
                self._alive = False

        def join(self, timeout=None):
            return None

        def is_alive(self):
            return self._alive

    def execute(value):
        value.session.start()
        if runtime_outcome == "STOPPED":
            value.session.stop()
            return
        failure = TimeoutError()
        value.session.fail(failure)
        raise failure

    class Service:
        def prepare_session(self, _campaign_id):
            return authority

        def register_prepared_session(self, _authority, *, session_id):
            calls.append(("register", session_id))

        def terminalize_snapshot(self, snapshot):
            calls.append(("terminal", snapshot.status))
            raise OSError("database unavailable")

        def fail_prepared_session(self, session_id, error):
            calls.append(("fail", session_id, type(error).__name__))

        def mark_session_running(self, session_id):
            calls.append(("running", session_id))

        def history(self, _campaign_id):
            return tuple(calls)

    monkeypatch.setattr(
        paper_app_module,
        "execute_prepared_live_paper_trading",
        execute,
    )
    monkeypatch.setattr(
        paper_app_module.threading,
        "Thread",
        InlineThread,
    )
    monkeypatch.setattr(
        qualified_app_module,
        "prepare_qualified_paper_trading",
        lambda *_args, **_kwargs: prepared,
    )

    paper_owner = PaperTradingApplication(
        lambda _request: prepared,
    )
    application = QualifiedPaperCampaignApplication(
        service=Service(),
        successor_retrieval_service=object(),
        app_config=AppConfig(
            paper_data_source=PaperDataSource.ANGELONE
        ),
        paper_application=paper_owner,
    )

    with pytest.raises(
        RuntimeError,
        match="terminal persistence callback failed",
    ):
        application.start_session("campaign-1")

    assert calls == [
        ("register", prepared.session.session_id),
        ("terminal", runtime_outcome),
    ]



def test_worker_start_failure_after_registration_uses_prestart_failure_terminalizer(
    monkeypatch,
):
    prepared = prepared_session("paper-worker-start-failure")
    authority = SimpleNamespace()
    calls = []

    class Service:
        def prepare_session(self, _campaign_id):
            return authority

        def register_prepared_session(self, _authority, *, session_id):
            calls.append(("register", session_id))

        def fail_prepared_session(self, session_id, error):
            calls.append(("fail", session_id, str(error)))

        def history(self, _campaign_id):
            return tuple(calls)

    class PaperApplication:
        def start_prepared(
            self,
            value,
            *,
            before_start_callback,
            terminal_callback,
        ):
            before_start_callback(value)
            raise RuntimeError("worker start failed")

    monkeypatch.setattr(
        qualified_app_module,
        "prepare_qualified_paper_trading",
        lambda *_args, **_kwargs: prepared,
    )
    application = QualifiedPaperCampaignApplication(
        service=Service(),
        successor_retrieval_service=object(),
        app_config=AppConfig(
            paper_data_source=PaperDataSource.ANGELONE
        ),
        paper_application=PaperApplication(),
    )

    with pytest.raises(RuntimeError, match="worker start failed"):
        application.start_session("campaign-1")

    assert calls == [
        ("register", prepared.session.session_id),
        ("fail", prepared.session.session_id, "worker start failed"),
    ]


def test_lifecycle_conflict_does_not_register_second_durable_session(monkeypatch):
    first = prepared_session("paper-session-1")
    second = prepared_session("paper-session-2")
    blocker = Event()

    def execute(value):
        value.session.start()
        blocker.wait(timeout=1.0)
        value.session.stop()

    monkeypatch.setattr(
        paper_app_module,
        "execute_prepared_live_paper_trading",
        execute,
    )
    application = PaperTradingApplication(lambda _request: first)
    application.start_prepared(first)
    called = []
    try:
        with pytest.raises(Exception, match="already active"):
            application.start_prepared(
                second,
                before_start_callback=lambda _value: called.append(True),
            )
    finally:
        blocker.set()
        application._current_handle.worker.join(timeout=1.0)
    assert called == []


def test_qualified_application_does_not_fabricate_running_from_created_response(
    monkeypatch,
):
    prepared = prepared_session("paper-created-observation")
    authority = SimpleNamespace()
    calls = []

    class Service:
        def prepare_session(self, _campaign_id):
            return authority

        def register_prepared_session(self, _authority, *, session_id):
            calls.append(("register", session_id))

        def terminalize_snapshot(self, snapshot):
            calls.append(("terminal", snapshot.status))

        def fail_prepared_session(self, session_id, error):
            calls.append(("fail", session_id, type(error).__name__))

        def mark_session_running(self, session_id):
            calls.append(("running", session_id))

        def history(self, _campaign_id):
            return tuple(calls)

    class PaperApplication:
        def start_prepared(
            self,
            value,
            *,
            before_start_callback,
            terminal_callback,
        ):
            before_start_callback(value)
            return SimpleNamespace(status="CREATED")

    monkeypatch.setattr(
        qualified_app_module,
        "prepare_qualified_paper_trading",
        lambda *_args, **_kwargs: prepared,
    )
    application = QualifiedPaperCampaignApplication(
        service=Service(),
        successor_retrieval_service=object(),
        app_config=AppConfig(paper_data_source=PaperDataSource.ANGELONE),
        paper_application=PaperApplication(),
    )

    history = application.start_session("campaign-1")

    assert history == (("register", prepared.session.session_id),)


def test_qualified_application_records_running_only_from_running_response(
    monkeypatch,
):
    prepared = prepared_session("paper-running-observation")
    authority = SimpleNamespace()
    calls = []

    class Service:
        def prepare_session(self, _campaign_id):
            return authority

        def register_prepared_session(self, _authority, *, session_id):
            calls.append(("register", session_id))

        def terminalize_snapshot(self, snapshot):
            calls.append(("terminal", snapshot.status))

        def fail_prepared_session(self, session_id, error):
            calls.append(("fail", session_id, type(error).__name__))

        def mark_session_running(self, session_id):
            calls.append(("running", session_id))

        def history(self, _campaign_id):
            return tuple(calls)

    class PaperApplication:
        def start_prepared(
            self,
            value,
            *,
            before_start_callback,
            terminal_callback,
        ):
            before_start_callback(value)
            return SimpleNamespace(status="RUNNING")

    monkeypatch.setattr(
        qualified_app_module,
        "prepare_qualified_paper_trading",
        lambda *_args, **_kwargs: prepared,
    )
    application = QualifiedPaperCampaignApplication(
        service=Service(),
        successor_retrieval_service=object(),
        app_config=AppConfig(paper_data_source=PaperDataSource.ANGELONE),
        paper_application=PaperApplication(),
    )

    history = application.start_session("campaign-1")

    assert history == (
        ("register", prepared.session.session_id),
        ("running", prepared.session.session_id),
    )


def test_runtime_timeout_empty_message_persists_failed_snapshot(tmp_path):
    fixture = service_fixture(tmp_path)
    campaign = fixture.service.create_campaign(fixture.candidate.candidate_revision_id)
    authority = fixture.service.prepare_session(campaign.campaign_id)
    fixture.service.register_prepared_session(authority, session_id="paper-session-1")
    session = PaperTradingSession(
        session_id="paper-session-1",
        strategy_name="fixture",
        symbol="RELIANCE",
        initial_capital=100000.0,
        status="FAILED",
        failure_type="TimeoutError",
        failure_message="",
    )
    terminal = fixture.service.terminalize_snapshot(session.snapshot())
    assert terminal.state is PaperCampaignSessionState.FAILED
    assert terminal.failure_type == "TimeoutError"
    assert terminal.failure_message == ""


def test_new_session_after_interruption_rechecks_current_authority(tmp_path):
    fixture = service_fixture(tmp_path)
    campaign = fixture.service.create_campaign(fixture.candidate.candidate_revision_id)
    authority = fixture.service.prepare_session(campaign.campaign_id)
    fixture.service.register_prepared_session(authority, session_id="paper-session-1")
    fixture.service.recover_after_application_restart()
    fixture.wfa_store.current_decision = replace(
        fixture.wfa,
        decision_id="wfa-decision-new",
    )
    with pytest.raises(QualifiedPaperAdmissionError, match="no longer matches"):
        fixture.service.prepare_session(campaign.campaign_id)


def _history_candles(count=40):
    start = NOW - timedelta(days=2)
    return tuple(
        SimpleNamespace(timestamp=start + timedelta(minutes=15 * index))
        for index in range(count)
    )


def test_qualified_runtime_composition_uses_exact_candidate_and_no_order_path(
    tmp_path,
    monkeypatch,
):
    fixture = service_fixture(tmp_path)
    campaign = fixture.service.create_campaign(fixture.candidate.candidate_revision_id)
    authority = fixture.service.prepare_session(campaign.campaign_id)
    retrieval_calls = []

    class Retrieval:
        def retrieve(self, context, request, **kwargs):
            retrieval_calls.append((context, request, kwargs))
            return SimpleNamespace(candles=_history_candles())

    broker_instances = []

    class Broker:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.order_calls = 0
            broker_instances.append(self)

        def login(self):
            return True

        def get_live_market_data_session(self):
            return "auth", "feed"

        def place_order(self, _order):
            self.order_calls += 1
            raise AssertionError("qualified Paper composition must not place broker orders")

    feed_calls = []
    feed_instances = []

    class Feed:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self.connected = False
            feed_calls.append(kwargs)
            feed_instances.append(self)

        def subscribe(self, on_candle, on_market_update=None):
            self.on_candle = on_candle
            self.on_market_update = on_market_update
            self.connected = True

        def reconnect(self):
            self.connected = True

        def close(self):
            self.connected = False

        def advance_time(self, _timestamp):
            return None

    monkeypatch.setattr(
        qualified_app_module.AngelOneConfig,
        "load_from_env",
        classmethod(
            lambda cls: AngelOneConfig(
                api_key="key",
                client_id="client",
                client_pin="pin",
                totp_secret="secret",
                exchange="NSE",
                symbol_token_map={"RELIANCE": "WRONG"},
            )
        ),
    )
    monkeypatch.setattr(qualified_app_module, "AngelOneBroker", Broker)
    monkeypatch.setattr(qualified_app_module, "AngelOneLiveCandleFeed", Feed)
    monkeypatch.chdir(tmp_path)

    utc_0430 = datetime(2026, 11, 5, 4, 30, tzinfo=timezone.utc)
    result = prepare_qualified_paper_trading(
        authority,
        successor_retrieval_service=Retrieval(),
        app_config=AppConfig(
            paper_data_source=PaperDataSource.ANGELONE,
            initial_capital=999999.0,
        ),
        now=lambda: utc_0430,
    )

    assert isinstance(result, PreparedLivePaperRun)
    assert retrieval_calls
    _, _, retrieval_kwargs = retrieval_calls[0]
    assert retrieval_kwargs["instrument_id"] == fixture.plan.instrument_id
    assert retrieval_kwargs["provider"] == "angelone"
    assert retrieval_kwargs["price_adjustment_basis"] is PriceAdjustmentBasis.RAW
    assert len(broker_instances) == 1
    broker_kwargs = broker_instances[0].kwargs
    assert broker_kwargs["paper_mode"] is True
    assert broker_kwargs["enable_historical_api"] is False
    assert broker_kwargs["config"].symbol_token_map == {"RELIANCE": "2885"}
    assert broker_instances[0].order_calls == 0
    assert feed_calls[0]["symbol"] == "RELIANCE"
    assert feed_calls[0]["timeframe"] == "15m"
    assert result.session.feed is feed_instances[0]
    assert result.session.strategy is authority.campaign_authority.execution_inputs.strategy
    assert result.session.runtime_context is authority.campaign_authority.execution_inputs.runtime_context
    assert result.session.dataset_context is authority.campaign_authority.execution_inputs.dataset_context
    assert result.session.initial_capital == fixture.plan.initial_capital
    assert result.session.execution_engine is not None
    assert result.session.execution_engine.portfolio_manager.snapshot().cash == fixture.plan.initial_capital
    normalized_now = result.now()
    assert normalized_now.utcoffset() == timedelta(hours=5, minutes=30)
    assert normalized_now.hour == 10


def test_history_remains_ordered_and_terminal_sessions_are_preserved(tmp_path):
    path = tmp_path / "research.sqlite3"
    campaign = _paper_campaign()
    _seed_campaign_parent_rows(path, campaign)
    store = SQLitePaperCampaignStore(path)
    store.create_campaign(campaign)
    first = _durable_session(campaign, session_id="paper-1")
    store.register_session(first)
    store.terminalize_session(
        first.session_id,
        state=PaperCampaignSessionState.STOPPED,
        terminal_at=NOW + timedelta(seconds=2),
        terminal_snapshot_json='{"status":"STOPPED"}',
        failure_type=None,
        failure_message=None,
    )
    second = replace(
        _durable_session(campaign, session_id="paper-2"),
        created_at=NOW + timedelta(seconds=3),
    )
    store.register_session(second)
    history = SQLitePaperCampaignStore(path).load_history(campaign.campaign_id)
    assert history is not None
    assert [value.session_id for value in history.sessions] == ["paper-1", "paper-2"]
    assert history.sessions[0].state is PaperCampaignSessionState.STOPPED
    assert history.sessions[1].state is PaperCampaignSessionState.CREATED

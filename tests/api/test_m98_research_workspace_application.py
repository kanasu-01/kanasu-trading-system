from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace

NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)

import pytest

from api.models.research_workspace_models import WorkspaceBacktestRunRequest
from api.research_workspace_application import (
    ResearchWorkspaceApplication,
    ResearchWorkspaceConflict,
)
from api.qualified_paper_campaign_application import QualifiedPaperCampaignApplication
from core.research.qualified_paper_campaign_service import (
    QualifiedPaperAdmissionError,
    QualifiedPaperCampaignService,
)
from core.config.app_config import AppConfig
from core.entities.candle import Candle
from core.entities.instrument import Instrument
from core.market_data.historical_retrieval import HistoricalFetchResult
from core.market_data.instrument_registry import StaticInstrumentRegistry
from core.market_data.provider_instrument_binding import ProviderInstrumentBinding
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.research.models.registered_study import TrialDisposition
from core.research.models.qualification import EvidenceValidity, QualificationOutcome
from core.research.registered_trial_execution_plan import (
    RegisteredTrialExecutionPlanResolver,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.software_identity import SoftwareIdentity
from core.research.sqlite_qualification_store import SQLiteQualificationStore
from core.research.sqlite_research_catalog_store import SQLiteResearchCatalogStore
from core.research.sqlite_research_evidence_store import SQLiteResearchEvidenceStore
from core.research.successor_historical_retrieval import (
    SuccessorHistoricalRetrievalService,
)


IST = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
START = datetime(2026, 1, 5, 9, 15, tzinfo=IST)
END = START + timedelta(minutes=90)
REVISION = "035ad39c73e69e647dbf492c999424f78c9c87bc"


class StaticIdentity:
    def resolve(self):
        return SoftwareIdentity(
            repository_revision=REVISION,
            worktree_clean=True,
        )


class Compatibility:
    def check(self, **_kwargs):
        return type("Result", (), {"compatible": True})()


class WfaStore:
    def load_current_decision(self, _candidate_revision_id):
        return None

    def load_current_decision_if_historical_current(self, _candidate_revision_id):
        return None


class QualifiedPaper:
    def list_campaigns_for_candidate(self, _candidate_revision_id):
        return ()


class Provider:
    def fetch(self, context, request, *, provider_binding):
        expected = {"RELIANCE": "2885", "TCS": "11536"}
        assert provider_binding.provider_instrument_id == expected[context.symbol]
        candles = tuple(
            Candle(
                timestamp=START + timedelta(minutes=15 * index),
                open=float(value),
                high=float(value + 1),
                low=float(value - 1),
                close=float(value),
                volume=1000.0,
            )
            for index, value in enumerate([100, 102, 104, 103, 101, 100])
        )
        return HistoricalFetchResult(
            candles=candles,
            coverage=(request,),
        )


def registry():
    return StaticInstrumentRegistry(
        instruments=(
            Instrument(
                instrument_id="NSE-EQ-RELIANCE",
                symbol="RELIANCE",
                exchange="NSE",
                segment="EQ",
                tick_size=0.05,
                lot_size=1,
            ),
            Instrument(
                instrument_id="NSE-EQ-TCS",
                symbol="TCS",
                exchange="NSE",
                segment="EQ",
                tick_size=0.05,
                lot_size=1,
            ),
        ),
        provider_bindings=(
            ProviderInstrumentBinding(
                binding_id="angelone-nse-eq-reliance-v1",
                instrument_id="NSE-EQ-RELIANCE",
                provider="angelone",
                provider_instrument_id="2885",
                provider_exchange="NSE",
                provider_segment="nse_cm",
                provider_symbol="RELIANCE",
            ),
            ProviderInstrumentBinding(
                binding_id="angelone-nse-eq-tcs-v1",
                instrument_id="NSE-EQ-TCS",
                provider="angelone",
                provider_instrument_id="11536",
                provider_exchange="NSE",
                provider_segment="nse_cm",
                provider_symbol="TCS",
            ),
        ),
    )


def application(tmp_path):
    config = AppConfig(
        research_database_path=str(tmp_path / "research.sqlite3"),
        research_artifact_root=str(tmp_path / "artifacts"),
        historical_database_path=str(tmp_path / "history.sqlite3"),
        research_max_workers=1,
    )
    catalog = SQLiteResearchCatalogStore(config.research_database_path)
    artifacts = ContentAddressedResearchArtifactStore(
        config.research_artifact_root
    )
    evidence = SQLiteResearchEvidenceStore(config.research_database_path)
    qualification = SQLiteQualificationStore(config.research_database_path)
    plan_resolver = RegisteredTrialExecutionPlanResolver(
        catalog_store=catalog,
        artifact_store=artifacts,
    )
    retrieval = SuccessorHistoricalRetrievalService(
        store=SQLiteCandleStore(config.historical_database_path),
        provider=Provider(),
        registry=registry(),
    )
    return ResearchWorkspaceApplication(
        app_config=config,
        instrument_registry=registry(),
        catalog_store=catalog,
        artifact_store=artifacts,
        evidence_store=evidence,
        qualification_store=qualification,
        wfa_store=WfaStore(),
        plan_resolver=plan_resolver,
        retrieval_service=retrieval,
        software_identity_provider=StaticIdentity(),
        compatibility_checker=Compatibility(),
        qualified_paper_application=QualifiedPaper(),
    )


def test_registered_workspace_backtest_runs_real_m94_path_and_reuses_identity(
    tmp_path,
):
    app = application(tmp_path)
    study = app.create_study("SMA Research")

    request = WorkspaceBacktestRunRequest(
        study_id=study.study_id,
        symbol="RELIANCE",
        timeframe="15m",
        strategy_id="sma_crossover",
        start=START,
        end=END,
        timezone="Asia/Kolkata",
        initial_capital=100000,
        strategy_params={"fast_period": 1, "slow_period": 2},
    )

    first = app.run_backtest(request)
    second = app.run_backtest(request)

    assert first.study_revision_id == second.study_revision_id
    assert first.trial_id == second.trial_id
    assert first.evidence_status == "ACCEPTED"
    assert first.summary.completed_trade_count == 1

    state = app.study_strategies(study.study_id)
    assert len(state.strategies) == 1
    assert state.strategies[0].trial_disposition in {
        TrialDisposition.EXECUTED.value,
        TrialDisposition.REUSED.value,
    }
    assert state.strategies[0].strategy_label == "SMA Crossover 1/2"


def test_unknown_symbol_fails_closed_without_guessing_provider_token(tmp_path):
    app = application(tmp_path)
    study = app.create_study("Unknown symbol")

    request = WorkspaceBacktestRunRequest(
        study_id=study.study_id,
        symbol="UNKNOWN",
        timeframe="15m",
        strategy_id="sma_crossover",
        start=START,
        end=END,
        timezone="Asia/Kolkata",
        initial_capital=100000,
        strategy_params={"fast_period": 1, "slow_period": 2},
    )

    try:
        app.run_backtest(request)
    except ValueError:
        pass
    else:
        raise AssertionError("unknown instrument must fail closed")


def test_registered_workspace_accepts_non_reliance_registry_symbol(tmp_path):
    app = application(tmp_path)
    study = app.create_study("TCS Research")

    response = app.run_backtest(
        WorkspaceBacktestRunRequest(
            study_id=study.study_id,
            symbol="TCS",
            timeframe="15m",
            strategy_id="sma_crossover",
            start=START,
            end=END,
            timezone="Asia/Kolkata",
            initial_capital=100000,
            strategy_params={"fast_period": 1, "slow_period": 2},
        )
    )

    assert response.symbol == "TCS"
    assert response.evidence_status == "ACCEPTED"


def test_saved_registered_backtest_result_reopens_without_rerun(tmp_path):
    app = application(tmp_path)
    study = app.create_study("Reopen Result")
    request = WorkspaceBacktestRunRequest(
        study_id=study.study_id,
        symbol="RELIANCE",
        timeframe="15m",
        strategy_id="sma_crossover",
        start=START,
        end=END,
        timezone="Asia/Kolkata",
        initial_capital=100000,
        strategy_params={"fast_period": 1, "slow_period": 2},
    )

    first = app.run_backtest(request)
    reopened = app.load_backtest_result(first.trial_id)

    assert reopened.trial_id == first.trial_id
    assert reopened.evidence_id == first.evidence_id
    assert reopened.run_id == first.run_id
    assert reopened.summary == first.summary


def test_concurrent_policy_supersession_is_reported_without_misattribution(tmp_path):
    app = application(tmp_path)
    study = app.create_study("Policy Race")
    for fast, slow in ((1, 2), (2, 3)):
        app.run_backtest(
            WorkspaceBacktestRunRequest(
                study_id=study.study_id,
                symbol="RELIANCE",
                timeframe="15m",
                strategy_id="sma_crossover",
                start=START,
                end=END,
                timezone="Asia/Kolkata",
                initial_capital=100000,
                strategy_params={"fast_period": fast, "slow_period": slow},
            )
        )

    calls = 0

    def evaluate(_trial_id, *, evaluated_at):
        nonlocal calls
        calls += 1
        current = app.qualification_store.load_active_policy()
        assert current is not None
        newer, _ = app.qualification_store.ensure_active_policy_threshold(
            Decimal("100"),
            changed_at=evaluated_at + timedelta(microseconds=1),
            expected_active_policy_id=current.policy_id,
        )
        return SimpleNamespace(
            outcome=QualificationOutcome.REJECTED,
            evidence_validity=EvidenceValidity.VALID,
            decision_id="decision-newer-policy",
            candidate_revision_id=None,
            policy_id=newer.policy_id,
            policy_version=newer.version,
            threshold_text="100",
            reason="evaluated by newer policy",
        )

    app.qualification_service.evaluate_selected_trial = evaluate

    response = app.qualify_study(study.study_id, Decimal("0"))

    assert response.policy.threshold_pct == "0"
    assert response.policy_current is False
    assert response.results[0].outcome == "POLICY_SUPERSEDED"
    assert response.results[0].decision_threshold_pct == "100"
    assert response.results[1].outcome == "POLICY_SUPERSEDED"
    assert response.results[1].decision_id is None
    assert calls == 1


def test_qualified_paper_application_exposes_durable_active_session():
    marker = object()

    class Service:
        def active_session(self):
            return marker

    app = QualifiedPaperCampaignApplication(
        service=Service(),
        successor_retrieval_service=object(),
        app_config=AppConfig(),
        paper_application=object(),
    )

    assert app.active_session() is marker


def test_qualified_stop_passes_exact_active_session_identity_to_process_owner():
    active = SimpleNamespace(
        campaign_id="campaign-a",
        session_id="session-a",
    )

    class Service:
        def active_session(self):
            return active

        def history(self, campaign_id):
            assert campaign_id == "campaign-a"
            return "history-a"

    class PaperOwner:
        expected_session_id = None

        def status(self):
            return SimpleNamespace(
                snapshot=SimpleNamespace(
                    session_id="session-a"
                )
            )

        def stop(self, *, expected_session_id=None):
            self.expected_session_id = expected_session_id

    owner = PaperOwner()
    app = QualifiedPaperCampaignApplication(
        service=Service(),
        successor_retrieval_service=object(),
        app_config=AppConfig(),
        paper_application=owner,
    )

    assert (
        app.stop_session(
            "campaign-a",
            expected_session_id="session-a",
        )
        == "history-a"
    )
    assert owner.expected_session_id == "session-a"

    with pytest.raises(Exception):
        app.stop_session(
            "campaign-a",
            expected_session_id="session-old",
        )
    assert owner.expected_session_id == "session-a"


def test_stale_policy_observation_cannot_reactivate_old_global_threshold(tmp_path):
    app = application(tmp_path)
    study = app.create_study("Policy precondition")

    first = app.qualify_study(
        study.study_id,
        Decimal("50"),
        None,
    )
    second, _ = app.qualification_store.ensure_active_policy_threshold(
        Decimal("60"),
        changed_at=NOW + timedelta(seconds=1),
        expected_active_policy_id=first.policy.policy_id,
    )

    with pytest.raises(
        ResearchWorkspaceConflict,
        match="changed since caller observation",
    ):
        app.qualify_study(
            study.study_id,
            Decimal("50"),
            first.policy.policy_id,
        )

    active = app.qualification_store.load_active_policy()
    assert active is not None
    assert active.policy_id == second.policy_id
    assert active.net_profitable_trade_rate_threshold_pct == Decimal("60")


def test_qualification_operational_failure_does_not_abort_next_strategy(tmp_path):
    app = application(tmp_path)
    study = app.create_study("Partial Qualification")
    for fast, slow in ((1, 2), (2, 3)):
        app.run_backtest(
            WorkspaceBacktestRunRequest(
                study_id=study.study_id,
                symbol="RELIANCE",
                timeframe="15m",
                strategy_id="sma_crossover",
                start=START,
                end=END,
                timezone="Asia/Kolkata",
                initial_capital=100000,
                strategy_params={"fast_period": fast, "slow_period": slow},
            )
        )

    original = app.qualification_service.evaluate_selected_trial
    calls = 0

    def evaluate(trial_id, *, evaluated_at):
        nonlocal calls
        calls += 1
        if calls == 1:
            from core.research.qualification_service import QualificationOperationalError
            raise QualificationOperationalError("temporary store failure")
        return original(trial_id, evaluated_at=evaluated_at)

    app.qualification_service.evaluate_selected_trial = evaluate
    response = app.qualify_study(study.study_id, Decimal("0"))

    assert len(response.results) == 2
    assert response.results[0].outcome == "OPERATIONAL_ERROR"
    assert response.results[1].outcome in {"ELIGIBLE", "REJECTED", "INSUFFICIENT", "INVALID"}
    assert calls == 2


def test_historically_eligible_strategy_is_visible_as_pending_before_wfa(tmp_path):
    app = application(tmp_path)
    study = app.create_study("Pending WFA")
    backtest = app.run_backtest(
        WorkspaceBacktestRunRequest(
            study_id=study.study_id,
            symbol="RELIANCE",
            timeframe="15m",
            strategy_id="sma_crossover",
            start=START,
            end=END,
            timezone="Asia/Kolkata",
            initial_capital=100000,
            strategy_params={"fast_period": 1, "slow_period": 2},
        )
    )

    qualification = app.qualify_study(study.study_id, Decimal("0"))
    assert qualification.results[0].outcome == "ELIGIBLE"

    state = app.wfa_state(study.study_id)

    assert len(state.strategies) == 1
    assert state.strategies[0].trial_id == backtest.trial_id
    assert state.strategies[0].outcome == "PENDING"
    assert state.strategies[0].evidence_validity == "NOT_EVALUATED"
    assert state.strategies[0].verdict is None



def test_superseded_wfa_is_presented_as_pending_after_requalification(tmp_path):
    app = application(tmp_path)
    study = app.create_study("Stale WFA")
    backtest = app.run_backtest(
        WorkspaceBacktestRunRequest(
            study_id=study.study_id,
            symbol="RELIANCE",
            timeframe="15m",
            strategy_id="sma_crossover",
            start=START,
            end=END,
            timezone="Asia/Kolkata",
            initial_capital=100000,
            strategy_params={"fast_period": 1, "slow_period": 2},
        )
    )
    qualified = app.qualify_study(study.study_id, Decimal("0"))
    historical = app.qualification_store.load_current_decision(backtest.trial_id)
    assert historical is not None
    assert historical.candidate_revision_id is not None

    app.wfa_store = SimpleNamespace(
        load_current_decision_if_historical_current=lambda _candidate_id: None
    )

    state = app.wfa_state(study.study_id)

    assert qualified.results[0].outcome == "ELIGIBLE"
    assert len(state.strategies) == 1
    assert state.strategies[0].outcome == "PENDING"
    assert state.strategies[0].verdict is None


def test_unexpected_qualification_exception_is_operational_not_invalid(tmp_path):
    app = application(tmp_path)
    study = app.create_study("Qualification Fault")
    app.run_backtest(
        WorkspaceBacktestRunRequest(
            study_id=study.study_id,
            symbol="RELIANCE",
            timeframe="15m",
            strategy_id="sma_crossover",
            start=START,
            end=END,
            timezone="Asia/Kolkata",
            initial_capital=100000,
            strategy_params={"fast_period": 1, "slow_period": 2},
        )
    )

    def fail(*_args, **_kwargs):
        raise RuntimeError("unexpected evaluator infrastructure failure")

    app.qualification_service.evaluate_selected_trial = fail
    response = app.qualify_study(study.study_id, Decimal("0"))

    assert response.results[0].outcome == "OPERATIONAL_ERROR"
    assert response.results[0].evidence_validity == "UNKNOWN"


def test_unexpected_wfa_exception_is_operational_not_invalid(tmp_path):
    app = application(tmp_path)
    study = app.create_study("WFA Fault")
    app.run_backtest(
        WorkspaceBacktestRunRequest(
            study_id=study.study_id,
            symbol="RELIANCE",
            timeframe="15m",
            strategy_id="sma_crossover",
            start=START,
            end=END,
            timezone="Asia/Kolkata",
            initial_capital=100000,
            strategy_params={"fast_period": 1, "slow_period": 2},
        )
    )
    app.qualify_study(study.study_id, Decimal("0"))

    def fail(_study_revision_id):
        raise RuntimeError("unexpected WFA infrastructure failure")

    app.wfa_service.evaluate_study_revision = fail
    active_policy = app.qualification_store.load_active_policy()
    assert active_policy is not None
    response = app.run_wfa(
        study.study_id,
        active_policy.policy_id,
    )

    assert response.strategies[0].outcome == "OPERATIONAL_ERROR"
    assert response.strategies[0].evidence_validity == "UNKNOWN"


def test_send_to_paper_preserves_partial_results_when_one_candidate_fails(tmp_path):
    app = application(tmp_path)
    study = app.create_study("Partial Paper")
    first_id = "sha256:" + "1" * 64
    second_id = "sha256:" + "2" * 64
    app.wfa_state = lambda _study_id: SimpleNamespace(
        strategies=[
            SimpleNamespace(
                candidate_revision_id=first_id,
                decision_id="wfa-1",
                strategy_label="SMA Crossover 20/50",
                outcome="ELIGIBLE",
                verdict="PASS",
            ),
            SimpleNamespace(
                candidate_revision_id=second_id,
                decision_id="wfa-2",
                strategy_label="SMA Crossover 25/55",
                outcome="ELIGIBLE",
                verdict="PASS",
            ),
        ]
    )

    calls = []

    def create_or_reuse(candidate_revision_id):
        calls.append(candidate_revision_id)
        if candidate_revision_id == first_id:
            raise PermissionError("campaign store unavailable")
        return SimpleNamespace(campaign_id="paper-campaign-2"), True

    app.qualified_paper_application.create_or_reuse_campaign = create_or_reuse
    response = app.send_to_paper(
        study.study_id,
        ["wfa-1", "wfa-2"],
    )

    assert calls == [first_id, second_id]
    assert [item.outcome for item in response.campaigns] == [
        "OPERATIONAL_ERROR",
        "READY",
    ]
    assert response.campaigns[1].campaign_id == "paper-campaign-2"



def test_send_to_paper_preserves_preflight_operational_error(tmp_path):
    app = application(tmp_path)
    study = app.create_study("Paper Preflight Error")
    app.wfa_state = lambda _study_id: SimpleNamespace(
        strategies=[
            SimpleNamespace(
                candidate_revision_id=None,
                decision_id=None,
                strategy_label="Revision 1",
                outcome="OPERATIONAL_ERROR",
                verdict=None,
                reason="candidate authority could not be read",
            )
        ]
    )

    app.qualified_paper_application.create_or_reuse_campaign = (
        lambda _candidate_revision_id: (_ for _ in ()).throw(
            AssertionError("preflight operational error must not attempt campaign creation")
        )
    )

    response = app.send_to_paper(study.study_id, [])

    assert len(response.campaigns) == 1
    assert response.campaigns[0].candidate_revision_id is None
    assert response.campaigns[0].outcome == "OPERATIONAL_ERROR"
    assert "could not be read" in response.campaigns[0].reason

def test_start_does_not_implicitly_retry_failed_trial(tmp_path):
    app = application(tmp_path)
    request = WorkspaceBacktestRunRequest(
        study_id="study-failed",
        symbol="RELIANCE",
        timeframe="15m",
        strategy_id="sma_crossover",
        start=START,
        end=END,
        timezone="Asia/Kolkata",
        initial_capital=100000,
        strategy_params={"fast_period": 1, "slow_period": 2},
    )
    app._register_backtest = lambda _request: (
        SimpleNamespace(study_revision_id="sha256:" + "a" * 64),
        SimpleNamespace(trial_id="sha256:" + "b" * 64),
    )
    failed = SimpleNamespace(
        trial_id="sha256:" + "b" * 64,
        disposition=TrialDisposition.FAILED,
    )
    app.catalog_store = SimpleNamespace(load_trial=lambda _trial_id: failed)
    app._retry_trial = lambda _trial_id: (_ for _ in ()).throw(
        AssertionError("Start must not invoke Retry")
    )

    try:
        app.run_backtest(request)
    except ResearchWorkspaceConflict as error:
        assert "explicit Retry" in str(error)
    else:
        raise AssertionError("failed Trial Start must require explicit Retry")


def _bare_workspace_for_generation_tests():
    app = object.__new__(ResearchWorkspaceApplication)
    app.clock = lambda: NOW
    return app


def test_study_strategy_projection_conflicts_if_policy_generation_changes():
    app = _bare_workspace_for_generation_tests()
    app._study = lambda _study_id: object()
    app._active_policy_id = lambda: "policy-b"
    app.qualification_store = SimpleNamespace(
        load_study_current_authority=lambda _study_id: ("policy-a", ()),
    )
    app.catalog_store = SimpleNamespace(
        list_study_revisions=lambda _study_id: (),
    )

    with pytest.raises(ResearchWorkspaceConflict, match="QualificationPolicy changed"):
        app.study_strategies("study-1")


def test_wfa_projection_conflicts_if_policy_generation_changes():
    app = _bare_workspace_for_generation_tests()
    app._study = lambda _study_id: object()
    app._active_policy_id = lambda: "policy-b"
    app.qualification_store = SimpleNamespace(
        load_study_current_authority=lambda _study_id: ("policy-a", ()),
    )
    app.catalog_store = SimpleNamespace(
        list_study_revisions=lambda _study_id: (),
    )

    with pytest.raises(ResearchWorkspaceConflict, match="QualificationPolicy changed"):
        app.wfa_state("study-1")


def test_run_wfa_rejects_stale_observed_policy_before_evaluator():
    app = _bare_workspace_for_generation_tests()
    app._study = lambda _study_id: object()
    app._active_policy_id = lambda: "policy-new"
    app.catalog_store = SimpleNamespace(
        list_study_revisions=lambda _study_id: (
            SimpleNamespace(study_revision_id="revision-1", revision_number=1),
        ),
    )
    app.wfa_service = SimpleNamespace(
        evaluate_study_revision=lambda _revision_id: (_ for _ in ()).throw(
            AssertionError("stale WFA intent must not evaluate")
        )
    )

    with pytest.raises(ResearchWorkspaceConflict, match="caller observation"):
        app.run_wfa("study-1", "policy-old")


def test_send_to_paper_rejects_unobserved_new_pass_decision():
    app = _bare_workspace_for_generation_tests()
    app._study = lambda _study_id: object()
    app.wfa_state = lambda _study_id: SimpleNamespace(
        strategies=(
            SimpleNamespace(
                decision_id="wfa-new",
                outcome="ELIGIBLE",
                verdict="PASS",
            ),
        ),
    )
    app.qualified_paper_application = SimpleNamespace(
        create_or_reuse_campaign=lambda _candidate_id: (_ for _ in ()).throw(
            AssertionError("stale send intent must not create campaign")
        )
    )

    with pytest.raises(ResearchWorkspaceConflict, match="decision set changed"):
        app.send_to_paper("study-1", ["wfa-old"])


def test_cand010_run_wfa_passes_exact_observed_qualification_set():
    app = _bare_workspace_for_generation_tests()
    app._study = lambda _study_id: object()
    app._require_policy_generation = lambda _expected: None
    revision = SimpleNamespace(
        study_revision_id="revision-1",
        revision_number=1,
    )
    observed = (
        SimpleNamespace(
            study_revision_id="revision-1",
            trial_id="trial-1",
            candidate_revision_id="candidate-1",
            outcome=QualificationOutcome.ELIGIBLE,
        ),
    )
    app.catalog_store = SimpleNamespace(
        list_study_revisions=lambda _study_id: (revision,),
    )
    app.qualification_store = SimpleNamespace(
        list_current_eligible_decisions=lambda _revision_id: observed,
    )
    seen = []

    def evaluate(_revision_id, *, observed_eligible_decisions=None):
        seen.append(observed_eligible_decisions)
        return ()

    app.wfa_service = SimpleNamespace(
        evaluate_study_revision=evaluate,
    )

    response = app.run_wfa("study-1", "policy-1")

    assert seen == [observed]
    assert response.strategies == []


def test_cand010_send_to_paper_binds_exact_observed_wfa_decision():
    app = _bare_workspace_for_generation_tests()
    app._study = lambda _study_id: object()
    strategy = SimpleNamespace(
        decision_id="wfa-observed",
        candidate_revision_id="candidate-1",
        strategy_label="SMA",
        outcome="ELIGIBLE",
        verdict="PASS",
        reason="ready",
    )
    app.wfa_state = lambda _study_id: SimpleNamespace(
        strategies=(strategy,),
    )
    seen = []

    def create(candidate_id, *, expected_wfa_decision_id=None):
        seen.append((candidate_id, expected_wfa_decision_id))
        return SimpleNamespace(campaign_id="campaign-1"), True

    app.qualified_paper_application = SimpleNamespace(
        create_or_reuse_campaign=create,
    )

    response = app.send_to_paper(
        "study-1",
        ["wfa-observed"],
    )

    assert seen == [("candidate-1", "wfa-observed")]
    assert response.campaigns[0].outcome == "READY"


def test_cand010_qualified_paper_rejects_unseen_wfa_substitution():
    service = QualifiedPaperCampaignService.__new__(
        QualifiedPaperCampaignService
    )
    service.qualification_store = SimpleNamespace(
        load_candidate_revision=lambda _candidate_id: object(),
    )
    service.wfa_store = SimpleNamespace(
        load_current_decision=lambda _candidate_id: SimpleNamespace(
            decision_id="wfa-new",
        ),
    )

    with pytest.raises(
        QualifiedPaperAdmissionError,
        match="changed since caller observation",
    ):
        service._resolve_candidate_authority(
            "candidate-1",
            expected_wfa_decision_id="wfa-old",
        )


def test_paper_projection_conflicts_if_authority_generation_changes():
    app = _bare_workspace_for_generation_tests()
    app._study = lambda _study_id: object()
    campaign = SimpleNamespace(campaign_id="campaign-1")
    app.qualified_paper_application = SimpleNamespace(
        list_campaigns_for_study=lambda _study_id: (campaign,),
    )
    generations = iter((("policy-a", ()), ("policy-b", ())))
    app._paper_authority_generation = lambda _campaigns: next(generations)
    app._campaign_response = lambda _study_id, _campaign: SimpleNamespace()

    with pytest.raises(ResearchWorkspaceConflict, match="Paper authority changed"):
        app.paper_state("study-1")

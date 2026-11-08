"""M9.8 application composition for the complete research workspace."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from uuid import uuid4

from api.models.backtest_models import (
    BacktestEquityPoint,
    BacktestSummaryResponse,
    BacktestTradeResponse,
)
from api.models.research_workspace_models import (
    ResearchWorkspaceConfigResponse,
    WorkspaceBacktestRunRequest,
    WorkspaceBacktestRunResponse,
    WorkspacePaperCampaignListResponse,
    WorkspacePaperCampaignResponse,
    WorkspacePaperHistoryResponse,
    WorkspacePaperSendItemResponse,
    WorkspacePaperSendResponse,
    WorkspacePaperSessionResponse,
    WorkspaceQualificationItemResponse,
    WorkspaceQualificationPolicyResponse,
    WorkspaceQualificationResponse,
    WorkspaceStrategyListResponse,
    WorkspaceStrategyState,
    WorkspaceStudyResponse,
    WorkspaceWfaItemResponse,
    WorkspaceWfaMetricsResponse,
    WorkspaceWfaResponse,
)
from api.paper_trading_application import paper_trading_application
from api.qualified_paper_campaign_application import (
    QualifiedPaperCampaignApplication,
    build_qualified_paper_campaign_application,
)
from core.research.qualified_paper_campaign_service import (
    QualifiedPaperAdmissionError,
    QualifiedPaperOperationalError,
)
from core.backtest.backtest_result import BacktestResult
from core.backtest.bar_record import BarRecord
from core.backtest.performance_metrics import PerformanceMetrics
from core.broker.broker_factory import create_angelone_broker
from core.config.app_config import AppConfig
from core.config.backtest_config import BacktestConfig
from core.config.backtest_economic_policy import BacktestEconomicPolicy
from core.config.execution_config import ExecutionConfig
from core.config.loaders import load_app_config
from core.entities.trade import Trade
from core.market_data.binding_aware_historical_feed_provider import (
    BindingAwareHistoricalFeedProvider,
)
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_feed import HistoricalFeed
from core.market_data.instrument_registry import StaticInstrumentRegistry
from core.market_data.instrument_registry_loader import load_instrument_registry
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.research.backtest_financial_configuration import (
    effective_backtest_financial_configuration,
)
from core.research.backtest_research_orchestrator import BacktestResearchOrchestrator
from core.research.candidate_wfa_service import (
    CandidateWfaOperationalError,
    CandidateWfaService,
)
from core.research.claimed_research_job_executor import ClaimedResearchJobExecutor
from core.research.claimed_trial_execution_inputs import (
    ClaimedTrialExecutionInputs,
)
from core.research.executable_compatibility import (
    GitHistoricalExecutableCompatibilityChecker,
)
from core.research.models.dataset import PriceAdjustmentBasis
from core.research.models.qualification import QualificationOutcome
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    Study,
    TrialDisposition,
)
from core.research.models.research_evidence import ResearchEvidenceStatus
from core.research.models.universe import (
    UniverseDefinition,
    UniverseQuality,
    UniverseSnapshot,
)
from core.research.qualification_service import (
    QualificationOperationalError,
    QualificationService,
)
from core.research.registered_study_registration import (
    RegisteredStudyRegistrationService,
)
from core.research.registered_trial_execution_plan import (
    RegisteredTrialExecutionPlan,
    RegisteredTrialExecutionPlanResolver,
)
from core.research.models.wfa_qualification import (
    WfaQualificationOutcome,
    decode_candidate_wfa_result_bytes,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.research_job_queue import ResearchJobQueueService
from core.research.software_identity import GitSoftwareIdentityProvider
from core.research.sqlite_candidate_wfa_store import SQLiteCandidateWfaStore
from core.research.sqlite_paper_campaign_store import SQLitePaperCampaignStore
from core.research.sqlite_qualification_store import (
    QualificationPolicyConcurrencyConflict,
    SQLiteQualificationStore,
)
from core.research.sqlite_research_catalog_store import SQLiteResearchCatalogStore
from core.research.sqlite_research_evidence_store import SQLiteResearchEvidenceStore
from core.research.study_aggregation import StudyAggregationService
from core.research.successor_backtest_research_coordinator import (
    SuccessorBacktestResearchCoordinator,
)
from core.research.successor_historical_retrieval import (
    SuccessorHistoricalRetrievalService,
)
from core.runtime.backtest_runtime import execute_backtest_candles
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.strategy_factory import create_registered_research_strategy


STRATEGY_TO_PROCEDURE = {
    "sma_crossover": "sma-crossover-v1",
}
PROCEDURE_TO_STRATEGY = {
    value: key for key, value in STRATEGY_TO_PROCEDURE.items()
}

_RETRYABLE = {
    TrialDisposition.FAILED,
    TrialDisposition.CANCELLED,
    TrialDisposition.INTERRUPTED,
}


class ResearchWorkspaceNotFound(LookupError):
    pass


class ResearchWorkspaceConflict(RuntimeError):
    pass


class ResearchWorkspaceOperationalError(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _LazyBindingAwareProvider:
    """Construct AngelOne only when a binding-backed fetch is actually needed."""

    def __init__(self, app_config: AppConfig):
        self.app_config = app_config
        self._provider = None

    def fetch(self, context, request, *, provider_binding):
        if self._provider is None:
            broker = create_angelone_broker(
                paper_mode=True,
                enable_historical_api=True,
            )
            feed = HistoricalFeed(
                broker,
                request_delay_sec=self.app_config.historical_request_delay_sec,
            )
            self._provider = BindingAwareHistoricalFeedProvider(feed)
        return self._provider.fetch(
            context,
            request,
            provider_binding=provider_binding,
        )


class ResearchWorkspaceApplication:
    def __init__(
        self,
        *,
        app_config: AppConfig,
        instrument_registry: StaticInstrumentRegistry,
        catalog_store: SQLiteResearchCatalogStore,
        artifact_store: ContentAddressedResearchArtifactStore,
        evidence_store: SQLiteResearchEvidenceStore,
        qualification_store: SQLiteQualificationStore,
        wfa_store: SQLiteCandidateWfaStore,
        plan_resolver: RegisteredTrialExecutionPlanResolver,
        retrieval_service: SuccessorHistoricalRetrievalService,
        software_identity_provider,
        compatibility_checker,
        qualified_paper_application: QualifiedPaperCampaignApplication,
        clock=_utc_now,
    ) -> None:
        self.app_config = app_config
        self.instrument_registry = instrument_registry
        self.catalog_store = catalog_store
        self.artifact_store = artifact_store
        self.evidence_store = evidence_store
        self.qualification_store = qualification_store
        self.wfa_store = wfa_store
        self.plan_resolver = plan_resolver
        self.retrieval_service = retrieval_service
        self.software_identity_provider = software_identity_provider
        self.compatibility_checker = compatibility_checker
        self.qualified_paper_application = qualified_paper_application
        self.clock = clock

        self.qualification_service = QualificationService(
            catalog_store=catalog_store,
            artifact_store=artifact_store,
            qualification_store=qualification_store,
        )
        self.wfa_service = CandidateWfaService(
            catalog_store=catalog_store,
            artifact_store=artifact_store,
            qualification_store=qualification_store,
            wfa_store=wfa_store,
            plan_resolver=plan_resolver,
            execution_input_resolver=self._execution_inputs,
            retrieval_service=retrieval_service,
            software_identity_provider=software_identity_provider,
            executable_compatibility_checker=compatibility_checker,
        )

    def _study(self, study_id: str) -> Study:
        study = self.catalog_store.load_study(study_id)
        if study is None or study.archived:
            raise ResearchWorkspaceNotFound(study_id)
        return study

    def _study_response(self, study: Study) -> WorkspaceStudyResponse:
        return WorkspaceStudyResponse(
            study_id=study.study_id,
            display_title=study.display_title,
            created_at=study.created_at,
            archived=study.archived,
        )

    def _policy_response(self, policy) -> WorkspaceQualificationPolicyResponse:
        return WorkspaceQualificationPolicyResponse(
            policy_id=policy.policy_id,
            version=policy.version,
            threshold_pct=str(policy.net_profitable_trade_rate_threshold_pct),
        )


    def _active_policy_id(self) -> str | None:
        try:
            policy = self.qualification_store.load_active_policy()
        except Exception as error:
            raise ResearchWorkspaceOperationalError(
                "active QualificationPolicy could not be read reliably"
            ) from error
        return None if policy is None else policy.policy_id

    def _require_policy_generation(self, expected_policy_id: str | None) -> None:
        if self._active_policy_id() != expected_policy_id:
            raise ResearchWorkspaceConflict(
                "active QualificationPolicy changed since caller observation"
            )

    def _paper_authority_generation(self, campaigns) -> tuple:
        policy_id = self._active_policy_id()
        values = []
        try:
            for campaign in campaigns:
                historical = self.qualification_store.load_current_decision(
                    campaign.trial_id
                )
                wfa = self.wfa_store.load_current_decision(
                    campaign.candidate_revision_id
                )
                values.append(
                    (
                        campaign.campaign_id,
                        None if historical is None else historical.decision_id,
                        None if wfa is None else wfa.decision_id,
                    )
                )
        except Exception as error:
            raise ResearchWorkspaceOperationalError(
                "Paper authority generation could not be read reliably"
            ) from error
        return policy_id, tuple(values)

    def _symbol_options(self):
        values = {
            (item.symbol, item.exchange)
            for item in self.instrument_registry.instruments
        }
        return [
            {"symbol": symbol, "exchange": exchange}
            for symbol, exchange in sorted(values)
        ]

    def config(self) -> ResearchWorkspaceConfigResponse:
        from api.application_catalog import (
            MARKETS,
            STRATEGIES,
            TIMEFRAMES,
            TIMEZONES,
        )

        studies = self.catalog_store.list_studies(include_archived=False)
        active = self.qualification_store.load_active_policy()
        return ResearchWorkspaceConfigResponse(
            markets=[dict(item) for item in MARKETS],
            symbols=self._symbol_options(),
            timeframes=[dict(item) for item in TIMEFRAMES],
            strategies=[dict(item) for item in STRATEGIES],
            timezones=list(TIMEZONES),
            studies=[self._study_response(item) for item in studies],
            active_qualification_policy=(
                None if active is None else self._policy_response(active)
            ),
        )

    def create_study(self, display_title: str) -> WorkspaceStudyResponse:
        if not isinstance(display_title, str) or not display_title.strip():
            raise ValueError("display_title must be non-empty")
        study = Study(
            study_id="study-" + uuid4().hex,
            created_at=self.clock(),
            display_title=display_title.strip(),
        )
        return self._study_response(self.catalog_store.save_study(study))

    def _instrument_for_request(
        self,
        symbol: str,
        exchange: str,
        request: TimeRange,
    ):
        instrument = self.instrument_registry.resolve_symbol(
            symbol=symbol,
            exchange=exchange,
            at=request.start,
        )
        matching = [
            item
            for item in self.instrument_registry.instruments
            if item.instrument_id == instrument.instrument_id
            and item.symbol == symbol
            and item.exchange == exchange
            and (item.effective_from is None or item.effective_from <= request.start)
            and (item.effective_to is None or request.end <= item.effective_to)
        ]
        if len(matching) != 1:
            raise ValueError(
                "canonical instrument metadata does not cover the complete Backtest range"
            )
        self.instrument_registry.resolve_bindings(
            instrument_id=instrument.instrument_id,
            provider="angelone",
            request=request,
        )
        return instrument

    def _runtime_context_from_plan(
        self,
        plan: RegisteredTrialExecutionPlan,
    ) -> RuntimeContext:
        values = dict(plan.risk_economic_configuration)
        execution = ExecutionConfig(
            slippage_pct=values.pop("slippage_pct"),
            brokerage_enabled=values.pop("brokerage_enabled"),
            slippage_enabled=values.pop("slippage_enabled"),
        )
        risk_per_trade_pct = values.pop("risk_per_trade_pct")
        policy = BacktestEconomicPolicy(**values)
        return RuntimeContext(
            execution_config=execution,
            risk_per_trade_pct=risk_per_trade_pct,
            economic_policy=policy,
        )

    def _instrument_for_plan(self, plan: RegisteredTrialExecutionPlan):
        matching = [
            item
            for item in self.instrument_registry.instruments
            if item.instrument_id == plan.instrument_id
            and (item.effective_from is None or item.effective_from <= plan.trial_range.start)
            and (item.effective_to is None or plan.trial_range.end <= item.effective_to)
        ]
        if len(matching) != 1:
            raise ValueError(
                "registered Trial instrument cannot be resolved uniquely for its range"
            )
        return matching[0]

    def _execution_inputs(
        self,
        plan: RegisteredTrialExecutionPlan,
    ) -> ClaimedTrialExecutionInputs:
        instrument = self._instrument_for_plan(plan)
        strategy_name = PROCEDURE_TO_STRATEGY.get(plan.strategy_procedure_id)
        if strategy_name is None:
            raise ValueError("registered strategy procedure is not supported")
        config = BacktestConfig(
            symbol=instrument.symbol,
            timeframe=plan.timeframe,
            strategy_name=strategy_name,
            start=plan.trial_range.start,
            end=plan.trial_range.end,
            initial_capital=plan.initial_capital,
            enable_replay=False,
            enable_visualization=False,
            enable_exports=False,
            strategy_params=dict(plan.parameter_configuration),
            timezone=plan.timezone,
        )
        runtime_context = self._runtime_context_from_plan(plan)
        data_treatment = dict(plan.data_treatment_basis)
        price_value = data_treatment.get("price_adjustment")
        if not isinstance(price_value, str):
            raise ValueError("registered price_adjustment is missing")
        price_basis = PriceAdjustmentBasis(price_value.upper())
        return ClaimedTrialExecutionInputs(
            strategy=create_registered_research_strategy(
                plan.strategy_procedure_id,
                config,
            ),
            config=config,
            runtime_context=runtime_context,
            dataset_context=DatasetContext(
                symbol=instrument.symbol,
                timeframe=plan.timeframe,
                timezone=plan.timezone,
            ),
            provider="angelone",
            price_adjustment_basis=price_basis,
            strategy_procedure_id=plan.strategy_procedure_id,
            risk_economic_configuration=dict(plan.risk_economic_configuration),
            data_treatment_basis=data_treatment,
        )

    def _claimed_executor(self) -> ClaimedResearchJobExecutor:
        orchestrator = BacktestResearchOrchestrator(
            catalog_store=self.catalog_store,
            evidence_store=self.evidence_store,
            artifact_store=self.artifact_store,
            software_identity_provider=self.software_identity_provider,
            retrieve_candles=lambda **_kwargs: (_ for _ in ()).throw(
                AssertionError("registered successor execution must not use legacy retrieval")
            ),
            execute_candles=execute_backtest_candles,
        )
        coordinator = SuccessorBacktestResearchCoordinator(
            retrieval_service=self.retrieval_service,
            orchestrator=orchestrator,
        )
        return ClaimedResearchJobExecutor(
            catalog_store=self.catalog_store,
            plan_resolver=self.plan_resolver,
            execution_input_resolver=self._execution_inputs,
            successor_coordinator=coordinator,
        )

    def _exact_repository_revision(self) -> str:
        identity = self.software_identity_provider.resolve()
        if not identity.is_exact:
            raise ResearchWorkspaceOperationalError(
                "registered Backtest requires exact clean repository identity"
            )
        return identity.repository_revision

    def _register_backtest(self, request: WorkspaceBacktestRunRequest):
        self._study(request.study_id)
        research_range = TimeRange(request.start, request.end)
        instrument = self._instrument_for_request(
            request.symbol,
            "NSE",
            research_range,
        )
        procedure = STRATEGY_TO_PROCEDURE.get(request.strategy_id)
        if procedure is None:
            raise ValueError("strategy is not registered for research execution")

        runtime_context = RuntimeContext(
            risk_per_trade_pct=self.app_config.risk_per_trade_pct
        )
        risk_config = effective_backtest_financial_configuration(runtime_context)
        definition = UniverseDefinition(
            name=f"m9.8-fixed-{instrument.instrument_id}",
            selection_spec="one explicitly selected canonical instrument",
            source_reference=self.app_config.instrument_registry_path,
        )
        snapshot = UniverseSnapshot(
            definition=definition,
            members=(instrument.instrument_id,),
            quality=UniverseQuality.CUSTOM_FIXED,
            as_of=request.start,
            provenance_refs=(
                f"instrument-registry:{instrument.instrument_id}",
            ),
            effective_from=request.start,
            effective_to=request.end,
        )
        intent_payload = {
            "instrument_id": instrument.instrument_id,
            "strategy_procedure_id": procedure,
            "strategy_parameters": request.strategy_params.model_dump(),
            "timeframe": request.timeframe,
            "start": request.start.isoformat(),
            "end": request.end.isoformat(),
            "timezone": request.timezone,
            "initial_capital": request.initial_capital,
        }
        registration = RegisteredStudyRegistrationService(
            catalog_store=self.catalog_store,
            artifact_store=self.artifact_store,
            max_trials_per_revision=self.app_config.research_max_trials_per_revision,
        ).register_study_revision(
            study_id=request.study_id,
            research_intent=json.dumps(
                intent_payload,
                sort_keys=True,
                separators=(",", ":"),
            ),
            strategy_procedure_id=procedure,
            timeframe=request.timeframe,
            research_range=research_range,
            timezone=request.timezone,
            initial_capital=request.initial_capital,
            risk_economic_configuration=risk_config,
            parameter_variants=(request.strategy_params.model_dump(),),
            universe_definition=definition,
            universe_snapshots=(snapshot,),
            require_point_in_time=False,
            data_treatment_basis={"price_adjustment": "raw"},
            repository_revision=self._exact_repository_revision(),
            evidence_reuse_policy=EvidenceReusePolicy.ALLOW_EXACT_ACCEPTED,
            registered_at=self.clock(),
        )
        if len(registration.trials) != 1:
            raise ResearchWorkspaceOperationalError(
                "M9.8 one-strategy Backtest must register exactly one Trial"
            )
        return registration.revision, registration.trials[0]

    def _drain_revision(self, study_revision_id: str) -> None:
        queue = ResearchJobQueueService(
            catalog_store=self.catalog_store,
            app_config=self.app_config,
        )
        queue.start_revision(study_revision_id, started_at=self.clock())
        executor = self._claimed_executor()
        queue.run_worker_pool(
            study_revision_id,
            worker_id_factory=lambda index: f"m98-worker-{index}-{uuid4().hex}",
            claimed_at_factory=self.clock,
            execute_claimed_job=executor.execute,
        )

    def _retry_trial(
        self,
        trial_id: str,
        expected_disposition_event_id: str,
    ) -> None:
        trial = self.catalog_store.load_trial(trial_id)
        if trial is None:
            raise ResearchWorkspaceNotFound(trial_id)
        if trial.disposition not in _RETRYABLE:
            raise ResearchWorkspaceConflict(
                "Trial is not retryable from its current disposition"
            )
        try:
            self.catalog_store.retry_trial(
                trial_id,
                retry_requested_at=self.clock(),
                expected_disposition_event_id=expected_disposition_event_id,
            )
        except ValueError as error:
            raise ResearchWorkspaceConflict(str(error)) from error
        queue = ResearchJobQueueService(
            catalog_store=self.catalog_store,
            app_config=self.app_config,
        )
        executor = self._claimed_executor()
        queue.run_worker_pool(
            trial.study_revision_id,
            worker_id_factory=lambda index: f"m98-retry-{index}-{uuid4().hex}",
            claimed_at_factory=self.clock,
            execute_claimed_job=executor.execute,
        )

    def _attempt_lineage(self, trial):
        snapshot = self.catalog_store.load_research_trial_detail_snapshot(
            trial.trial_id
        )
        if snapshot is None or not snapshot.disposition_events:
            raise ResearchWorkspaceOperationalError(
                "registered Trial detail is unavailable"
            )
        event = snapshot.disposition_events[-1]
        job = next(
            (item for item in snapshot.jobs if item.job_id == event.causing_job_id),
            None,
        )
        if job is None:
            raise ResearchWorkspaceOperationalError(
                "terminal Trial causing job is unavailable"
            )
        if trial.disposition is TrialDisposition.REUSED:
            attempt_id = job.reused_attempt_id
            attempts = dict(snapshot.reused_attempts)
        else:
            attempt_id = job.attempt_id
            attempts = dict(snapshot.owned_attempts)
        if attempt_id is None or attempt_id not in attempts:
            raise ResearchWorkspaceOperationalError(
                "registered Trial attempt lineage is unavailable"
            )
        return attempts[attempt_id]

    @staticmethod
    def _backtest_result_from_payload(payload: dict, session_id: str) -> BacktestResult:
        trades = [
            Trade(
                symbol=item["symbol"],
                entry_time=item["entry_time"],
                entry_price=item["entry_price"],
                exit_time=item["exit_time"],
                exit_price=item["exit_price"],
                stop_price=item["stop_price"],
                quantity=item["quantity"],
                direction=item["direction"],
                exit_reason=item["exit_reason"],
                pnl=item["pnl"],
                gross_pnl=item["gross_pnl"],
                transaction_cost=item["transaction_cost"],
                pnl_pct=item["pnl_pct"],
            )
            for item in payload["trades"]
        ]
        bars = [
            BarRecord(
                timestamp=item["timestamp"],
                open=item["open"],
                high=item["high"],
                low=item["low"],
                close=item["close"],
                volume=item["volume"],
                strategy=item["strategy"],
                state=item["state"],
                signal=item["signal"],
                execution_event=item["execution_event"],
                execution_price=item["execution_price"],
                execution_quantity=item["execution_quantity"],
                decision_snapshot=dict(item["decision_snapshot"]),
                equity=item["equity"],
                cash=item["cash"],
                position_size=item["position_size"],
                drawdown=item["drawdown"],
            )
            for item in payload["bar_records"]
        ]
        return BacktestResult(
            trades=trades,
            bar_records=bars,
            session_id=session_id,
        )

    def _backtest_response_from_trial(
        self,
        trial,
    ) -> WorkspaceBacktestRunResponse:
        revision = self.catalog_store.load_study_revision(
            trial.study_revision_id
        )
        if revision is None:
            raise ResearchWorkspaceOperationalError(
                "StudyRevision disappeared while loading Backtest result"
            )
        plan = self.plan_resolver.resolve(trial.trial_id)
        instrument = self._instrument_for_plan(plan)
        strategy_id = PROCEDURE_TO_STRATEGY.get(plan.strategy_procedure_id)
        if strategy_id is None:
            raise ResearchWorkspaceOperationalError(
                "registered strategy procedure is not displayable"
            )
        verified = StudyAggregationService(
            catalog_store=self.catalog_store,
            artifact_store=self.artifact_store,
        ).load_verified_trial_backtest(trial.trial_id)
        attempt = self._attempt_lineage(trial)
        if attempt.evidence_id is None:
            raise ResearchWorkspaceOperationalError("accepted evidence is missing")
        evidence = self.evidence_store.load(attempt.evidence_id)
        if evidence is None or evidence.status is not ResearchEvidenceStatus.ACCEPTED:
            raise ResearchWorkspaceOperationalError(
                "registered Backtest does not have ACCEPTED evidence"
            )
        session_id = attempt.runtime_session_id or attempt.attempt_id
        result = self._backtest_result_from_payload(
            verified.payload,
            session_id,
        )
        summary = BacktestSummaryResponse.model_validate(
            PerformanceMetrics.summarize_backtest(result)
        )
        trades = [
            BacktestTradeResponse(
                symbol=trade.symbol,
                entry_time=trade.entry_time,
                entry_price=trade.entry_price,
                exit_time=trade.exit_time,
                exit_price=trade.exit_price,
                stop_price=trade.stop_price,
                quantity=trade.quantity,
                direction=trade.direction,
                exit_reason=trade.exit_reason,
                net_pnl=trade.pnl,
                gross_pnl=trade.gross_pnl,
                transaction_cost=trade.transaction_cost,
                instrument_return_pct=trade.pnl_pct,
            )
            for trade in result.trades
        ]
        return WorkspaceBacktestRunResponse(
            run_id=result.session_id,
            attempt_id=attempt.attempt_id,
            evidence_id=evidence.evidence_id,
            evidence_status=evidence.status.value,
            status="completed",
            symbol=instrument.symbol,
            timeframe=plan.timeframe,
            strategy_id=strategy_id,
            start=plan.trial_range.start,
            end=plan.trial_range.end,
            timezone=plan.timezone,
            summary=summary,
            equity_curve=[
                BacktestEquityPoint(timestamp=timestamp, equity=equity)
                for timestamp, equity in result.equity_curve
            ],
            trades=trades,
            study_id=revision.study_id,
            study_revision_id=revision.study_revision_id,
            trial_id=trial.trial_id,
        )

    def run_backtest(
        self,
        request: WorkspaceBacktestRunRequest,
    ) -> WorkspaceBacktestRunResponse:
        revision, trial = self._register_backtest(request)
        current = self.catalog_store.load_trial(trial.trial_id)
        if current is None:
            raise ResearchWorkspaceOperationalError("registered Trial disappeared")
        if current.disposition in _RETRYABLE:
            raise ResearchWorkspaceConflict(
                "registered Trial is retryable; use the explicit Retry action"
            )
        elif current.disposition is TrialDisposition.PENDING:
            self._drain_revision(revision.study_revision_id)
        elif current.disposition not in {
            TrialDisposition.EXECUTED,
            TrialDisposition.REUSED,
        }:
            raise ResearchWorkspaceConflict(
                f"registered Trial cannot run from {current.disposition.value}"
            )
        current = self.catalog_store.load_trial(trial.trial_id)
        if current is None or current.disposition not in {
            TrialDisposition.EXECUTED,
            TrialDisposition.REUSED,
        }:
            raise ResearchWorkspaceOperationalError(
                "registered Backtest did not finish with result-bearing evidence"
            )
        return self._backtest_response_from_trial(current)

    def load_backtest_result(
        self,
        trial_id: str,
    ) -> WorkspaceBacktestRunResponse:
        trial = self.catalog_store.load_trial(trial_id)
        if trial is None:
            raise ResearchWorkspaceNotFound(trial_id)
        if trial.disposition not in {
            TrialDisposition.EXECUTED,
            TrialDisposition.REUSED,
        }:
            raise ResearchWorkspaceConflict(
                "selected Trial does not have a saved Backtest result"
            )
        return self._backtest_response_from_trial(trial)

    def retry_backtest(
        self,
        trial_id: str,
        expected_disposition_event_id: str,
    ) -> WorkspaceStrategyState:
        self._retry_trial(trial_id, expected_disposition_event_id)
        return self._strategy_state(self.catalog_store.load_trial(trial_id))

    def _strategy_label(self, procedure_id: str, params: dict) -> str:
        if procedure_id == "sma-crossover-v1":
            return (
                f"SMA Crossover "
                f"{params.get('fast_period')}/{params.get('slow_period')}"
            )
        return procedure_id

    def _campaign_for_candidate(self, candidate_revision_id: str):
        campaigns = self.qualified_paper_application.list_campaigns_for_candidate(
            candidate_revision_id
        )
        current = [
            campaign
            for campaign in campaigns
            if self.qualified_paper_application.campaign_is_current(
                campaign.campaign_id
            )
        ]
        return current[-1] if current else None

    def _current_wfa_for_historical(self, historical_decision):
        """Return WFA only when it still depends on the current M9.5 decision."""

        if (
            historical_decision is None
            or historical_decision.candidate_revision_id is None
            or historical_decision.outcome is not QualificationOutcome.ELIGIBLE
        ):
            return None

        decision = self.wfa_store.load_current_decision_if_historical_current(
            historical_decision.candidate_revision_id
        )
        if decision is None:
            return None
        if (
            decision.historical_qualification_decision_id
            != historical_decision.decision_id
        ):
            return None
        return decision

    def _strategy_state(self, trial) -> WorkspaceStrategyState:
        if trial is None:
            raise ResearchWorkspaceNotFound("trial")
        revision = self.catalog_store.load_study_revision(trial.study_revision_id)
        if revision is None:
            raise ResearchWorkspaceOperationalError("StudyRevision disappeared")
        events = self.catalog_store.load_trial_disposition_events(trial.trial_id)
        if not events:
            raise ResearchWorkspaceOperationalError(
                "Trial disposition generation is missing"
            )
        plan = self.plan_resolver.resolve(trial.trial_id)
        instrument = self._instrument_for_plan(plan)
        qualification = self.qualification_store.load_current_decision(trial.trial_id)
        candidate_id = (
            None if qualification is None else qualification.candidate_revision_id
        )
        wfa = self._current_wfa_for_historical(qualification)
        campaign = (
            None
            if (
                candidate_id is None
                or wfa is None
                or wfa.outcome is not WfaQualificationOutcome.ELIGIBLE
                or wfa.wfa_verdict != "PASS"
            )
            else self._campaign_for_candidate(candidate_id)
        )
        return WorkspaceStrategyState(
            study_id=revision.study_id,
            study_revision_id=revision.study_revision_id,
            revision_number=revision.revision_number,
            trial_id=trial.trial_id,
            instrument_id=trial.instrument_id,
            symbol=instrument.symbol,
            timeframe=plan.timeframe,
            strategy_procedure_id=plan.strategy_procedure_id,
            strategy_label=self._strategy_label(
                plan.strategy_procedure_id,
                dict(plan.parameter_configuration),
            ),
            strategy_parameters=dict(plan.parameter_configuration),
            trial_disposition=trial.disposition.value,
            trial_disposition_event_id=events[-1].event_id,
            qualification_outcome=(
                None if qualification is None else qualification.outcome.value
            ),
            qualification_decision_id=(
                None if qualification is None else qualification.decision_id
            ),
            candidate_revision_id=candidate_id,
            wfa_outcome=None if wfa is None else wfa.outcome.value,
            wfa_verdict=None if wfa is None else wfa.wfa_verdict,
            wfa_decision_id=None if wfa is None else wfa.decision_id,
            paper_campaign_id=None if campaign is None else campaign.campaign_id,
            retryable=trial.disposition in _RETRYABLE,
        )

    def study_strategies(self, study_id: str) -> WorkspaceStrategyListResponse:
        self._study(study_id)
        policy_generation = self._active_policy_id()
        values = []
        for revision in self.catalog_store.list_study_revisions(study_id):
            for trial in self.catalog_store.list_registered_trials_for_revision(
                revision.study_revision_id
            ):
                values.append(self._strategy_state(trial))
        if self._active_policy_id() != policy_generation:
            raise ResearchWorkspaceConflict(
                "QualificationPolicy changed while Study state was assembled"
            )
        return WorkspaceStrategyListResponse(
            study_id=study_id,
            strategies=values,
        )

    def qualify_study(
        self,
        study_id: str,
        threshold_pct: Decimal,
        observed_policy_id: str | None = None,
    ) -> WorkspaceQualificationResponse:
        self._study(study_id)
        try:
            policy, changed = self.qualification_store.ensure_active_policy_threshold(
                threshold_pct,
                changed_at=self.clock(),
                expected_active_policy_id=observed_policy_id,
            )
        except QualificationPolicyConcurrencyConflict as error:
            raise ResearchWorkspaceConflict(
                "active global QualificationPolicy changed since caller observation"
            ) from error
        results = []
        policy_superseded = False
        for revision in self.catalog_store.list_study_revisions(study_id):
            for trial in self.catalog_store.list_registered_trials_for_revision(
                revision.study_revision_id
            ):
                if trial.disposition not in {
                    TrialDisposition.EXECUTED,
                    TrialDisposition.REUSED,
                }:
                    continue
                try:
                    plan = self.plan_resolver.resolve(trial.trial_id)
                    label = self._strategy_label(
                        plan.strategy_procedure_id,
                        dict(plan.parameter_configuration),
                    )
                except Exception as error:
                    results.append(
                        WorkspaceQualificationItemResponse(
                            trial_id=trial.trial_id,
                            strategy_label=trial.trial_id,
                            outcome="OPERATIONAL_ERROR",
                            evidence_validity="UNKNOWN",
                            reason=str(error) or type(error).__name__,
                        )
                    )
                    continue

                if policy_superseded:
                    results.append(
                        WorkspaceQualificationItemResponse(
                            trial_id=trial.trial_id,
                            strategy_label=label,
                            outcome="POLICY_SUPERSEDED",
                            evidence_validity="NOT_EVALUATED",
                            reason=(
                                "Requested QualificationPolicy was superseded "
                                "before this strategy could be evaluated"
                            ),
                        )
                    )
                    continue

                try:
                    decision = self.qualification_service.evaluate_selected_trial(
                        trial.trial_id,
                        evaluated_at=self.clock(),
                    )
                    decision_matches_request = (
                        decision.policy_id == policy.policy_id
                    )
                    if not decision_matches_request:
                        policy_superseded = True
                    results.append(
                        WorkspaceQualificationItemResponse(
                            trial_id=trial.trial_id,
                            strategy_label=label,
                            outcome=(
                                decision.outcome.value
                                if decision_matches_request
                                else "POLICY_SUPERSEDED"
                            ),
                            evidence_validity=decision.evidence_validity.value,
                            decision_id=decision.decision_id,
                            candidate_revision_id=decision.candidate_revision_id,
                            decision_policy_id=decision.policy_id,
                            decision_policy_version=decision.policy_version,
                            decision_threshold_pct=decision.threshold_text,
                            reason=(
                                decision.reason
                                if decision_matches_request
                                else (
                                    "Concurrent policy activation superseded the "
                                    "requested policy; this decision belongs to "
                                    "the newer active policy"
                                )
                            ),
                        )
                    )
                except QualificationOperationalError as error:
                    results.append(
                        WorkspaceQualificationItemResponse(
                            trial_id=trial.trial_id,
                            strategy_label=label,
                            outcome="OPERATIONAL_ERROR",
                            evidence_validity="UNKNOWN",
                            reason=str(error) or type(error).__name__,
                        )
                    )
                except Exception as error:
                    results.append(
                        WorkspaceQualificationItemResponse(
                            trial_id=trial.trial_id,
                            strategy_label=label,
                            outcome="OPERATIONAL_ERROR",
                            evidence_validity="UNKNOWN",
                            reason=str(error) or type(error).__name__,
                        )
                    )

        active = self.qualification_store.load_active_policy()
        policy_current = (
            active is not None and active.policy_id == policy.policy_id
        )
        return WorkspaceQualificationResponse(
            study_id=study_id,
            policy=self._policy_response(policy),
            policy_changed=changed,
            policy_current=policy_current,
            results=results,
        )

    def _wfa_item(self, decision) -> WorkspaceWfaItemResponse:
        candidate = self.qualification_store.load_candidate_revision(
            decision.candidate_revision_id
        )
        if candidate is None:
            raise ResearchWorkspaceOperationalError("CandidateRevision disappeared")
        plan = self.plan_resolver.resolve(candidate.trial_id)
        metrics = None
        if decision.result_artifact_id is not None:
            payload = self.artifact_store.load_bytes(decision.result_artifact_id)
            decoded = decode_candidate_wfa_result_bytes(payload)
            aggregated = decoded["aggregated_metrics"]
            stitched = decoded["stitched_equity_metrics"]
            metrics = WorkspaceWfaMetricsResponse(
                consistency_ratio=aggregated["consistency_ratio"],
                avg_account_return_pct=aggregated["avg_account_return_pct"],
                worst_equity_drawdown_pct=aggregated["worst_equity_drawdown_pct"],
                stitched_total_return_pct=stitched["stitched_total_return_pct"],
                stitched_max_drawdown_pct=stitched["stitched_max_drawdown_pct"],
                account_return_stability_score=aggregated[
                    "account_return_stability_score"
                ],
            )
        return WorkspaceWfaItemResponse(
            trial_id=decision.trial_id,
            candidate_revision_id=decision.candidate_revision_id,
            strategy_label=self._strategy_label(
                plan.strategy_procedure_id,
                dict(plan.parameter_configuration),
            ),
            evidence_validity=decision.evidence_validity.value,
            outcome=decision.outcome.value,
            verdict=decision.wfa_verdict,
            decision_id=decision.decision_id,
            reason=decision.reason,
            metrics=metrics,
        )

    def _pending_wfa_item(self, historical) -> WorkspaceWfaItemResponse:
        candidate_id = historical.candidate_revision_id
        if candidate_id is None:
            raise ResearchWorkspaceOperationalError(
                "current eligible qualification lacks CandidateRevision"
            )
        candidate = self.qualification_store.load_candidate_revision(
            candidate_id
        )
        if candidate is None:
            raise ResearchWorkspaceOperationalError(
                "CandidateRevision disappeared"
            )
        plan = self.plan_resolver.resolve(candidate.trial_id)
        return WorkspaceWfaItemResponse(
            trial_id=historical.trial_id,
            candidate_revision_id=candidate_id,
            strategy_label=self._strategy_label(
                plan.strategy_procedure_id,
                dict(plan.parameter_configuration),
            ),
            evidence_validity="NOT_EVALUATED",
            outcome="PENDING",
            verdict=None,
            decision_id=None,
            reason="Historically eligible; WFA has not yet been evaluated",
            metrics=None,
        )

    def wfa_state(self, study_id: str) -> WorkspaceWfaResponse:
        self._study(study_id)
        policy_generation = self._active_policy_id()
        items = []
        for revision in self.catalog_store.list_study_revisions(study_id):
            try:
                historical_decisions = (
                    self.qualification_store.list_current_eligible_decisions(
                        revision.study_revision_id
                    )
                )
            except Exception as error:
                items.append(
                    WorkspaceWfaItemResponse(
                        trial_id=revision.study_revision_id,
                        candidate_revision_id=None,
                        strategy_label=f"Revision {revision.revision_number}",
                        evidence_validity="UNKNOWN",
                        outcome="OPERATIONAL_ERROR",
                        verdict=None,
                        decision_id=None,
                        reason=str(error) or type(error).__name__,
                        metrics=None,
                    )
                )
                continue
            for historical in historical_decisions:
                if historical.candidate_revision_id is None:
                    continue
                try:
                    decision = self._current_wfa_for_historical(historical)
                    items.append(
                        self._pending_wfa_item(historical)
                        if decision is None
                        else self._wfa_item(decision)
                    )
                except Exception as error:
                    try:
                        pending = self._pending_wfa_item(historical)
                        label = pending.strategy_label
                    except Exception:
                        label = historical.trial_id
                    items.append(
                        WorkspaceWfaItemResponse(
                            trial_id=historical.trial_id,
                            candidate_revision_id=(
                                historical.candidate_revision_id
                            ),
                            strategy_label=label,
                            evidence_validity="UNKNOWN",
                            outcome="OPERATIONAL_ERROR",
                            verdict=None,
                            decision_id=None,
                            reason=str(error) or type(error).__name__,
                            metrics=None,
                        )
                    )
        if self._active_policy_id() != policy_generation:
            raise ResearchWorkspaceConflict(
                "QualificationPolicy changed while WFA state was assembled"
            )
        return WorkspaceWfaResponse(
            study_id=study_id,
            active_policy_id=policy_generation,
            strategies=items,
        )

    def run_wfa(
        self,
        study_id: str,
        expected_policy_id: str | None,
    ) -> WorkspaceWfaResponse:
        self._study(study_id)
        self._require_policy_generation(expected_policy_id)
        results = []
        for revision in self.catalog_store.list_study_revisions(study_id):
            self._require_policy_generation(expected_policy_id)
            try:
                historical_decisions = (
                    self.qualification_store.list_current_eligible_decisions(
                        revision.study_revision_id
                    )
                )
            except Exception as error:
                results.append(
                    WorkspaceWfaItemResponse(
                        trial_id=revision.study_revision_id,
                        candidate_revision_id=None,
                        strategy_label=f"Revision {revision.revision_number}",
                        evidence_validity="UNKNOWN",
                        outcome="OPERATIONAL_ERROR",
                        verdict=None,
                        decision_id=None,
                        reason=str(error) or type(error).__name__,
                        metrics=None,
                    )
                )
                continue
            if not historical_decisions:
                continue

            self._require_policy_generation(expected_policy_id)
            try:
                decisions = self.wfa_service.evaluate_study_revision(
                    revision.study_revision_id
                )
                self._require_policy_generation(expected_policy_id)
            except CandidateWfaOperationalError as error:
                for historical in historical_decisions:
                    try:
                        pending = self._pending_wfa_item(historical)
                        label = pending.strategy_label
                    except Exception:
                        label = historical.trial_id
                    results.append(
                        WorkspaceWfaItemResponse(
                            trial_id=historical.trial_id,
                            candidate_revision_id=(
                                historical.candidate_revision_id
                            ),
                            strategy_label=label,
                            evidence_validity="UNKNOWN",
                            outcome="OPERATIONAL_ERROR",
                            verdict=None,
                            decision_id=None,
                            reason=str(error) or type(error).__name__,
                            metrics=None,
                        )
                    )
                continue
            except Exception as error:
                for historical in historical_decisions:
                    try:
                        pending = self._pending_wfa_item(historical)
                        label = pending.strategy_label
                    except Exception:
                        label = historical.trial_id
                    results.append(
                        WorkspaceWfaItemResponse(
                            trial_id=historical.trial_id,
                            candidate_revision_id=(
                                historical.candidate_revision_id
                            ),
                            strategy_label=label,
                            evidence_validity="UNKNOWN",
                            outcome="OPERATIONAL_ERROR",
                            verdict=None,
                            decision_id=None,
                            reason=str(error) or type(error).__name__,
                            metrics=None,
                        )
                    )
                continue

            for decision in decisions:
                try:
                    results.append(self._wfa_item(decision))
                except Exception as error:
                    results.append(
                        WorkspaceWfaItemResponse(
                            trial_id=decision.trial_id,
                            candidate_revision_id=(
                                decision.candidate_revision_id
                            ),
                            strategy_label=decision.trial_id,
                            evidence_validity="UNKNOWN",
                            outcome="OPERATIONAL_ERROR",
                            verdict=None,
                            decision_id=decision.decision_id,
                            reason=str(error) or type(error).__name__,
                            metrics=None,
                        )
                    )
        self._require_policy_generation(expected_policy_id)
        return WorkspaceWfaResponse(
            study_id=study_id,
            active_policy_id=expected_policy_id,
            strategies=results,
        )

    def send_to_paper(
        self,
        study_id: str,
        expected_wfa_decision_ids: list[str],
    ) -> WorkspacePaperSendResponse:
        self._study(study_id)
        items = []
        state = self.wfa_state(study_id)
        current_pass_ids = sorted(
            item.decision_id
            for item in state.strategies
            if (
                item.decision_id is not None
                and item.outcome == WfaQualificationOutcome.ELIGIBLE.value
                and item.verdict == "PASS"
            )
        )
        if current_pass_ids != sorted(expected_wfa_decision_ids):
            raise ResearchWorkspaceConflict(
                "current WFA PASS decision set changed since caller observation"
            )
        for strategy in state.strategies:
            if strategy.outcome == "OPERATIONAL_ERROR":
                items.append(
                    WorkspacePaperSendItemResponse(
                        candidate_revision_id=strategy.candidate_revision_id,
                        strategy_label=strategy.strategy_label,
                        outcome="OPERATIONAL_ERROR",
                        campaign_id=None,
                        reused=None,
                        reason=strategy.reason,
                    )
                )
                continue
            if (
                strategy.candidate_revision_id is None
                or strategy.outcome != WfaQualificationOutcome.ELIGIBLE.value
                or strategy.verdict != "PASS"
            ):
                continue
            try:
                campaign, created = (
                    self.qualified_paper_application.create_or_reuse_campaign(
                        strategy.candidate_revision_id
                    )
                )
                items.append(
                    WorkspacePaperSendItemResponse(
                        candidate_revision_id=strategy.candidate_revision_id,
                        strategy_label=strategy.strategy_label,
                        outcome="READY",
                        campaign_id=campaign.campaign_id,
                        reused=not created,
                        reason=(
                            "Existing current campaign reused"
                            if not created
                            else "Current campaign created"
                        ),
                    )
                )
            except QualifiedPaperAdmissionError as error:
                items.append(
                    WorkspacePaperSendItemResponse(
                        candidate_revision_id=strategy.candidate_revision_id,
                        strategy_label=strategy.strategy_label,
                        outcome="STALE_OR_INELIGIBLE",
                        campaign_id=None,
                        reused=None,
                        reason=str(error) or type(error).__name__,
                    )
                )
            except QualifiedPaperOperationalError as error:
                items.append(
                    WorkspacePaperSendItemResponse(
                        candidate_revision_id=strategy.candidate_revision_id,
                        strategy_label=strategy.strategy_label,
                        outcome="OPERATIONAL_ERROR",
                        campaign_id=None,
                        reused=None,
                        reason=str(error) or type(error).__name__,
                    )
                )
            except Exception as error:
                items.append(
                    WorkspacePaperSendItemResponse(
                        candidate_revision_id=strategy.candidate_revision_id,
                        strategy_label=strategy.strategy_label,
                        outcome="OPERATIONAL_ERROR",
                        campaign_id=None,
                        reused=None,
                        reason=str(error) or type(error).__name__,
                    )
                )
        return WorkspacePaperSendResponse(
            study_id=study_id,
            campaigns=items,
        )

    def _campaign_response(self, study_id: str, campaign):
        plan = self.plan_resolver.resolve(campaign.trial_id)
        return WorkspacePaperCampaignResponse(
            campaign_id=campaign.campaign_id,
            study_id=study_id,
            study_revision_id=campaign.study_revision_id,
            trial_id=campaign.trial_id,
            candidate_revision_id=campaign.candidate_revision_id,
            strategy_label=self._strategy_label(
                plan.strategy_procedure_id,
                dict(plan.parameter_configuration),
            ),
            wfa_decision_id=campaign.wfa_decision_id,
            created_at=campaign.created_at,
            current_authority=self.qualified_paper_application.campaign_is_current(
                campaign.campaign_id
            ),
        )

    def paper_state(self, study_id: str) -> WorkspacePaperCampaignListResponse:
        self._study(study_id)
        campaigns = self.qualified_paper_application.list_campaigns_for_study(
            study_id
        )
        generation = self._paper_authority_generation(campaigns)
        responses = [
            self._campaign_response(study_id, item)
            for item in campaigns
        ]
        if self._paper_authority_generation(campaigns) != generation:
            raise ResearchWorkspaceConflict(
                "Paper authority changed while campaign state was assembled"
            )
        return WorkspacePaperCampaignListResponse(
            study_id=study_id,
            campaigns=responses,
        )

    def paper_history(self, campaign_id: str) -> WorkspacePaperHistoryResponse:
        history = self.qualified_paper_application.history(campaign_id)
        revision = self.catalog_store.load_study_revision(
            history.campaign.study_revision_id
        )
        if revision is None:
            raise ResearchWorkspaceOperationalError("campaign StudyRevision disappeared")
        runtime = paper_trading_application.status()
        durable_active = self.qualified_paper_application.active_session()
        owns_runtime = (
            durable_active is not None
            and durable_active.campaign_id == campaign_id
            and runtime.snapshot is not None
            and runtime.snapshot.session_id == durable_active.session_id
        )
        return WorkspacePaperHistoryResponse(
            campaign=self._campaign_response(revision.study_id, history.campaign),
            sessions=[
                WorkspacePaperSessionResponse(
                    session_id=item.session_id,
                    state=item.state.value,
                    created_at=item.created_at,
                    started_at=item.started_at,
                    terminal_at=item.terminal_at,
                    failure_type=item.failure_type,
                    failure_message=item.failure_message,
                )
                for item in history.sessions
            ],
            runtime=runtime,
            campaign_owns_runtime=owns_runtime,
        )

    def start_paper(
        self,
        campaign_id: str,
        expected_latest_session_id: str | None,
    ) -> WorkspacePaperHistoryResponse:
        self.qualified_paper_application.start_session(
            campaign_id,
            expected_latest_session_id=expected_latest_session_id,
        )
        return self.paper_history(campaign_id)

    def stop_paper(
        self,
        campaign_id: str,
        expected_session_id: str,
    ) -> WorkspacePaperHistoryResponse:
        self.qualified_paper_application.stop_session(
            campaign_id,
            expected_session_id=expected_session_id,
        )
        return self.paper_history(campaign_id)

def build_research_workspace_application(
    *,
    app_config: AppConfig | None = None,
    instrument_registry: StaticInstrumentRegistry | None = None,
    software_identity_provider=None,
    compatibility_checker=None,
) -> ResearchWorkspaceApplication:
    config = app_config if app_config is not None else load_app_config()
    registry = (
        instrument_registry
        if instrument_registry is not None
        else load_instrument_registry(config.instrument_registry_path)
    )
    catalog = SQLiteResearchCatalogStore(config.research_database_path)
    artifact_store = ContentAddressedResearchArtifactStore(
        config.research_artifact_root
    )
    evidence_store = SQLiteResearchEvidenceStore(config.research_database_path)
    qualification_store = SQLiteQualificationStore(config.research_database_path)
    identity = software_identity_provider or GitSoftwareIdentityProvider()
    compatibility = (
        compatibility_checker or GitHistoricalExecutableCompatibilityChecker()
    )
    wfa_store = SQLiteCandidateWfaStore(
        config.research_database_path,
        artifact_store=artifact_store,
        software_identity_provider=identity,
        executable_compatibility_checker=compatibility,
    )
    plan_resolver = RegisteredTrialExecutionPlanResolver(
        catalog_store=catalog,
        artifact_store=artifact_store,
    )
    candle_store = SQLiteCandleStore(Path(config.historical_database_path))
    retrieval = SuccessorHistoricalRetrievalService(
        store=candle_store,
        registry=registry,
        policy=config.historical_source_policy,
        provider_factory=lambda: _LazyBindingAwareProvider(config),
    )

    def resolver(plan):
        # Build a temporary application shell only to reuse the exact resolver.
        return application._execution_inputs(plan)

    qualified_paper = build_qualified_paper_campaign_application(
        execution_input_resolver=resolver,
        successor_retrieval_service=retrieval,
        instrument_registry=registry,
        app_config=config,
        paper_application=paper_trading_application,
    )
    application = ResearchWorkspaceApplication(
        app_config=config,
        instrument_registry=registry,
        catalog_store=catalog,
        artifact_store=artifact_store,
        evidence_store=evidence_store,
        qualification_store=qualification_store,
        wfa_store=wfa_store,
        plan_resolver=plan_resolver,
        retrieval_service=retrieval,
        software_identity_provider=identity,
        compatibility_checker=compatibility,
        qualified_paper_application=qualified_paper,
    )
    return application

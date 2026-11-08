"""Application composition for M9.7 qualified persistent Paper campaigns."""

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime

import pytz

from api.paper_trading_application import (
    PaperTradingApplication,
    paper_trading_application,
)
from core.broker.angelone import AngelOneBroker
from core.broker.angelone_config import AngelOneConfig
from core.config.app_config import AppConfig
from core.config.loaders import load_app_config
from core.config.paper_data_source import PaperDataSource
from core.market_data.angelone_live_candle_feed import AngelOneLiveCandleFeed
from core.market_data.instrument_registry import StaticInstrumentRegistry
from core.research.executable_compatibility import (
    GitHistoricalExecutableCompatibilityChecker,
)
from core.research.qualified_paper_campaign_service import (
    PaperCampaignLifecycleConflict,
    QualifiedPaperCampaignService,
    QualifiedPaperSessionAuthority,
)
from core.research.registered_trial_execution_plan import (
    RegisteredTrialExecutionPlanResolver,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.software_identity import GitSoftwareIdentityProvider
from core.research.sqlite_candidate_wfa_store import SQLiteCandidateWfaStore
from core.research.sqlite_paper_campaign_store import SQLitePaperCampaignStore
from core.research.sqlite_qualification_store import SQLiteQualificationStore
from core.research.sqlite_research_catalog_store import SQLiteResearchCatalogStore
from core.runtime.live_paper_session import resolve_live_paper_session_window
from core.runtime.live_paper_warmup import load_live_paper_warmup
from core.runtime.paper_runtime import PreparedLivePaperRun, prepare_live_paper_trading


class _QualifiedHistoricalSourceAdapter:
    """Bind warm-up/reconciliation retrieval to the candidate's canonical instrument."""

    def __init__(
        self,
        *,
        retrieval_service,
        instrument_id: str,
        provider: str,
        price_adjustment_basis,
    ) -> None:
        self.retrieval_service = retrieval_service
        self.instrument_id = instrument_id
        self.provider = provider
        self.price_adjustment_basis = price_adjustment_basis

    def retrieve(self, context, request):
        result = self.retrieval_service.retrieve(
            context,
            request,
            instrument_id=self.instrument_id,
            provider=self.provider,
            price_adjustment_basis=self.price_adjustment_basis,
        )
        return list(result.candles)


def prepare_qualified_paper_trading(
    authority: QualifiedPaperSessionAuthority,
    *,
    successor_retrieval_service,
    app_config: AppConfig | None = None,
    now: Callable[[], datetime] | None = None,
) -> PreparedLivePaperRun:
    """Prepare existing M7 Paper runtime from one exact qualified CandidateRevision."""

    if not isinstance(authority, QualifiedPaperSessionAuthority):
        raise TypeError("authority must be a QualifiedPaperSessionAuthority")
    resolved_app_config = app_config if app_config is not None else load_app_config()
    if resolved_app_config.paper_data_source is not PaperDataSource.ANGELONE:
        raise ValueError(
            "qualified Paper requires ANGELONE real-market-data source"
        )

    inputs = authority.campaign_authority.execution_inputs
    plan = authority.campaign_authority.plan
    binding = authority.live_binding
    if binding.instrument_id != plan.instrument_id:
        raise ValueError("live provider binding does not match candidate instrument")
    if binding.provider != "angelone":
        raise ValueError("qualified Paper MVP supports AngelOne live data")
    if binding.provider_symbol != inputs.dataset_context.symbol:
        raise ValueError("live provider symbol does not match candidate symbol")
    if binding.provider_exchange is None or binding.provider_exchange.upper() != "NSE":
        raise ValueError("qualified Paper MVP supports NSE cash-equity binding")

    if inputs.dataset_context.timezone != "Asia/Kolkata":
        raise ValueError(
            "qualified Paper MVP supports only Asia/Kolkata candidate time semantics"
        )
    paper_timezone = pytz.timezone("Asia/Kolkata")
    raw_now = now if now is not None else lambda: datetime.now(paper_timezone)

    def now_fn() -> datetime:
        value = raw_now()
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "qualified Paper current time must be timezone-aware"
            )
        return value.astimezone(paper_timezone)

    current_time = now_fn()
    session_window = resolve_live_paper_session_window(
        current_time=current_time,
        session_start=resolved_app_config.paper_session_start,
        session_end=resolved_app_config.paper_session_end,
    )

    source = _QualifiedHistoricalSourceAdapter(
        retrieval_service=successor_retrieval_service,
        instrument_id=plan.instrument_id,
        provider=inputs.provider,
        price_adjustment_basis=inputs.price_adjustment_basis,
    )
    history_bars = load_live_paper_warmup(
        app_config=resolved_app_config,
        historical_source=source,
        strategy=inputs.strategy,
        dataset_context=inputs.dataset_context,
        current_time=current_time,
        session_start=session_window.start,
    )

    base_angelone_config = AngelOneConfig.load_from_env()
    angelone_config = replace(
        base_angelone_config,
        exchange=binding.provider_exchange,
        symbol_token_map={
            binding.provider_symbol: binding.provider_instrument_id,
        },
    )
    broker = AngelOneBroker(
        config=angelone_config,
        paper_mode=True,
        enable_historical_api=False,
    )
    broker.login()
    auth_token, feed_token = broker.get_live_market_data_session()

    current_time = now_fn()
    session_window = resolve_live_paper_session_window(
        current_time=current_time,
        session_start=resolved_app_config.paper_session_start,
        session_end=resolved_app_config.paper_session_end,
    )
    feed = AngelOneLiveCandleFeed(
        config=angelone_config,
        auth_token=auth_token,
        feed_token=feed_token,
        symbol=binding.provider_symbol,
        timeframe=inputs.dataset_context.timeframe,
        session_start=resolved_app_config.paper_session_start,
    )
    return prepare_live_paper_trading(
        feed=feed,
        strategy=inputs.strategy,
        runtime_context=inputs.runtime_context,
        dataset_context=inputs.dataset_context,
        session_end=session_window.end,
        now=now_fn,
        reconnect_attempts=resolved_app_config.broker_retry_attempts,
        reconnect_delay_seconds=resolved_app_config.broker_retry_delay_sec,
        clock_interval_seconds=resolved_app_config.paper_clock_interval_sec,
        initial_capital=inputs.config.initial_capital,
        history_bars=history_bars,
        historical_source=source,
    )


class QualifiedPaperCampaignApplication:
    """Coordinate durable research campaign state with the existing Paper owner."""

    def __init__(
        self,
        *,
        service: QualifiedPaperCampaignService,
        successor_retrieval_service,
        app_config: AppConfig,
        paper_application: PaperTradingApplication = paper_trading_application,
    ) -> None:
        self.service = service
        self.successor_retrieval_service = successor_retrieval_service
        self.app_config = app_config
        self.paper_application = paper_application

    def create_campaign(self, candidate_revision_id: str):
        return self.service.create_campaign(candidate_revision_id)

    def create_or_reuse_campaign(self, candidate_revision_id: str):
        return self.service.create_or_reuse_campaign(candidate_revision_id)

    def list_campaigns_for_study(self, study_id: str):
        return self.service.list_campaigns_for_study(study_id)

    def list_campaigns_for_candidate(self, candidate_revision_id: str):
        return self.service.list_campaigns_for_candidate(
            candidate_revision_id
        )

    def campaign_is_current(self, campaign_id: str) -> bool:
        return self.service.campaign_is_current(campaign_id)

    def active_session(self):
        return self.service.active_session()

    def start_session(self, campaign_id: str):
        authority = self.service.prepare_session(campaign_id)
        prepared = prepare_qualified_paper_trading(
            authority,
            successor_retrieval_service=self.successor_retrieval_service,
            app_config=self.app_config,
        )
        registered = False

        def before_start(value: PreparedLivePaperRun) -> None:
            nonlocal registered
            self.service.register_prepared_session(
                authority,
                session_id=value.session.session_id,
            )
            registered = True

        def terminal(snapshot) -> None:
            self.service.terminalize_snapshot(snapshot)

        try:
            response = self.paper_application.start_prepared(
                prepared,
                before_start_callback=before_start,
                terminal_callback=terminal,
            )
        except Exception as error:
            if registered:
                with prepared.state_lock:
                    observed = prepared.session.snapshot()

                if observed.status == "CREATED":
                    self.service.fail_prepared_session(
                        prepared.session.session_id,
                        error,
                    )
            raise

        if response.status == "RUNNING":
            self.service.mark_session_running(
                prepared.session.session_id
            )
        return self.service.history(campaign_id)

    def stop_session(self, campaign_id: str):
        active = self.service.active_session()
        if active is None or active.campaign_id != campaign_id:
            raise PaperCampaignLifecycleConflict(
                "requested PaperCampaign does not own the active qualified session"
            )
        status = self.paper_application.status()
        if (
            status.snapshot is None
            or status.snapshot.session_id != active.session_id
        ):
            raise PaperCampaignLifecycleConflict(
                "durable qualified session does not match process Paper ownership"
            )
        self.paper_application.stop(
            expected_session_id=active.session_id
        )
        return self.service.history(campaign_id)

    def history(self, campaign_id: str):
        return self.service.history(campaign_id)


def build_qualified_paper_campaign_application(
    *,
    execution_input_resolver,
    successor_retrieval_service,
    instrument_registry: StaticInstrumentRegistry,
    app_config: AppConfig | None = None,
    paper_application: PaperTradingApplication = paper_trading_application,
) -> QualifiedPaperCampaignApplication:
    """Build M9.7 from explicit research/data authorities; invent none."""

    config = app_config if app_config is not None else load_app_config()
    catalog = SQLiteResearchCatalogStore(config.research_database_path)
    artifact_store = ContentAddressedResearchArtifactStore(
        config.research_artifact_root
    )
    software_identity = GitSoftwareIdentityProvider()
    compatibility = GitHistoricalExecutableCompatibilityChecker()
    qualification_store = SQLiteQualificationStore(config.research_database_path)
    wfa_store = SQLiteCandidateWfaStore(
        config.research_database_path,
        artifact_store=artifact_store,
        software_identity_provider=software_identity,
        executable_compatibility_checker=compatibility,
    )
    campaign_store = SQLitePaperCampaignStore(config.research_database_path)
    plan_resolver = RegisteredTrialExecutionPlanResolver(
        catalog_store=catalog,
        artifact_store=artifact_store,
    )
    service = QualifiedPaperCampaignService(
        catalog_store=catalog,
        artifact_store=artifact_store,
        qualification_store=qualification_store,
        wfa_store=wfa_store,
        campaign_store=campaign_store,
        plan_resolver=plan_resolver,
        execution_input_resolver=execution_input_resolver,
        software_identity_provider=software_identity,
        executable_compatibility_checker=compatibility,
        instrument_registry=instrument_registry,
    )
    return QualifiedPaperCampaignApplication(
        service=service,
        successor_retrieval_service=successor_retrieval_service,
        app_config=config,
        paper_application=paper_application,
    )

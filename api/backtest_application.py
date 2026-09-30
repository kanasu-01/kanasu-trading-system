from dataclasses import dataclass

from api.models.backtest_models import (
    BacktestEquityPoint,
    BacktestRunRequest,
    BacktestRunResponse,
    BacktestSummaryResponse,
    BacktestTradeResponse,
)
from core.backtest.performance_metrics import PerformanceMetrics
from core.config.app_config import AppConfig
from core.config.backtest_config import BacktestConfig
from core.config.loaders import load_app_config
from core.market_data.historical_source import HistoricalSource
from core.market_data.historical_source_factory import create_historical_source
from core.research.backtest_research_orchestrator import (
    BacktestResearchOrchestrator,
)
from core.research.models.dataset import (
    PriceAdjustmentBasis,
)
from core.research.successor_backtest_research_coordinator import (
    SuccessorBacktestResearchCoordinator,
)
from core.research.successor_historical_retrieval import (
    SuccessorHistoricalRetrievalService,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.software_identity import (
    GitSoftwareIdentityProvider,
    SoftwareIdentityProvider,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)
from core.research.sqlite_research_evidence_store import (
    SQLiteResearchEvidenceStore,
)
from core.runtime.backtest_runtime import (
    execute_backtest_candles,
    retrieve_backtest_candles,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.strategy_factory import create_strategy


@dataclass(frozen=True)
class SuccessorBacktestApplicationContext:
    """
    Explicit opt-in context for truthful successor Backtest research.

    Normal callers do not construct this value and therefore retain the
    existing legacy historical-data path.
    """

    request_symbol: str
    instrument_id: str
    provider: str
    price_adjustment_basis: PriceAdjustmentBasis
    retrieval_service: SuccessorHistoricalRetrievalService

    def __post_init__(self) -> None:
        for field_name, value in (
            ("request_symbol", self.request_symbol),
            ("instrument_id", self.instrument_id),
            ("provider", self.provider),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"{field_name} must be a non-empty string"
                )

        if not isinstance(
            self.price_adjustment_basis,
            PriceAdjustmentBasis,
        ):
            raise TypeError(
                "price_adjustment_basis must be "
                "a PriceAdjustmentBasis"
            )

        if not callable(
            getattr(
                self.retrieval_service,
                "retrieve",
                None,
            )
        ):
            raise TypeError(
                "retrieval_service must provide retrieve()"
            )


def _create_backtest_research_orchestrator(
    app_config: AppConfig,
    *,
    software_identity_provider: SoftwareIdentityProvider | None = None,
) -> BacktestResearchOrchestrator:
    provider = (
        software_identity_provider
        if software_identity_provider is not None
        else GitSoftwareIdentityProvider()
    )

    return BacktestResearchOrchestrator(
        catalog_store=SQLiteResearchCatalogStore(
            app_config.research_database_path
        ),
        evidence_store=SQLiteResearchEvidenceStore(
            app_config.research_database_path
        ),
        artifact_store=ContentAddressedResearchArtifactStore(
            app_config.research_artifact_root
        ),
        software_identity_provider=provider,
        retrieve_candles=retrieve_backtest_candles,
        execute_candles=execute_backtest_candles,
    )


def execute_backtest_request(
    request: BacktestRunRequest,
    *,
    app_config: AppConfig | None = None,
    historical_source: HistoricalSource | None = None,
    software_identity_provider: SoftwareIdentityProvider | None = None,
    successor_context: (
        SuccessorBacktestApplicationContext
        | None
    ) = None,
) -> BacktestRunResponse:
    resolved_app_config = (
        app_config
        if app_config is not None
        else load_app_config()
    )

    config = BacktestConfig(
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy_name=request.strategy_id,
        start=request.start,
        end=request.end,
        initial_capital=request.initial_capital,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        strategy_params=request.strategy_params.model_dump(),
        timezone=request.timezone,
    )

    dataset_context = DatasetContext(
        symbol=request.symbol,
        timeframe=request.timeframe,
        timezone=request.timezone,
    )

    if (
        successor_context is not None
        and historical_source is not None
    ):
        raise ValueError(
            "historical_source and successor_context "
            "cannot be supplied together"
        )

    if (
        successor_context is not None
        and request.symbol
        != successor_context.request_symbol
    ):
        raise ValueError(
            "successor context symbol does not match "
            "the Backtest request"
        )

    source = None

    if successor_context is None:
        source = (
            historical_source
            if historical_source is not None
            else create_historical_source(
                resolved_app_config
            )
        )

    strategy = create_strategy(config)

    runtime_context = RuntimeContext(
        risk_per_trade_pct=(
            resolved_app_config.risk_per_trade_pct
        ),
    )

    orchestrator = (
        _create_backtest_research_orchestrator(
            resolved_app_config,
            software_identity_provider=(
                software_identity_provider
            ),
        )
    )

    if successor_context is None:
        research_execution = orchestrator.execute(
            historical_source=source,
            strategy=strategy,
            config=config,
            runtime_context=runtime_context,
            dataset_context=dataset_context,
        )
    else:
        research_execution = (
            SuccessorBacktestResearchCoordinator(
                retrieval_service=(
                    successor_context.retrieval_service
                ),
                orchestrator=orchestrator,
            ).execute(
                strategy=strategy,
                config=config,
                runtime_context=runtime_context,
                dataset_context=dataset_context,
                instrument_id=(
                    successor_context.instrument_id
                ),
                provider=(
                    successor_context.provider
                ),
                price_adjustment_basis=(
                    successor_context
                    .price_adjustment_basis
                ),
            )
        )

    result = research_execution.result

    summary = BacktestSummaryResponse.model_validate(
        PerformanceMetrics.summarize_backtest(result)
    )

    trades = []
    for trade in result.trades:
        if trade.exit_time is None:
            raise ValueError(
                "completed Backtest trade requires exit_time"
            )

        trades.append(
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
        )

    return BacktestRunResponse(
        run_id=result.session_id,
        attempt_id=research_execution.attempt_id,
        evidence_id=research_execution.evidence_id,
        evidence_status=(
            research_execution.evidence_status.value
        ),
        status="completed",
        symbol=request.symbol,
        timeframe=request.timeframe,
        strategy_id=request.strategy_id,
        start=request.start,
        end=request.end,
        timezone=request.timezone,
        summary=summary,
        equity_curve=[
            BacktestEquityPoint(
                timestamp=timestamp,
                equity=equity,
            )
            for timestamp, equity in result.equity_curve
        ],
        trades=trades,
    )

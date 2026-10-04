from collections.abc import Callable
from datetime import datetime, timezone

from core.config.backtest_config import BacktestConfig
from core.market_data.historical_coverage import TimeRange
from core.research.backtest_research_orchestrator import (
    AuthoritativeResearchStateError,
    BacktestResearchExecution,
    BacktestResearchOrchestrator,
    PreparedBacktestResearchSpecification,
    PreparedResearchRetrieval,
    PreparedResearchSpecificationError,
)
from core.research.models.dataset import (
    DatasetIdentityV2,
    DatasetProvenance,
    PriceAdjustmentBasis,
)
from core.research.models.dataset_reference import (
    DatasetReference,
)
from core.research.research_artifact_store import (
    research_artifact_reference,
)
from core.research.successor_historical_retrieval import (
    SuccessorHistoricalRetrievalService,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SuccessorHistoricalRetrievalError(RuntimeError):
    """Provider/dataset retrieval failed before specification building."""

    def __init__(
        self,
        original_error: Exception,
    ) -> None:
        self.original_error = original_error
        super().__init__(str(original_error))


class SuccessorBacktestResearchCoordinator:
    """
    Add successor dataset truth to the existing Backtest research path.

    Production activation is intentionally external to this class. The
    caller must supply the canonical instrument and provider explicitly.
    """

    def __init__(
        self,
        *,
        retrieval_service: SuccessorHistoricalRetrievalService,
        orchestrator: BacktestResearchOrchestrator,
        clock: Clock | None = None,
    ):
        self.retrieval_service = retrieval_service
        self.orchestrator = orchestrator
        self._clock = clock or _utc_now

    def prepare_specification(
        self,
        *,
        strategy: BaseStrategy,
        config: BacktestConfig,
        runtime_context: RuntimeContext,
        dataset_context: DatasetContext,
        instrument_id: str,
        provider: str,
        price_adjustment_basis: PriceAdjustmentBasis,
    ) -> PreparedBacktestResearchSpecification:
        """
        Prepare exact successor dataset/specification without execution.

        M9.4 uses this seam to decide exact evidence reuse before any
        new physical Backtest RunAttempt is created.
        """

        requested_range = TimeRange(
            config.start,
            config.end,
        )

        def prepare() -> PreparedResearchRetrieval:
            try:
                retrieval = self.retrieval_service.retrieve(
                    dataset_context,
                    requested_range,
                    instrument_id=instrument_id,
                    provider=provider,
                    price_adjustment_basis=(
                        price_adjustment_basis
                    ),
                )
            except Exception as error:
                raise SuccessorHistoricalRetrievalError(
                    error
                ) from error

            try:
                candles = list(
                    retrieval.candles
                )

                identity = DatasetIdentityV2(
                    instrument_id=instrument_id,
                    requested_range=requested_range,
                    timeframe=config.timeframe,
                    timezone=config.timezone,
                    price_adjustment_basis=(
                        price_adjustment_basis
                    ),
                    candles=candles,
                )

                created_at = self._clock()

                limitations = (
                    (
                        "price adjustment basis is unknown",
                    )
                    if (
                        price_adjustment_basis
                        is PriceAdjustmentBasis.UNKNOWN
                    )
                    else ()
                )

                provenance = DatasetProvenance(
                    dataset_id=identity.dataset_id,
                    instrument_id=instrument_id,
                    requested_range=requested_range,
                    timeframe=config.timeframe,
                    timezone=config.timezone,
                    price_adjustment_basis=(
                        price_adjustment_basis
                    ),
                    source=retrieval.source,
                    binding_segments=(
                        retrieval.binding_segments
                    ),
                    coverage=retrieval.coverage,
                    retrieved_at=created_at,
                    limitations=limitations,
                )

                reference = DatasetReference(
                    identity=identity,
                    provenance=provenance,
                )

                try:
                    artifact = (
                        self.orchestrator
                        .artifact_store
                        .persist_dataset_reference(
                            reference,
                            created_at=created_at,
                        )
                    )

                    artifact = (
                        self.orchestrator
                        .catalog_store
                        .save_artifact(
                            artifact
                        )
                    )
                except Exception as error:
                    raise AuthoritativeResearchStateError(
                        error
                    ) from error

                return PreparedResearchRetrieval(
                    candles=candles,
                    artifact_references=(
                        research_artifact_reference(
                            artifact.artifact_id
                        ),
                    ),
                )

            except AuthoritativeResearchStateError:
                raise
            except Exception as error:
                raise PreparedResearchSpecificationError(
                    error
                ) from error

        return self.orchestrator.prepare_specification(
            historical_source=None,
            strategy=strategy,
            config=config,
            runtime_context=runtime_context,
            dataset_context=dataset_context,
            prepared_retrieval=prepare,
        )

    def execute(
        self,
        *,
        strategy: BaseStrategy,
        config: BacktestConfig,
        runtime_context: RuntimeContext,
        dataset_context: DatasetContext,
        instrument_id: str,
        provider: str,
        price_adjustment_basis: PriceAdjustmentBasis,
    ) -> BacktestResearchExecution:
        prepared = self.prepare_specification(
            strategy=strategy,
            config=config,
            runtime_context=runtime_context,
            dataset_context=dataset_context,
            instrument_id=instrument_id,
            provider=provider,
            price_adjustment_basis=(
                price_adjustment_basis
            ),
        )

        return self.orchestrator.execute_prepared(
            prepared=prepared,
            strategy=strategy,
            config=config,
            runtime_context=runtime_context,
            dataset_context=dataset_context,
        )

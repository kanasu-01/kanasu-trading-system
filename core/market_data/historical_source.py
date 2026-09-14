from collections.abc import Callable

from core.config.historical_source_policy import HistoricalSourcePolicy
from core.entities.candle import Candle
from core.market_data.historical_coverage import (
    TimeRange,
    find_missing_ranges,
)
from core.market_data.historical_retrieval import (
    HistoricalProvider,
    IncompleteHistoricalCoverageError,
    LocalFirstHistoricalService,
    load_half_open_candles,
    validate_historical_fetch_result,
)
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.runtime.dataset_context import DatasetContext


ProviderFactory = Callable[[], HistoricalProvider]


class HistoricalSource:
    def __init__(
        self,
        store: SQLiteCandleStore,
        policy: HistoricalSourcePolicy,
        provider_factory: ProviderFactory | None = None,
    ):
        self.store = store
        self.policy = policy
        self.provider_factory = provider_factory

    def retrieve(
        self,
        context: DatasetContext,
        request: TimeRange,
    ) -> list[Candle]:
        if self.policy is HistoricalSourcePolicy.LOCAL_ONLY:
            return self._retrieve_local_only(context, request)

        if self.policy is HistoricalSourcePolicy.LOCAL_FIRST:
            return self._retrieve_local_first(context, request)

        if self.policy is HistoricalSourcePolicy.PROVIDER_BACKED:
            return self._retrieve_provider_backed(context, request)

        raise ValueError(f"unsupported historical source policy: {self.policy}")

    def _retrieve_local_only(
        self,
        context: DatasetContext,
        request: TimeRange,
    ) -> list[Candle]:
        missing_ranges = find_missing_ranges(
            request,
            self.store.load_coverage(context),
        )
        if missing_ranges:
            raise IncompleteHistoricalCoverageError(missing_ranges)
        return load_half_open_candles(self.store, context, request)

    def _retrieve_local_first(
        self,
        context: DatasetContext,
        request: TimeRange,
    ) -> list[Candle]:
        missing_ranges = find_missing_ranges(
            request,
            self.store.load_coverage(context),
        )
        if not missing_ranges:
            return load_half_open_candles(self.store, context, request)

        provider = self._create_required_provider()
        return LocalFirstHistoricalService(
            self.store,
            provider,
        ).retrieve(context, request)

    def _retrieve_provider_backed(
        self,
        context: DatasetContext,
        request: TimeRange,
    ) -> list[Candle]:
        provider = self._create_required_provider()
        result = provider.fetch(context, request)
        validate_historical_fetch_result(request, result)

        missing_ranges = find_missing_ranges(
            request,
            list(result.coverage),
        )
        if missing_ranges:
            raise IncompleteHistoricalCoverageError(missing_ranges)

        self.store.save_retrieval(
            context,
            list(result.candles),
            list(result.coverage),
        )
        return load_half_open_candles(self.store, context, request)

    def _create_required_provider(self) -> HistoricalProvider:
        if self.provider_factory is None:
            raise RuntimeError(
                "historical provider is required by source policy"
            )
        return self.provider_factory()

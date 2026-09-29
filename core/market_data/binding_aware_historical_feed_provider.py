from core.market_data.historical_feed import HistoricalFeed
from core.market_data.historical_retrieval import (
    HistoricalFetchResult,
    validate_historical_fetch_result,
)
from core.market_data.historical_coverage import TimeRange
from core.market_data.provider_instrument_binding import (
    ProviderInstrumentBinding,
    resolve_provider_bindings,
)
from core.runtime.dataset_context import DatasetContext


class BindingAwareHistoricalFeedProvider:
    """
    Fetch one explicitly bound historical subrange.

    This adapter is parallel to HistoricalFeedProvider. It does not
    change the legacy HistoricalProvider contract and deliberately does
    not perform multi-binding orchestration.
    """

    def __init__(
        self,
        feed: HistoricalFeed,
    ):
        self.feed = feed

    def fetch(
        self,
        context: DatasetContext,
        request: TimeRange,
        *,
        provider_binding: ProviderInstrumentBinding,
    ) -> HistoricalFetchResult:
        if not isinstance(
            provider_binding,
            ProviderInstrumentBinding,
        ):
            raise TypeError(
                "provider_binding must be a "
                "ProviderInstrumentBinding"
            )

        resolved = resolve_provider_bindings(
            instrument_id=provider_binding.instrument_id,
            provider=provider_binding.provider,
            request=request,
            bindings=(provider_binding,),
        )

        if (
            len(resolved) != 1
            or resolved[0].applied_range != request
        ):
            raise ValueError(
                "provider binding must cover the exact "
                "requested subrange"
            )

        candles = tuple(
            candle
            for candle in self.feed.stream_with_binding(
                symbol=context.symbol,
                timeframe=context.timeframe,
                start=request.start,
                end=request.end,
                provider_binding=provider_binding,
            )
            if candle.timestamp != request.end
        )

        result = HistoricalFetchResult(
            candles=candles,
            coverage=(request,),
        )

        validate_historical_fetch_result(
            request,
            result,
        )

        return result

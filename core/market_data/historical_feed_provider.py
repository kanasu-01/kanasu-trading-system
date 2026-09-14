from core.market_data.historical_feed import HistoricalFeed
from core.market_data.historical_retrieval import (
    HistoricalFetchResult,
    validate_historical_fetch_result,
)
from core.market_data.historical_coverage import TimeRange
from core.runtime.dataset_context import DatasetContext


class HistoricalFeedProvider:
    """Adapt a completed HistoricalFeed stream to HistoricalProvider."""

    def __init__(self, feed: HistoricalFeed):
        self.feed = feed

    def fetch(
        self,
        context: DatasetContext,
        request: TimeRange,
    ) -> HistoricalFetchResult:
        candles = tuple(
            candle
            for candle in self.feed.stream(
                symbol=context.symbol,
                timeframe=context.timeframe,
                start=request.start,
                end=request.end,
            )
            if candle.timestamp != request.end
        )
        result = HistoricalFetchResult(
            candles=candles,
            coverage=(request,),
        )
        validate_historical_fetch_result(request, result)
        return result

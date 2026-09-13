from dataclasses import dataclass
from typing import Protocol

from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.market_data.historical_coverage import (
    TimeRange,
    find_missing_ranges,
)
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.runtime.dataset_context import DatasetContext


def _is_timezone_aware(timestamp) -> bool:
    return timestamp.utcoffset() is not None


@dataclass(frozen=True)
class HistoricalFetchResult:
    candles: tuple[Candle, ...]
    coverage: tuple[TimeRange, ...]


class HistoricalProvider(Protocol):
    def fetch(
        self,
        context: DatasetContext,
        request: TimeRange,
    ) -> HistoricalFetchResult:
        ...


class IncompleteHistoricalCoverageError(RuntimeError):
    def __init__(self, missing_ranges: list[TimeRange]):
        self.missing_ranges = tuple(missing_ranges)
        super().__init__(
            "historical retrieval remains incomplete; "
            f"{len(self.missing_ranges)} range(s) are still uncovered"
        )


class LocalFirstHistoricalService:
    def __init__(
        self,
        store: SQLiteCandleStore,
        provider: HistoricalProvider,
    ):
        self.store = store
        self.provider = provider

    def retrieve(
        self,
        context: DatasetContext,
        request: TimeRange,
    ) -> list[Candle]:
        missing_ranges = find_missing_ranges(
            request,
            self.store.load_coverage(context),
        )

        for missing_range in missing_ranges:
            result = self.provider.fetch(context, missing_range)
            self._validate_result(missing_range, result)
            self.store.save_retrieval(
                context,
                list(result.candles),
                list(result.coverage),
            )

        remaining = find_missing_ranges(
            request,
            self.store.load_coverage(context),
        )
        if remaining:
            raise IncompleteHistoricalCoverageError(remaining)

        return self._load_half_open(context, request)

    @staticmethod
    def _validate_result(
        requested_gap: TimeRange,
        result: HistoricalFetchResult,
    ) -> None:
        if not result.coverage:
            raise ValueError(
                "provider result requires explicit coverage evidence"
            )

        gap_is_aware = _is_timezone_aware(requested_gap.start)

        for interval in result.coverage:
            if _is_timezone_aware(interval.start) != gap_is_aware:
                raise ValueError(
                    "provider coverage and requested gap timezone "
                    "awareness must match"
                )

            if (
                interval.start < requested_gap.start
                or interval.end > requested_gap.end
            ):
                raise ValueError(
                    "provider coverage must be contained within "
                    "the requested gap"
                )

        for candle in result.candles:
            timestamp = candle.timestamp
            if _is_timezone_aware(timestamp) != gap_is_aware:
                raise ValueError(
                    "provider candle and requested gap timezone "
                    "awareness must match"
                )

            if not (
                requested_gap.start
                <= timestamp
                < requested_gap.end
            ):
                raise ValueError(
                    "provider candle must be within the requested gap"
                )

            if not any(
                interval.start <= timestamp < interval.end
                for interval in result.coverage
            ):
                raise ValueError(
                    "provider candle must be within explicit coverage"
                )

        CandleSeries(list(result.candles))

    def _load_half_open(
        self,
        context: DatasetContext,
        request: TimeRange,
    ) -> list[Candle]:
        inclusive_candles = self.store.load(
            context,
            start=request.start,
            end=request.end,
        )
        candles = [
            candle
            for candle in inclusive_candles
            if candle.timestamp < request.end
        ]
        CandleSeries(candles)
        return candles

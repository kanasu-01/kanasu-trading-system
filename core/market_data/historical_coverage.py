from dataclasses import dataclass
from datetime import datetime
from typing import Iterable


def _is_timezone_aware(timestamp: datetime) -> bool:
    return timestamp.utcoffset() is not None


@dataclass(frozen=True)
class TimeRange:
    """A non-empty half-open temporal interval: [start, end)."""

    start: datetime
    end: datetime

    def __post_init__(self) -> None:
        if _is_timezone_aware(self.start) != _is_timezone_aware(self.end):
            raise ValueError(
                "time range timezone awareness must match"
            )

        if self.start >= self.end:
            raise ValueError(
                "time range start must be before end"
            )


def find_missing_ranges(
    request: TimeRange,
    coverage: Iterable[TimeRange],
) -> list[TimeRange]:
    """Return chronological uncovered portions of a requested time range."""

    request_is_aware = _is_timezone_aware(request.start)
    relevant_coverage: list[TimeRange] = []

    for interval in coverage:
        if _is_timezone_aware(interval.start) != request_is_aware:
            raise ValueError(
                "request and coverage timezone awareness must match"
            )

        if interval.end <= request.start or interval.start >= request.end:
            continue

        relevant_coverage.append(
            TimeRange(
                start=(
                    request.start
                    if interval.start < request.start
                    else interval.start
                ),
                end=(
                    request.end
                    if interval.end > request.end
                    else interval.end
                ),
            )
        )

    relevant_coverage.sort(key=lambda interval: interval.start)

    merged_coverage: list[TimeRange] = []
    for interval in relevant_coverage:
        if (
            not merged_coverage
            or interval.start > merged_coverage[-1].end
        ):
            merged_coverage.append(interval)
            continue

        previous = merged_coverage[-1]
        if interval.end > previous.end:
            merged_coverage[-1] = TimeRange(
                start=previous.start,
                end=interval.end,
            )

    missing: list[TimeRange] = []
    cursor = request.start

    for interval in merged_coverage:
        if cursor < interval.start:
            missing.append(
                TimeRange(start=cursor, end=interval.start)
            )
        if interval.end > cursor:
            cursor = interval.end

    if cursor < request.end:
        missing.append(TimeRange(start=cursor, end=request.end))

    return missing

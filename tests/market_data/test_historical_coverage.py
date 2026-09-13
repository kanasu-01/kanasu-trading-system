from datetime import datetime, timedelta, timezone

import pytest

from core.market_data.historical_coverage import (
    TimeRange,
    find_missing_ranges,
)


BASE = datetime(2026, 1, 2, 9, 0)


def at(minutes: int) -> datetime:
    return BASE + timedelta(minutes=minutes)


def time_range(start_minutes: int, end_minutes: int) -> TimeRange:
    return TimeRange(start=at(start_minutes), end=at(end_minutes))


REQUEST = time_range(0, 60)


def test_no_coverage_returns_entire_request():
    assert find_missing_ranges(REQUEST, []) == [REQUEST]


def test_full_coverage_returns_nothing_missing():
    assert find_missing_ranges(REQUEST, [time_range(0, 60)]) == []


@pytest.mark.parametrize(
    "coverage",
    [
        pytest.param([time_range(-60, 0)], id="entirely-before"),
        pytest.param([time_range(60, 120)], id="entirely-after"),
    ],
)
def test_coverage_outside_request_leaves_request_unchanged(coverage):
    assert find_missing_ranges(REQUEST, coverage) == [REQUEST]


@pytest.mark.parametrize(
    ("coverage", "expected"),
    [
        pytest.param(
            [time_range(0, 15)],
            [time_range(15, 60)],
            id="covered-beginning",
        ),
        pytest.param(
            [time_range(45, 60)],
            [time_range(0, 45)],
            id="covered-end",
        ),
    ],
)
def test_partial_edge_coverage_returns_remaining_range(coverage, expected):
    assert find_missing_ranges(REQUEST, coverage) == expected


def test_internal_coverage_returns_two_missing_ranges():
    assert find_missing_ranges(
        REQUEST,
        [time_range(15, 30)],
    ) == [
        time_range(0, 15),
        time_range(30, 60),
    ]


def test_multiple_disjoint_intervals_return_every_gap_chronologically():
    assert find_missing_ranges(
        REQUEST,
        [
            time_range(10, 20),
            time_range(30, 40),
            time_range(50, 55),
        ],
    ) == [
        time_range(0, 10),
        time_range(20, 30),
        time_range(40, 50),
        time_range(55, 60),
    ]


@pytest.mark.parametrize(
    "coverage",
    [
        pytest.param(
            [time_range(0, 35), time_range(20, 60)],
            id="overlapping",
        ),
        pytest.param(
            [time_range(0, 30), time_range(30, 60)],
            id="touching",
        ),
        pytest.param(
            [time_range(0, 60), time_range(15, 30)],
            id="nested",
        ),
        pytest.param(
            [time_range(0, 60), time_range(0, 60)],
            id="duplicate",
        ),
        pytest.param(
            [time_range(30, 60), time_range(0, 30)],
            id="unordered",
        ),
    ],
)
def test_coverage_is_normalized_for_planning(coverage):
    assert find_missing_ranges(REQUEST, coverage) == []


def test_coverage_is_logically_clipped_to_request():
    assert find_missing_ranges(
        REQUEST,
        [
            time_range(-30, 15),
            time_range(45, 90),
        ],
    ) == [time_range(15, 45)]


def test_half_open_request_boundaries_do_not_create_false_coverage():
    assert find_missing_ranges(
        REQUEST,
        [
            time_range(-30, 0),
            time_range(60, 90),
        ],
    ) == [REQUEST]


def test_missing_ranges_are_non_empty_ordered_and_non_overlapping():
    missing = find_missing_ranges(
        REQUEST,
        [
            time_range(45, 50),
            time_range(5, 10),
            time_range(20, 30),
            time_range(8, 15),
        ],
    )

    assert missing == [
        time_range(0, 5),
        time_range(15, 20),
        time_range(30, 45),
        time_range(50, 60),
    ]
    assert all(interval.start < interval.end for interval in missing)
    assert all(
        earlier.end <= later.start
        for earlier, later in zip(missing, missing[1:])
    )


@pytest.mark.parametrize(
    ("start_minutes", "end_minutes"),
    [
        pytest.param(0, 0, id="empty"),
        pytest.param(60, 0, id="reversed"),
    ],
)
def test_invalid_request_range_is_rejected(start_minutes, end_minutes):
    with pytest.raises(ValueError, match="start.*before.*end|invalid"):
        request = time_range(start_minutes, end_minutes)
        find_missing_ranges(request, [])


@pytest.mark.parametrize(
    ("start_minutes", "end_minutes"),
    [
        pytest.param(15, 15, id="empty"),
        pytest.param(30, 15, id="reversed"),
    ],
)
def test_invalid_coverage_range_is_rejected(start_minutes, end_minutes):
    with pytest.raises(ValueError, match="start.*before.*end|invalid"):
        coverage = time_range(start_minutes, end_minutes)
        find_missing_ranges(REQUEST, [coverage])


@pytest.mark.parametrize(
    ("requested_range", "coverage"),
    [
        pytest.param(
            TimeRange(
                datetime(2026, 1, 2, 9, 0),
                datetime(2026, 1, 2, 10, 0),
            ),
            [
                TimeRange(
                    datetime(2026, 1, 2, 9, 15, tzinfo=timezone.utc),
                    datetime(2026, 1, 2, 9, 30, tzinfo=timezone.utc),
                )
            ],
            id="naive-request-aware-coverage",
        ),
        pytest.param(
            TimeRange(
                datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
            ),
            [
                TimeRange(
                    datetime(2026, 1, 2, 9, 15),
                    datetime(2026, 1, 2, 9, 30),
                )
            ],
            id="aware-request-naive-coverage",
        ),
    ],
)
def test_mixed_request_and_coverage_timezone_awareness_is_rejected(
    requested_range,
    coverage,
):
    with pytest.raises(ValueError, match="timezone"):
        find_missing_ranges(requested_range, coverage)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        pytest.param(
            datetime(2026, 1, 2, 9, 0),
            datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
            id="naive-start-aware-end",
        ),
        pytest.param(
            datetime(2026, 1, 2, 9, 0, tzinfo=timezone.utc),
            datetime(2026, 1, 2, 10, 0),
            id="aware-start-naive-end",
        ),
    ],
)
def test_mixed_timezone_awareness_within_range_is_rejected(start, end):
    with pytest.raises(ValueError, match="timezone"):
        TimeRange(start=start, end=end)


def test_different_aware_offsets_use_normal_datetime_comparison():
    india = timezone(timedelta(hours=5, minutes=30))
    request = TimeRange(
        start=datetime(2026, 1, 2, 9, 0, tzinfo=india),
        end=datetime(2026, 1, 2, 10, 0, tzinfo=india),
    )
    coverage = TimeRange(
        start=datetime(2026, 1, 2, 3, 45, tzinfo=timezone.utc),
        end=datetime(2026, 1, 2, 4, 15, tzinfo=timezone.utc),
    )

    assert find_missing_ranges(request, [coverage]) == [
        TimeRange(
            start=request.start,
            end=coverage.start,
        ),
        TimeRange(
            start=coverage.end,
            end=request.end,
        ),
    ]

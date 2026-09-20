from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.walk_forward.equity_stitcher import EquityStitcher


START = datetime(2026, 1, 2, 9, 15)


def window(index, points):
    return SimpleNamespace(
        window_index=index,
        backtest_result=SimpleNamespace(
            equity_curve=points,
        ),
    )


def test_empty_window_collection_returns_empty_curve():
    assert EquityStitcher.stitch([]) == []


def test_non_overlapping_windows_compound_continuously():
    windows = [
        window(
            0,
            [
                (START, 100.0),
                (START + timedelta(minutes=15), 110.0),
            ],
        ),
        window(
            1,
            [
                (START + timedelta(minutes=30), 200.0),
                (START + timedelta(minutes=45), 180.0),
            ],
        ),
    ]

    stitched = EquityStitcher.stitch(windows)

    assert [equity for _, equity in stitched] == pytest.approx(
        [100.0, 110.0, 110.0, 99.0]
    )


@pytest.mark.parametrize(
    "second_start",
    [
        START,
        START + timedelta(minutes=15),
    ],
)
def test_overlapping_or_duplicate_oos_timestamps_are_rejected(
    second_start,
):
    windows = [
        window(
            0,
            [
                (START, 100.0),
                (START + timedelta(minutes=15), 110.0),
            ],
        ),
        window(
            1,
            [
                (second_start, 100.0),
                (START + timedelta(minutes=30), 105.0),
            ],
        ),
    ]

    with pytest.raises(
        ValueError,
        match="strictly increasing and non-overlapping",
    ):
        EquityStitcher.stitch(windows)


def test_empty_oos_equity_window_is_rejected():
    with pytest.raises(
        ValueError,
        match="requires OOS equity records",
    ):
        EquityStitcher.stitch([window(0, [])])


@pytest.mark.parametrize("starting_equity", [0.0, -1.0])
def test_non_positive_window_start_is_rejected(starting_equity):
    with pytest.raises(ValueError, match="strictly positive"):
        EquityStitcher.stitch(
            [window(0, [(START, starting_equity)])]
        )


@pytest.mark.parametrize(
    "equity",
    [float("nan"), float("inf"), float("-inf")],
)
def test_non_finite_window_equity_is_rejected(equity):
    with pytest.raises(ValueError, match="must be finite"):
        EquityStitcher.stitch(
            [
                window(
                    0,
                    [
                        (START, 100.0),
                        (
                            START + timedelta(minutes=15),
                            equity,
                        ),
                    ],
                )
            ]
        )


@pytest.mark.parametrize("ending_equity", [0.0, -10.0])
def test_stitching_cannot_continue_after_capital_is_exhausted(
    ending_equity,
):
    windows = [
        window(
            0,
            [
                (START, 100.0),
                (START + timedelta(minutes=15), ending_equity),
            ],
        ),
        window(
            1,
            [
                (START + timedelta(minutes=30), 100.0),
            ],
        ),
    ]

    with pytest.raises(
        ValueError,
        match="cannot continue after non-positive equity",
    ):
        EquityStitcher.stitch(windows)


def test_first_window_equity_is_preserved_without_normalization():
    curve = [
        (START, 100_000.0),
        (START + timedelta(minutes=15), 110_000.0),
        (START + timedelta(minutes=30), 88_000.0),
        (START + timedelta(minutes=45), 101_000.0),
    ]

    assert EquityStitcher.stitch(
        [window(0, curve)]
    ) == curve


def test_scale_one_preserves_later_window_equity_exactly():
    windows = [
        window(
            0,
            [
                (START, 100.0),
                (START + timedelta(minutes=15), 110.0),
            ],
        ),
        window(
            1,
            [
                (START + timedelta(minutes=30), 110.0),
                (START + timedelta(minutes=45), 88.0),
            ],
        ),
    ]

    stitched = EquityStitcher.stitch(windows)

    assert stitched == [
        (START, 100.0),
        (START + timedelta(minutes=15), 110.0),
        (START + timedelta(minutes=30), 110.0),
        (START + timedelta(minutes=45), 88.0),
    ]

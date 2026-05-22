from datetime import datetime, timedelta

from core.entities.candle import Candle

from core.walk_forward.window_generator import (
    WalkForwardWindowGenerator,
)


def build_dummy_candles(count: int):

    candles = []

    base_time = datetime(2020, 1, 1)

    for i in range(count):

        candles.append(
            Candle(
                timestamp=(base_time + timedelta(minutes=i)),
                open=100,
                high=101,
                low=99,
                close=100,
                volume=1000,
            )
        )

    return candles


def test_generates_expected_number_of_windows():

    candles = build_dummy_candles(1000)

    generator = WalkForwardWindowGenerator(
        in_sample_bars=300,
        out_sample_bars=100,
        step_bars=100,
        mode="rolling",
    )

    windows = list(generator.generate(candles))

    assert len(windows) == 7


def test_returns_no_windows_when_data_insufficient():

    candles = build_dummy_candles(200)

    generator = WalkForwardWindowGenerator(
        in_sample_bars=300,
        out_sample_bars=100,
        step_bars=100,
        mode="rolling",
    )

    windows = list(generator.generate(candles))

    assert len(windows) == 0


def test_each_window_has_expected_sizes():

    candles = build_dummy_candles(1000)

    generator = WalkForwardWindowGenerator(
        in_sample_bars=300,
        out_sample_bars=100,
        step_bars=100,
        mode="rolling",
    )

    windows = list(generator.generate(candles))

    for window in windows:

        assert len(window.train_bars) == 300

        assert len(window.test_bars) == 100

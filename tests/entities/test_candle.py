from datetime import datetime

import pytest

from core.entities.candle import Candle


def valid_candle_values() -> dict:
    return {
        "timestamp": datetime(2026, 1, 2, 9, 15),
        "open": 100.0,
        "high": 101.0,
        "low": 99.0,
        "close": 100.5,
        "volume": 1000.0,
    }


@pytest.mark.parametrize("field", ["open", "high", "low", "close", "volume"])
@pytest.mark.parametrize(
    "non_finite_value",
    [float("nan"), float("inf"), float("-inf")],
    ids=["nan", "positive_infinity", "negative_infinity"],
)
def test_candle_rejects_non_finite_ohlcv(field, non_finite_value):
    values = valid_candle_values()
    values[field] = non_finite_value

    with pytest.raises(ValueError):
        Candle(**values)


def test_candle_accepts_normal_finite_values():
    candle = Candle(**valid_candle_values())

    assert candle.open == 100.0
    assert candle.high == 101.0
    assert candle.low == 99.0
    assert candle.close == 100.5
    assert candle.volume == 1000.0


def test_candle_accepts_integer_numeric_inputs():
    candle = Candle(
        timestamp=datetime(2026, 1, 2, 9, 15),
        open=100,
        high=101,
        low=99,
        close=100,
        volume=1000,
    )

    assert candle.open == 100
    assert candle.high == 101
    assert candle.low == 99
    assert candle.close == 100
    assert candle.volume == 1000


def test_candle_accepts_zero_volume():
    values = valid_candle_values()
    values["volume"] = 0

    candle = Candle(**values)

    assert candle.volume == 0

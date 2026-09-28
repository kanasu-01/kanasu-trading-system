from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from core.entities.instrument import Instrument


def test_instrument_uses_explicit_canonical_identity():
    instrument = Instrument(
        instrument_id="NSE-EQ-RELIANCE",
        symbol="RELIANCE",
        exchange="NSE",
        segment="EQ",
    )

    assert instrument.instrument_id == "NSE-EQ-RELIANCE"
    assert instrument.symbol == "RELIANCE"
    assert instrument.exchange == "NSE"
    assert instrument.segment == "EQ"


def test_symbol_change_can_preserve_canonical_identity():
    old = Instrument(
        instrument_id="NSE-EQ-ABC",
        symbol="ABC",
        effective_to=datetime(2026, 1, 1),
    )
    new = Instrument(
        instrument_id="NSE-EQ-ABC",
        symbol="XYZ",
        effective_from=datetime(2026, 1, 1),
    )

    assert old.instrument_id == new.instrument_id
    assert old.symbol != new.symbol


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("instrument_id", ""),
        ("symbol", ""),
        ("exchange", ""),
        ("segment", ""),
    ],
)
def test_instrument_rejects_empty_identity_metadata(field, value):
    values = {
        "instrument_id": "NSE-EQ-RELIANCE",
        "symbol": "RELIANCE",
        "exchange": "NSE",
        "segment": "EQ",
    }
    values[field] = value

    with pytest.raises(ValueError):
        Instrument(**values)


@pytest.mark.parametrize(
    "tick_size",
    [0, -0.05, float("nan"), float("inf"), float("-inf"), True],
)
def test_instrument_rejects_invalid_tick_size(tick_size):
    with pytest.raises(ValueError):
        Instrument(
            instrument_id="NSE-EQ-RELIANCE",
            symbol="RELIANCE",
            tick_size=tick_size,
        )


@pytest.mark.parametrize("lot_size", [0, -1, 1.5, True])
def test_instrument_rejects_invalid_lot_size(lot_size):
    with pytest.raises(ValueError):
        Instrument(
            instrument_id="NSE-EQ-RELIANCE",
            symbol="RELIANCE",
            lot_size=lot_size,
        )


def test_instrument_rejects_reversed_effective_range():
    with pytest.raises(ValueError, match="effective_from.*before"):
        Instrument(
            instrument_id="NSE-EQ-RELIANCE",
            symbol="RELIANCE",
            effective_from=datetime(2026, 2, 1),
            effective_to=datetime(2026, 1, 1),
        )


def test_instrument_rejects_mixed_effective_timezone_awareness():
    with pytest.raises(ValueError, match="timezone"):
        Instrument(
            instrument_id="NSE-EQ-RELIANCE",
            symbol="RELIANCE",
            effective_from=datetime(2026, 1, 1),
            effective_to=datetime(
                2026,
                2,
                1,
                tzinfo=timezone.utc,
            ),
        )


def test_instrument_is_immutable():
    instrument = Instrument(
        instrument_id="NSE-EQ-RELIANCE",
        symbol="RELIANCE",
    )

    with pytest.raises(FrozenInstanceError):
        instrument.symbol = "OTHER"

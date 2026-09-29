from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from core.entities.instrument import Instrument
from core.market_data.historical_coverage import TimeRange
from core.market_data.instrument_registry import (
    InstrumentRegistryError,
    StaticInstrumentRegistry,
)
from core.market_data.provider_instrument_binding import (
    ProviderInstrumentBinding,
)


START = datetime(2026, 1, 1)
TRANSITION = datetime(2026, 6, 1)
END = datetime(2027, 1, 1)


def instrument(
    *,
    instrument_id="NSE-EQ-ABC",
    symbol="ABC",
    effective_from=START,
    effective_to=END,
):
    return Instrument(
        instrument_id=instrument_id,
        symbol=symbol,
        exchange="NSE",
        segment="EQ",
        effective_from=effective_from,
        effective_to=effective_to,
    )


def binding(
    *,
    binding_id="angelone-abc-v1",
    instrument_id="NSE-EQ-ABC",
    token="100",
    effective_from=START,
    effective_to=END,
):
    return ProviderInstrumentBinding(
        binding_id=binding_id,
        instrument_id=instrument_id,
        provider="angelone",
        provider_instrument_id=token,
        provider_exchange="NSE",
        provider_segment="EQ",
        provider_symbol="ABC",
        effective_from=effective_from,
        effective_to=effective_to,
    )


def test_registry_resolves_canonical_identity_inside_effective_range():
    registry = StaticInstrumentRegistry(
        instruments=(instrument(),),
        provider_bindings=(),
    )

    resolved = registry.resolve_symbol(
        symbol="ABC",
        exchange="NSE",
        at=datetime(2026, 2, 1),
    )

    assert resolved.instrument_id == "NSE-EQ-ABC"


def test_registry_does_not_resolve_before_instrument_effective_range():
    registry = StaticInstrumentRegistry(
        instruments=(instrument(),),
        provider_bindings=(),
    )

    with pytest.raises(
        InstrumentRegistryError,
        match="could not be resolved",
    ):
        registry.resolve_symbol(
            symbol="ABC",
            exchange="NSE",
            at=datetime(2025, 12, 31),
        )


def test_registry_does_not_resolve_at_half_open_end_boundary():
    registry = StaticInstrumentRegistry(
        instruments=(instrument(),),
        provider_bindings=(),
    )

    with pytest.raises(
        InstrumentRegistryError,
        match="could not be resolved",
    ):
        registry.resolve_symbol(
            symbol="ABC",
            exchange="NSE",
            at=END,
        )


def test_registry_preserves_effective_dated_symbol_change():
    registry = StaticInstrumentRegistry(
        instruments=(
            instrument(
                instrument_id="NSE-EQ-CONTINUING",
                symbol="OLD",
                effective_from=START,
                effective_to=TRANSITION,
            ),
            instrument(
                instrument_id="NSE-EQ-CONTINUING",
                symbol="NEW",
                effective_from=TRANSITION,
                effective_to=END,
            ),
        ),
        provider_bindings=(),
    )

    old = registry.resolve_symbol(
        symbol="OLD",
        exchange="NSE",
        at=datetime(2026, 5, 1),
    )

    new = registry.resolve_symbol(
        symbol="NEW",
        exchange="NSE",
        at=TRANSITION,
    )

    assert old.instrument_id == "NSE-EQ-CONTINUING"
    assert new.instrument_id == "NSE-EQ-CONTINUING"


def test_registry_fails_closed_on_ambiguous_symbol_resolution():
    registry = StaticInstrumentRegistry(
        instruments=(
            instrument(
                instrument_id="NSE-EQ-ONE",
            ),
            instrument(
                instrument_id="NSE-EQ-TWO",
            ),
        ),
        provider_bindings=(),
    )

    with pytest.raises(
        InstrumentRegistryError,
        match="ambiguous",
    ):
        registry.resolve_symbol(
            symbol="ABC",
            exchange="NSE",
            at=datetime(2026, 2, 1),
        )


def test_registry_rejects_duplicate_binding_identity():
    with pytest.raises(
        InstrumentRegistryError,
        match="duplicated",
    ):
        StaticInstrumentRegistry(
            instruments=(instrument(),),
            provider_bindings=(
                binding(),
                binding(token="101"),
            ),
        )


def test_registry_rejects_orphan_provider_binding():
    with pytest.raises(
        InstrumentRegistryError,
        match="unknown canonical instrument",
    ):
        StaticInstrumentRegistry(
            instruments=(instrument(),),
            provider_bindings=(
                binding(
                    instrument_id="NSE-EQ-UNKNOWN",
                ),
            ),
        )


def test_registry_returns_candidate_bindings_deterministically():
    registry = StaticInstrumentRegistry(
        instruments=(instrument(),),
        provider_bindings=(
            binding(
                binding_id="binding-b",
                token="200",
            ),
            binding(
                binding_id="binding-a",
                token="100",
            ),
        ),
    )

    assert [
        value.binding_id
        for value in registry.bindings_for(
            instrument_id="NSE-EQ-ABC",
            provider="angelone",
        )
    ] == [
        "binding-a",
        "binding-b",
    ]


def test_registry_preserves_binding_transition_subranges():
    registry = StaticInstrumentRegistry(
        instruments=(instrument(),),
        provider_bindings=(
            binding(
                binding_id="angelone-abc-old",
                token="100",
                effective_from=START,
                effective_to=TRANSITION,
            ),
            binding(
                binding_id="angelone-abc-new",
                token="200",
                effective_from=TRANSITION,
                effective_to=END,
            ),
        ),
    )

    request = TimeRange(
        datetime(2026, 5, 1),
        datetime(2026, 7, 1),
    )

    resolved = registry.resolve_bindings(
        instrument_id="NSE-EQ-ABC",
        provider="angelone",
        request=request,
    )

    assert [
        value.binding.binding_id
        for value in resolved
    ] == [
        "angelone-abc-old",
        "angelone-abc-new",
    ]

    assert [
        value.applied_range
        for value in resolved
    ] == [
        TimeRange(
            datetime(2026, 5, 1),
            TRANSITION,
        ),
        TimeRange(
            TRANSITION,
            datetime(2026, 7, 1),
        ),
    ]


def test_registry_retains_binding_gap_failure():
    registry = StaticInstrumentRegistry(
        instruments=(instrument(),),
        provider_bindings=(
            binding(
                effective_from=START,
                effective_to=TRANSITION,
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="gap",
    ):
        registry.resolve_bindings(
            instrument_id="NSE-EQ-ABC",
            provider="angelone",
            request=TimeRange(
                datetime(2026, 5, 1),
                datetime(2026, 7, 1),
            ),
        )


def test_registry_rejects_resolution_awareness_mismatch():
    registry = StaticInstrumentRegistry(
        instruments=(
            instrument(
                effective_from=datetime(
                    2026,
                    1,
                    1,
                    tzinfo=timezone.utc,
                ),
                effective_to=datetime(
                    2027,
                    1,
                    1,
                    tzinfo=timezone.utc,
                ),
            ),
        ),
        provider_bindings=(),
    )

    with pytest.raises(
        InstrumentRegistryError,
        match="timezone awareness",
    ):
        registry.resolve_symbol(
            symbol="ABC",
            exchange="NSE",
            at=datetime(2026, 2, 1),
        )


def test_registry_is_immutable():
    registry = StaticInstrumentRegistry(
        instruments=(instrument(),),
        provider_bindings=(),
    )

    with pytest.raises(FrozenInstanceError):
        registry.instruments = ()

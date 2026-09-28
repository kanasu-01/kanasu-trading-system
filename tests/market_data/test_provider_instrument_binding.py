from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from core.market_data.historical_coverage import TimeRange
from core.market_data.provider_instrument_binding import (
    ProviderBindingResolutionError,
    ProviderInstrumentBinding,
    resolve_provider_bindings,
)


BASE = datetime(2026, 1, 1)


def at(days: int) -> datetime:
    return BASE + timedelta(days=days)


def binding(
    binding_id: str,
    token: str,
    start: datetime | None = None,
    end: datetime | None = None,
    instrument_id: str = "NSE-EQ-RELIANCE",
    provider: str = "angelone",
) -> ProviderInstrumentBinding:
    return ProviderInstrumentBinding(
        binding_id=binding_id,
        instrument_id=instrument_id,
        provider=provider,
        provider_instrument_id=token,
        provider_exchange="NSE",
        provider_segment="EQ",
        provider_symbol="RELIANCE-EQ",
        effective_from=start,
        effective_to=end,
    )


def test_binding_keeps_provider_identity_separate_from_instrument_identity():
    value = binding("binding-1", "2885")

    assert value.instrument_id == "NSE-EQ-RELIANCE"
    assert value.provider == "angelone"
    assert value.provider_instrument_id == "2885"


def test_binding_is_immutable():
    value = binding("binding-1", "2885")

    with pytest.raises(FrozenInstanceError):
        value.provider_instrument_id = "9999"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("binding_id", ""),
        ("instrument_id", ""),
        ("provider", ""),
        ("provider_instrument_id", ""),
        ("provider_exchange", ""),
        ("provider_segment", ""),
        ("provider_symbol", ""),
    ],
)
def test_binding_rejects_empty_identity_fields(field, value):
    values = {
        "binding_id": "binding-1",
        "instrument_id": "NSE-EQ-RELIANCE",
        "provider": "angelone",
        "provider_instrument_id": "2885",
        "provider_exchange": "NSE",
        "provider_segment": "EQ",
        "provider_symbol": "RELIANCE-EQ",
    }
    values[field] = value

    with pytest.raises(ValueError):
        ProviderInstrumentBinding(**values)


def test_binding_accepts_open_ended_effective_period():
    value = binding(
        "binding-1",
        "2885",
        start=None,
        end=None,
    )

    assert value.effective_from is None
    assert value.effective_to is None


def test_binding_rejects_reversed_effective_period():
    with pytest.raises(ValueError, match="effective_from.*before"):
        binding(
            "binding-1",
            "2885",
            start=at(10),
            end=at(5),
        )


def test_binding_rejects_mixed_effective_timezone_awareness():
    with pytest.raises(ValueError, match="timezone"):
        binding(
            "binding-1",
            "2885",
            start=datetime(2026, 1, 1),
            end=datetime(
                2026,
                2,
                1,
                tzinfo=timezone.utc,
            ),
        )


def test_one_binding_can_cover_entire_request():
    request = TimeRange(at(10), at(20))

    resolved = resolve_provider_bindings(
        "NSE-EQ-RELIANCE",
        "angelone",
        request,
        [binding("binding-1", "2885")],
    )

    assert len(resolved) == 1
    assert resolved[0].binding.binding_id == "binding-1"
    assert resolved[0].applied_range == request


def test_transition_splits_request_into_exact_subranges():
    request = TimeRange(at(0), at(20))

    resolved = resolve_provider_bindings(
        "NSE-EQ-RELIANCE",
        "angelone",
        request,
        [
            binding("new", "2222", start=at(10)),
            binding("old", "1111", end=at(10)),
        ],
    )

    assert [
        (
            item.binding.binding_id,
            item.applied_range,
        )
        for item in resolved
    ] == [
        (
            "old",
            TimeRange(at(0), at(10)),
        ),
        (
            "new",
            TimeRange(at(10), at(20)),
        ),
    ]


def test_resolution_is_independent_of_input_order():
    request = TimeRange(at(0), at(20))
    old = binding("old", "1111", end=at(10))
    new = binding("new", "2222", start=at(10))

    forward = resolve_provider_bindings(
        "NSE-EQ-RELIANCE",
        "angelone",
        request,
        [old, new],
    )
    reverse = resolve_provider_bindings(
        "NSE-EQ-RELIANCE",
        "angelone",
        request,
        [new, old],
    )

    assert forward == reverse


def test_gap_fails_clearly():
    request = TimeRange(at(0), at(20))

    with pytest.raises(
        ProviderBindingResolutionError,
        match="gap",
    ):
        resolve_provider_bindings(
            "NSE-EQ-RELIANCE",
            "angelone",
            request,
            [
                binding("old", "1111", end=at(8)),
                binding("new", "2222", start=at(10)),
            ],
        )


def test_overlap_fails_clearly():
    request = TimeRange(at(0), at(20))

    with pytest.raises(
        ProviderBindingResolutionError,
        match="overlap",
    ):
        resolve_provider_bindings(
            "NSE-EQ-RELIANCE",
            "angelone",
            request,
            [
                binding("old", "1111", end=at(12)),
                binding("new", "2222", start=at(10)),
            ],
        )


def test_unrelated_bindings_do_not_satisfy_request():
    request = TimeRange(at(0), at(20))

    with pytest.raises(
        ProviderBindingResolutionError,
        match="gap",
    ):
        resolve_provider_bindings(
            "NSE-EQ-RELIANCE",
            "angelone",
            request,
            [
                binding(
                    "other-instrument",
                    "9999",
                    instrument_id="NSE-EQ-TCS",
                ),
                binding(
                    "other-provider",
                    "8888",
                    provider="other",
                ),
            ],
        )


def test_resolution_rejects_timezone_awareness_mismatch():
    request = TimeRange(
        datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
        datetime(
            2026,
            1,
            2,
            tzinfo=timezone.utc,
        ),
    )

    with pytest.raises(
        ProviderBindingResolutionError,
        match="timezone",
    ):
        resolve_provider_bindings(
            "NSE-EQ-RELIANCE",
            "angelone",
            request,
            [
                binding(
                    "binding-1",
                    "2885",
                    start=datetime(2025, 1, 1),
                )
            ],
        )


def test_adjacent_bindings_are_valid_half_open_transitions():
    request = TimeRange(at(0), at(20))

    resolved = resolve_provider_bindings(
        "NSE-EQ-RELIANCE",
        "angelone",
        request,
        [
            binding("first", "1111", start=at(-10), end=at(10)),
            binding("second", "2222", start=at(10), end=at(30)),
        ],
    )

    assert [item.binding.binding_id for item in resolved] == [
        "first",
        "second",
    ]
    assert [item.applied_range for item in resolved] == [
        TimeRange(at(0), at(10)),
        TimeRange(at(10), at(20)),
    ]


def test_duplicate_binding_identity_fails_clearly():
    request = TimeRange(at(0), at(20))

    with pytest.raises(
        ProviderBindingResolutionError,
        match="identity.*duplicated",
    ):
        resolve_provider_bindings(
            "NSE-EQ-RELIANCE",
            "angelone",
            request,
            [
                binding(
                    "same-binding-id",
                    "2885",
                    end=at(10),
                ),
                binding(
                    "same-binding-id",
                    "9999",
                    start=at(10),
                ),
            ],
        )

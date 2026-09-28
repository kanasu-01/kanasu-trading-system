from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from core.market_data.historical_coverage import TimeRange
from core.research.models.universe import (
    ResolvedUniverseSnapshot,
    UniverseDefinition,
    UniverseQuality,
    UniverseResolutionError,
    UniverseSnapshot,
    resolve_universe_snapshots,
)


INDIA = timezone(timedelta(hours=5, minutes=30))
BASE = datetime(
    2026,
    1,
    1,
    tzinfo=INDIA,
)


def at(days: int) -> datetime:
    return BASE + timedelta(days=days)


def definition(**changes) -> UniverseDefinition:
    values = {
        "name": "NIFTY 50",
        "selection_spec": "official NIFTY 50 membership",
        "source_reference": "nse:index-membership",
    }
    values.update(changes)
    return UniverseDefinition(**values)


def snapshot(**changes) -> UniverseSnapshot:
    values = {
        "definition": definition(),
        "members": (
            "NSE-EQ-RELIANCE",
            "NSE-EQ-TCS",
        ),
        "quality": UniverseQuality.PIT_VERIFIED,
        "as_of": at(0),
        "provenance_refs": (
            "evidence:nse-membership",
        ),
        "effective_from": at(0),
        "effective_to": at(10),
    }
    values.update(changes)
    return UniverseSnapshot(**values)


def test_v1_quality_classes_are_exact():
    assert [quality.value for quality in UniverseQuality] == [
        "PIT_VERIFIED",
        "PIT_RECONSTRUCTED",
        "RULE_BASED_PIT",
        "CURRENT_SNAPSHOT",
        "CUSTOM_FIXED",
    ]


@pytest.mark.parametrize(
    ("quality", "expected"),
    [
        (UniverseQuality.PIT_VERIFIED, True),
        (UniverseQuality.PIT_RECONSTRUCTED, True),
        (UniverseQuality.RULE_BASED_PIT, True),
        (UniverseQuality.CURRENT_SNAPSHOT, False),
        (UniverseQuality.CUSTOM_FIXED, False),
    ],
)
def test_quality_exposes_point_in_time_semantics(
    quality,
    expected,
):
    assert quality.is_point_in_time is expected


def test_definition_has_deterministic_content_identity():
    first = definition()
    second = definition()

    assert first.definition_id == second.definition_id
    assert first.definition_id.startswith("sha256:")


def test_definition_change_changes_identity():
    first = definition()
    second = definition(
        selection_spec="different declared selection rule",
    )

    assert first.definition_id != second.definition_id


def test_definition_is_immutable():
    value = definition()

    with pytest.raises(FrozenInstanceError):
        value.name = "OTHER"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", ""),
        ("selection_spec", ""),
        ("source_reference", ""),
    ],
)
def test_definition_rejects_empty_metadata(
    field,
    value,
):
    with pytest.raises(ValueError):
        definition(**{field: value})


def test_snapshot_normalizes_member_order():
    value = snapshot(
        members=(
            "NSE-EQ-TCS",
            "NSE-EQ-RELIANCE",
        )
    )

    assert value.members == (
        "NSE-EQ-RELIANCE",
        "NSE-EQ-TCS",
    )


def test_snapshot_identity_ignores_accidental_member_order():
    first = snapshot(
        members=(
            "NSE-EQ-RELIANCE",
            "NSE-EQ-TCS",
        )
    )
    second = snapshot(
        members=(
            "NSE-EQ-TCS",
            "NSE-EQ-RELIANCE",
        )
    )

    assert first.snapshot_id == second.snapshot_id


def test_snapshot_rejects_duplicate_members():
    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        snapshot(
            members=(
                "NSE-EQ-RELIANCE",
                "NSE-EQ-RELIANCE",
            )
        )


def test_snapshot_rejects_invalid_member_identity():
    with pytest.raises(
        ValueError,
        match="instrument_id",
    ):
        snapshot(
            members=(
                "NSE-EQ-RELIANCE",
                "",
            )
        )


def test_snapshot_requires_provenance():
    with pytest.raises(
        ValueError,
        match="must not be empty",
    ):
        snapshot(
            provenance_refs=(),
        )


def test_snapshot_normalizes_provenance_order():
    value = snapshot(
        provenance_refs=(
            "evidence:z",
            "evidence:a",
        )
    )

    assert value.provenance_refs == (
        "evidence:a",
        "evidence:z",
    )


def test_snapshot_rejects_duplicate_provenance():
    with pytest.raises(
        ValueError,
        match="duplicates",
    ):
        snapshot(
            provenance_refs=(
                "evidence:a",
                "evidence:a",
            )
        )


def test_snapshot_identity_changes_with_quality():
    first = snapshot()

    second = snapshot(
        quality=UniverseQuality.CUSTOM_FIXED,
        effective_from=None,
        effective_to=None,
    )

    assert first.snapshot_id != second.snapshot_id


def test_snapshot_identity_changes_with_effective_period():
    first = snapshot(
        effective_to=at(10),
    )
    second = snapshot(
        effective_to=at(11),
    )

    assert first.snapshot_id != second.snapshot_id


def test_snapshot_is_immutable():
    value = snapshot()

    with pytest.raises(FrozenInstanceError):
        value.quality = UniverseQuality.CUSTOM_FIXED


def test_snapshot_requires_timezone_aware_as_of():
    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        snapshot(
            as_of=datetime(2026, 1, 1),
        )


def test_snapshot_rejects_reversed_effective_period():
    with pytest.raises(
        ValueError,
        match="before",
    ):
        snapshot(
            effective_from=at(10),
            effective_to=at(5),
        )


@pytest.mark.parametrize(
    "quality",
    [
        UniverseQuality.PIT_VERIFIED,
        UniverseQuality.PIT_RECONSTRUCTED,
        UniverseQuality.RULE_BASED_PIT,
    ],
)
def test_pit_snapshot_requires_effective_applicability(
    quality,
):
    changes = {
        "quality": quality,
        "effective_from": None,
        "effective_to": None,
    }

    if quality in {
        UniverseQuality.PIT_RECONSTRUCTED,
        UniverseQuality.RULE_BASED_PIT,
    }:
        changes["derivation_version"] = "v1"

    with pytest.raises(
        ValueError,
        match="effective applicability",
    ):
        snapshot(**changes)


@pytest.mark.parametrize(
    "quality",
    [
        UniverseQuality.PIT_RECONSTRUCTED,
        UniverseQuality.RULE_BASED_PIT,
    ],
)
def test_derived_pit_quality_requires_version(
    quality,
):
    with pytest.raises(
        ValueError,
        match="derivation_version",
    ):
        snapshot(
            quality=quality,
        )


def test_derived_pit_quality_keeps_version():
    value = snapshot(
        quality=UniverseQuality.RULE_BASED_PIT,
        derivation_version="rule-v3",
    )

    assert value.derivation_version == "rule-v3"


def test_current_snapshot_keeps_explicit_capture_time():
    captured = at(50)

    value = snapshot(
        quality=UniverseQuality.CURRENT_SNAPSHOT,
        as_of=captured,
        effective_from=None,
        effective_to=None,
    )

    assert value.as_of == captured
    assert value.quality.is_point_in_time is False


def test_custom_fixed_remains_non_pit():
    value = snapshot(
        quality=UniverseQuality.CUSTOM_FIXED,
        effective_from=None,
        effective_to=None,
    )

    assert value.quality is UniverseQuality.CUSTOM_FIXED
    assert value.quality.is_point_in_time is False


def test_resolver_splits_membership_transition():
    old = snapshot(
        members=("NSE-EQ-RELIANCE",),
        effective_from=None,
        effective_to=at(10),
    )
    new = snapshot(
        members=(
            "NSE-EQ-RELIANCE",
            "NSE-EQ-TCS",
        ),
        as_of=at(10),
        effective_from=at(10),
        effective_to=None,
    )

    resolved = resolve_universe_snapshots(
        TimeRange(at(0), at(20)),
        [new, old],
        require_point_in_time=True,
    )

    assert all(
        isinstance(item, ResolvedUniverseSnapshot)
        for item in resolved
    )

    assert [
        item.applied_range
        for item in resolved
    ] == [
        TimeRange(at(0), at(10)),
        TimeRange(at(10), at(20)),
    ]

    assert resolved[0].snapshot.members == (
        "NSE-EQ-RELIANCE",
    )
    assert resolved[1].snapshot.members == (
        "NSE-EQ-RELIANCE",
        "NSE-EQ-TCS",
    )


def test_future_membership_is_not_backfilled():
    future = snapshot(
        effective_from=at(10),
        effective_to=None,
        as_of=at(10),
    )

    with pytest.raises(
        UniverseResolutionError,
        match="gap",
    ):
        resolve_universe_snapshots(
            TimeRange(at(0), at(20)),
            [future],
            require_point_in_time=True,
        )


def test_departed_membership_is_not_silently_retained():
    historical = snapshot(
        effective_from=None,
        effective_to=at(10),
    )

    with pytest.raises(
        UniverseResolutionError,
        match="gap",
    ):
        resolve_universe_snapshots(
            TimeRange(at(0), at(20)),
            [historical],
            require_point_in_time=True,
        )


def test_resolver_rejects_overlap():
    first = snapshot(
        effective_from=None,
        effective_to=at(12),
    )
    second = snapshot(
        as_of=at(10),
        effective_from=at(10),
        effective_to=None,
    )

    with pytest.raises(
        UniverseResolutionError,
        match="overlap",
    ):
        resolve_universe_snapshots(
            TimeRange(at(0), at(20)),
            [first, second],
        )


def test_resolver_is_independent_of_input_order():
    old = snapshot(
        effective_from=None,
        effective_to=at(10),
    )
    new = snapshot(
        members=("NSE-EQ-TCS",),
        as_of=at(10),
        effective_from=at(10),
        effective_to=None,
    )

    request = TimeRange(at(0), at(20))

    forward = resolve_universe_snapshots(
        request,
        [old, new],
    )
    reverse = resolve_universe_snapshots(
        request,
        [new, old],
    )

    assert forward == reverse


def test_point_in_time_mode_rejects_current_snapshot():
    current = snapshot(
        quality=UniverseQuality.CURRENT_SNAPSHOT,
        effective_from=None,
        effective_to=None,
    )

    with pytest.raises(
        UniverseResolutionError,
        match="non-PIT",
    ):
        resolve_universe_snapshots(
            TimeRange(at(0), at(20)),
            [current],
            require_point_in_time=True,
        )


def test_current_snapshot_can_be_used_with_non_pit_semantics():
    current = snapshot(
        quality=UniverseQuality.CURRENT_SNAPSHOT,
        as_of=at(100),
        effective_from=None,
        effective_to=None,
        provenance_refs=(
            "capture:current-members",
        ),
    )

    resolved = resolve_universe_snapshots(
        TimeRange(at(0), at(20)),
        [current],
    )

    assert len(resolved) == 1
    assert (
        resolved[0].snapshot.quality
        is UniverseQuality.CURRENT_SNAPSHOT
    )
    assert (
        resolved[0].applied_range
        == TimeRange(at(0), at(20))
    )


def test_mixed_historical_quality_remains_visible():
    verified = snapshot(
        quality=UniverseQuality.PIT_VERIFIED,
        effective_from=None,
        effective_to=at(10),
    )
    reconstructed = snapshot(
        quality=UniverseQuality.PIT_RECONSTRUCTED,
        as_of=at(10),
        effective_from=at(10),
        effective_to=None,
        derivation_version="evidence-v2",
        provenance_refs=(
            "evidence:reconstructed-v2",
        ),
    )

    resolved = resolve_universe_snapshots(
        TimeRange(at(0), at(20)),
        [verified, reconstructed],
        require_point_in_time=True,
    )

    assert [
        item.snapshot.quality
        for item in resolved
    ] == [
        UniverseQuality.PIT_VERIFIED,
        UniverseQuality.PIT_RECONSTRUCTED,
    ]


def test_duplicate_snapshot_identity_fails_clearly():
    value = snapshot()

    with pytest.raises(
        UniverseResolutionError,
        match="identity.*duplicated",
    ):
        resolve_universe_snapshots(
            TimeRange(at(0), at(10)),
            [value, value],
        )


def test_resolver_rejects_mixed_universe_definitions():
    first = snapshot(
        effective_from=None,
        effective_to=at(10),
    )
    second = snapshot(
        definition=definition(
            name="NIFTY 500",
            selection_spec="official NIFTY 500 membership",
        ),
        as_of=at(10),
        effective_from=at(10),
        effective_to=None,
    )

    with pytest.raises(
        UniverseResolutionError,
        match="mix definitions",
    ):
        resolve_universe_snapshots(
            TimeRange(at(0), at(20)),
            [first, second],
            require_point_in_time=True,
        )

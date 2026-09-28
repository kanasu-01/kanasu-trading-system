"""Immutable universe identity and temporal-resolution contracts."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import hashlib
import json

from core.market_data.historical_coverage import TimeRange


UNIVERSE_DEFINITION_SCHEMA_ID = "kanasu.universe-definition.v1"
UNIVERSE_SNAPSHOT_SCHEMA_ID = "kanasu.universe-snapshot.v1"


class UniverseQuality(str, Enum):
    PIT_VERIFIED = "PIT_VERIFIED"
    PIT_RECONSTRUCTED = "PIT_RECONSTRUCTED"
    RULE_BASED_PIT = "RULE_BASED_PIT"
    CURRENT_SNAPSHOT = "CURRENT_SNAPSHOT"
    CUSTOM_FIXED = "CUSTOM_FIXED"

    @property
    def is_point_in_time(self) -> bool:
        return self in {
            UniverseQuality.PIT_VERIFIED,
            UniverseQuality.PIT_RECONSTRUCTED,
            UniverseQuality.RULE_BASED_PIT,
        }


def _require_nonempty_string(
    value: str,
    field_name: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"{field_name} must be a non-empty string"
        )


def _require_aware_datetime(
    value: datetime,
    field_name: str,
) -> None:
    if not isinstance(value, datetime):
        raise TypeError(
            f"{field_name} must be a datetime"
        )

    if value.utcoffset() is None:
        raise ValueError(
            f"{field_name} must be timezone-aware"
        )


def _optional_aware_datetime(
    value: datetime | None,
    field_name: str,
) -> None:
    if value is not None:
        _require_aware_datetime(value, field_name)


def _content_id(
    payload: dict,
    *,
    schema: str,
) -> str:
    envelope = {
        "schema": schema,
        "payload": payload,
    }

    encoded = json.dumps(
        envelope,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    return "sha256:" + hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class UniverseDefinition:
    """Immutable description of universe-selection intent."""

    name: str
    selection_spec: str
    source_reference: str | None = None
    definition_id: str = field(init=False)

    def __post_init__(self) -> None:
        _require_nonempty_string(self.name, "name")
        _require_nonempty_string(
            self.selection_spec,
            "selection_spec",
        )

        if self.source_reference is not None:
            _require_nonempty_string(
                self.source_reference,
                "source_reference",
            )

        definition_id = _content_id(
            {
                "name": self.name,
                "selection_spec": self.selection_spec,
                "source_reference": self.source_reference,
            },
            schema=UNIVERSE_DEFINITION_SCHEMA_ID,
        )

        object.__setattr__(
            self,
            "definition_id",
            definition_id,
        )


@dataclass(frozen=True)
class UniverseSnapshot:
    """
    Immutable resolved universe membership state.

    Membership and provenance references are normalized so accidental
    input ordering cannot change canonical snapshot identity.
    """

    definition: UniverseDefinition
    members: tuple[str, ...] | list[str]
    quality: UniverseQuality
    as_of: datetime
    provenance_refs: tuple[str, ...] | list[str]
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    derivation_version: str | None = None
    snapshot_id: str = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(
            self.definition,
            UniverseDefinition,
        ):
            raise TypeError(
                "definition must be a UniverseDefinition"
            )

        if not isinstance(self.quality, UniverseQuality):
            raise TypeError(
                "quality must be a UniverseQuality"
            )

        _require_aware_datetime(
            self.as_of,
            "as_of",
        )
        _optional_aware_datetime(
            self.effective_from,
            "effective_from",
        )
        _optional_aware_datetime(
            self.effective_to,
            "effective_to",
        )

        if (
            self.effective_from is not None
            and self.effective_to is not None
            and self.effective_from >= self.effective_to
        ):
            raise ValueError(
                "effective_from must be before effective_to"
            )

        if self.quality.is_point_in_time and (
            self.effective_from is None
            and self.effective_to is None
        ):
            raise ValueError(
                "point-in-time universe quality requires "
                "explicit effective applicability"
            )

        if not isinstance(self.members, (list, tuple)):
            raise TypeError(
                "members must be an ordered list or tuple"
            )

        raw_members = tuple(self.members)

        for member in raw_members:
            _require_nonempty_string(
                member,
                "member instrument_id",
            )

        if len(set(raw_members)) != len(raw_members):
            raise ValueError(
                "universe membership contains duplicates"
            )

        normalized_members = tuple(
            sorted(raw_members)
        )

        if not isinstance(
            self.provenance_refs,
            (list, tuple),
        ):
            raise TypeError(
                "provenance_refs must be an ordered list or tuple"
            )

        raw_provenance = tuple(self.provenance_refs)

        if not raw_provenance:
            raise ValueError(
                "provenance_refs must not be empty"
            )

        for reference in raw_provenance:
            _require_nonempty_string(
                reference,
                "provenance reference",
            )

        if (
            len(set(raw_provenance))
            != len(raw_provenance)
        ):
            raise ValueError(
                "provenance_refs contains duplicates"
            )

        normalized_provenance = tuple(
            sorted(raw_provenance)
        )

        if self.derivation_version is not None:
            _require_nonempty_string(
                self.derivation_version,
                "derivation_version",
            )

        if self.quality in {
            UniverseQuality.PIT_RECONSTRUCTED,
            UniverseQuality.RULE_BASED_PIT,
        } and self.derivation_version is None:
            raise ValueError(
                f"{self.quality.value} requires derivation_version"
            )

        object.__setattr__(
            self,
            "members",
            normalized_members,
        )
        object.__setattr__(
            self,
            "provenance_refs",
            normalized_provenance,
        )

        snapshot_id = _content_id(
            {
                "definition_id": (
                    self.definition.definition_id
                ),
                "members": list(normalized_members),
                "quality": self.quality.value,
                "as_of": self.as_of.isoformat(
                    timespec="microseconds"
                ),
                "effective_from": (
                    None
                    if self.effective_from is None
                    else self.effective_from.isoformat(
                        timespec="microseconds"
                    )
                ),
                "effective_to": (
                    None
                    if self.effective_to is None
                    else self.effective_to.isoformat(
                        timespec="microseconds"
                    )
                ),
                "derivation_version": (
                    self.derivation_version
                ),
                "provenance_refs": list(
                    normalized_provenance
                ),
            },
            schema=UNIVERSE_SNAPSHOT_SCHEMA_ID,
        )

        object.__setattr__(
            self,
            "snapshot_id",
            snapshot_id,
        )


@dataclass(frozen=True)
class ResolvedUniverseSnapshot:
    snapshot: UniverseSnapshot
    applied_range: TimeRange


class UniverseResolutionError(ValueError):
    pass


def _validate_request_awareness(
    request: TimeRange,
    snapshot: UniverseSnapshot,
) -> None:
    request_aware = (
        request.start.utcoffset() is not None
    )

    for boundary in (
        snapshot.effective_from,
        snapshot.effective_to,
    ):
        if boundary is None:
            continue

        if (
            boundary.utcoffset() is not None
        ) != request_aware:
            raise UniverseResolutionError(
                "universe snapshot and request timezone "
                "awareness must match"
            )


def _intersection(
    request: TimeRange,
    snapshot: UniverseSnapshot,
) -> TimeRange | None:
    start = request.start

    if (
        snapshot.effective_from is not None
        and snapshot.effective_from > start
    ):
        start = snapshot.effective_from

    end = request.end

    if (
        snapshot.effective_to is not None
        and snapshot.effective_to < end
    ):
        end = snapshot.effective_to

    if start >= end:
        return None

    return TimeRange(
        start=start,
        end=end,
    )


def resolve_universe_snapshots(
    request: TimeRange,
    snapshots: Iterable[UniverseSnapshot],
    *,
    require_point_in_time: bool = False,
) -> tuple[ResolvedUniverseSnapshot, ...]:
    """
    Resolve exact membership states used across one research period.

    Applicable snapshot intervals must cover the request without gaps
    or overlaps. Point-in-time mode rejects non-PIT quality classes.
    """

    if not isinstance(request, TimeRange):
        raise TypeError(
            "request must be a TimeRange"
        )

    if not isinstance(
        require_point_in_time,
        bool,
    ):
        raise TypeError(
            "require_point_in_time must be a bool"
        )

    applicable: list[
        tuple[TimeRange, UniverseSnapshot]
    ] = []

    seen_snapshot_ids: set[str] = set()
    expected_definition_id: str | None = None

    for snapshot in snapshots:
        if not isinstance(
            snapshot,
            UniverseSnapshot,
        ):
            raise TypeError(
                "snapshots must contain UniverseSnapshot values"
            )

        if expected_definition_id is None:
            expected_definition_id = (
                snapshot.definition.definition_id
            )
        elif (
            snapshot.definition.definition_id
            != expected_definition_id
        ):
            raise UniverseResolutionError(
                "universe resolution cannot mix definitions"
            )

        if snapshot.snapshot_id in seen_snapshot_ids:
            raise UniverseResolutionError(
                "universe snapshot identity is duplicated"
            )

        seen_snapshot_ids.add(
            snapshot.snapshot_id
        )

        if (
            require_point_in_time
            and not snapshot.quality.is_point_in_time
        ):
            raise UniverseResolutionError(
                "point-in-time universe resolution cannot "
                "use non-PIT snapshot quality"
            )

        _validate_request_awareness(
            request,
            snapshot,
        )

        applied_range = _intersection(
            request,
            snapshot,
        )

        if applied_range is not None:
            applicable.append(
                (
                    applied_range,
                    snapshot,
                )
            )

    applicable.sort(
        key=lambda item: (
            item[0].start,
            item[0].end,
            item[1].snapshot_id,
        )
    )

    resolved: list[
        ResolvedUniverseSnapshot
    ] = []

    cursor = request.start

    for applied_range, snapshot in applicable:
        if applied_range.start > cursor:
            raise UniverseResolutionError(
                "universe snapshot coverage has a gap"
            )

        if applied_range.start < cursor:
            raise UniverseResolutionError(
                "universe snapshot coverage has "
                "a conflicting overlap"
            )

        resolved.append(
            ResolvedUniverseSnapshot(
                snapshot=snapshot,
                applied_range=applied_range,
            )
        )

        cursor = applied_range.end

    if cursor < request.end:
        raise UniverseResolutionError(
            "universe snapshot coverage has a gap"
        )

    if not resolved:
        raise UniverseResolutionError(
            "universe snapshot coverage has a gap"
        )

    return tuple(resolved)

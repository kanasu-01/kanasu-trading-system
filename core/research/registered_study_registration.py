"""M9.4b canonical StudyRevision registration and Trial expansion.

BEHAVIOR IMPACT: ADDED
BEHAVIOR IDS: RESEARCH-RULE-014, RESEARCH-RULE-017,
RESEARCH-RULE-018

This module registers research plans and immutable Trial denominators.
It does not start jobs, execute Backtests, reuse evidence, retry work,
cancel work, recover work, qualify research or place broker orders.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime
import hashlib
import math
from typing import Any

from core.market_data.historical_coverage import TimeRange
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    STUDY_REVISION_SCHEMA_ID,
    TRIAL_IDENTITY_SCHEMA_ID,
    TRIAL_MEMBERSHIP_EVIDENCE_SCHEMA_ID,
    StudyRevision,
    Trial,
    TrialDisposition,
    TrialDispositionEvent,
)
from core.research.models.research_catalog import (
    ResearchArtifactKind,
)
from core.research.models.universe import (
    ResolvedUniverseSnapshot,
    UniverseDefinition,
    UniverseSnapshot,
    resolve_universe_snapshots,
)
from core.research.reproducibility import (
    canonical_bytes,
    canonical_fingerprint,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)


PARAMETER_VARIANT_SCHEMA_ID = (
    "kanasu.study-parameter-variant.v1"
)
TRIAL_DISPOSITION_EVENT_SCHEMA_ID = (
    "kanasu.trial-disposition-event.v1"
)

DEFAULT_RESEARCH_MAX_TRIALS_PER_REVISION = 5_000


@dataclass(frozen=True)
class RegisteredStudyPopulation:
    revision: StudyRevision
    trials: tuple[Trial, ...]


@dataclass(frozen=True)
class _Episode:
    instrument_id: str
    start: datetime
    end: datetime
    evidence_payload: dict[str, Any]
    evidence_bytes: bytes
    evidence_fingerprint: str


def _require_nonempty(
    value: str,
    field_name: str,
) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(
            f"{field_name} must be a non-empty string"
        )


def _range_payload(
    value: TimeRange,
) -> dict[str, datetime]:
    return {
        "start": value.start,
        "end": value.end,
    }


def _definition_payload(
    definition: UniverseDefinition,
) -> dict[str, Any]:
    return {
        "definition_id": definition.definition_id,
        "name": definition.name,
        "selection_spec": definition.selection_spec,
        "source_reference": definition.source_reference,
    }


def _resolved_snapshot_payload(
    resolved: ResolvedUniverseSnapshot,
) -> dict[str, Any]:
    snapshot = resolved.snapshot

    return {
        "snapshot_id": snapshot.snapshot_id,
        "universe_definition_id": (
            snapshot.definition.definition_id
        ),
        "members": list(snapshot.members),
        "quality": snapshot.quality.value,
        "as_of": snapshot.as_of,
        "effective_from": snapshot.effective_from,
        "effective_to": snapshot.effective_to,
        "derivation_version": snapshot.derivation_version,
        "provenance_refs": list(
            snapshot.provenance_refs
        ),
        "applied_range": _range_payload(
            resolved.applied_range
        ),
    }


def _membership_segment_payload(
    resolved: ResolvedUniverseSnapshot,
) -> dict[str, Any]:
    snapshot = resolved.snapshot

    return {
        "snapshot_id": snapshot.snapshot_id,
        "universe_definition_id": (
            snapshot.definition.definition_id
        ),
        "quality": snapshot.quality.value,
        "as_of": snapshot.as_of,
        "effective_from": snapshot.effective_from,
        "effective_to": snapshot.effective_to,
        "derivation_version": snapshot.derivation_version,
        "provenance_refs": list(
            snapshot.provenance_refs
        ),
        "applied_range": _range_payload(
            resolved.applied_range
        ),
    }


def _normalize_parameter_variants(
    values: Iterable[Mapping[str, Any]],
) -> tuple[tuple[str, dict[str, Any]], ...]:
    variants = []

    for value in values:
        if not isinstance(value, Mapping):
            raise TypeError(
                "parameter_variants must contain mappings"
            )

        payload = dict(value)

        fingerprint = canonical_fingerprint(
            payload,
            schema=PARAMETER_VARIANT_SCHEMA_ID,
        )

        variants.append(
            (
                fingerprint,
                payload,
            )
        )

    if not variants:
        raise ValueError(
            "parameter_variants must contain at least one "
            "finite configuration"
        )

    variants.sort(
        key=lambda item: item[0]
    )

    fingerprints = [
        fingerprint
        for fingerprint, _ in variants
    ]

    if (
        len(set(fingerprints))
        != len(fingerprints)
    ):
        raise ValueError(
            "parameter_variants contain duplicate canonical "
            "configurations"
        )

    return tuple(variants)


def _build_membership_episodes(
    *,
    study_revision_id: str,
    resolved: tuple[ResolvedUniverseSnapshot, ...],
) -> tuple[_Episode, ...]:
    active: dict[
        str,
        list[dict[str, Any]],
    ] = {}

    episodes: list[_Episode] = []

    def finish(
        instrument_id: str,
    ) -> None:
        segments = active.pop(
            instrument_id
        )

        start = segments[0][
            "applied_range"
        ]["start"]

        end = segments[-1][
            "applied_range"
        ]["end"]

        evidence_payload = {
            "study_revision_id": study_revision_id,
            "instrument_id": instrument_id,
            "membership_episode": {
                "start": start,
                "end": end,
            },
            "ordered_snapshot_subranges": segments,
        }

        evidence_bytes = canonical_bytes(
            evidence_payload,
            schema=(
                TRIAL_MEMBERSHIP_EVIDENCE_SCHEMA_ID
            ),
        )

        evidence_fingerprint = (
            "sha256:"
            + hashlib.sha256(
                evidence_bytes
            ).hexdigest()
        )

        episodes.append(
            _Episode(
                instrument_id=instrument_id,
                start=start,
                end=end,
                evidence_payload=evidence_payload,
                evidence_bytes=evidence_bytes,
                evidence_fingerprint=(
                    evidence_fingerprint
                ),
            )
        )

    for item in resolved:
        applied_start = (
            item.applied_range.start
        )

        current_members = set(
            item.snapshot.members
        )

        for instrument_id in tuple(
            sorted(active)
        ):
            segments = active[
                instrument_id
            ]

            previous_end = segments[-1][
                "applied_range"
            ]["end"]

            if (
                instrument_id
                not in current_members
                or previous_end
                != applied_start
            ):
                finish(
                    instrument_id
                )

        segment = _membership_segment_payload(
            item
        )

        for instrument_id in item.snapshot.members:
            active.setdefault(
                instrument_id,
                [],
            ).append(
                dict(segment)
            )

    for instrument_id in tuple(
        sorted(active)
    ):
        finish(
            instrument_id
        )

    episodes.sort(
        key=lambda episode: (
            episode.start,
            episode.end,
            episode.instrument_id,
            episode.evidence_fingerprint,
        )
    )

    return tuple(episodes)


class RegisteredStudyRegistrationService:
    """Freeze and atomically register one complete research population."""

    def __init__(
        self,
        *,
        catalog_store: SQLiteResearchCatalogStore,
        artifact_store: ContentAddressedResearchArtifactStore,
        max_trials_per_revision: int = (
            DEFAULT_RESEARCH_MAX_TRIALS_PER_REVISION
        ),
    ) -> None:
        if not isinstance(
            catalog_store,
            SQLiteResearchCatalogStore,
        ):
            raise TypeError(
                "catalog_store must be a "
                "SQLiteResearchCatalogStore"
            )

        if not isinstance(
            artifact_store,
            ContentAddressedResearchArtifactStore,
        ):
            raise TypeError(
                "artifact_store must be a "
                "ContentAddressedResearchArtifactStore"
            )

        if (
            type(max_trials_per_revision) is not int
            or max_trials_per_revision <= 0
        ):
            raise ValueError(
                "max_trials_per_revision must be a "
                "positive integer"
            )

        self.catalog_store = catalog_store
        self.artifact_store = artifact_store
        self.max_trials_per_revision = (
            max_trials_per_revision
        )

    def register_study_revision(
        self,
        *,
        study_id: str,
        research_intent: str,
        strategy_procedure_id: str,
        timeframe: str,
        research_range: TimeRange,
        timezone: str,
        initial_capital: float,
        risk_economic_configuration: Mapping[str, Any],
        parameter_variants: Iterable[Mapping[str, Any]],
        universe_definition: UniverseDefinition,
        universe_snapshots: Iterable[UniverseSnapshot],
        require_point_in_time: bool,
        data_treatment_basis: Mapping[str, Any],
        repository_revision: str,
        evidence_reuse_policy: EvidenceReusePolicy,
        registered_at: datetime,
    ) -> RegisteredStudyPopulation:
        """
        Register the complete finite Trial denominator before execution.

        Filesystem artifact publication is content-addressed and may
        precede the SQLite transaction. The StudyRevision/Trial catalog
        becomes authoritative only through the one atomic population
        commit.
        """

        for field_name, value in (
            ("study_id", study_id),
            ("research_intent", research_intent),
            (
                "strategy_procedure_id",
                strategy_procedure_id,
            ),
            ("timeframe", timeframe),
            ("timezone", timezone),
            (
                "repository_revision",
                repository_revision,
            ),
        ):
            _require_nonempty(
                value,
                field_name,
            )

        if not isinstance(
            research_range,
            TimeRange,
        ):
            raise TypeError(
                "research_range must be a TimeRange"
            )

        if (
            not isinstance(initial_capital, (int, float))
            or isinstance(initial_capital, bool)
            or not math.isfinite(
                float(initial_capital)
            )
            or initial_capital <= 0
        ):
            raise ValueError(
                "initial_capital must be finite and positive"
            )

        if not isinstance(
            risk_economic_configuration,
            Mapping,
        ):
            raise TypeError(
                "risk_economic_configuration must be a mapping"
            )

        if not isinstance(
            data_treatment_basis,
            Mapping,
        ):
            raise TypeError(
                "data_treatment_basis must be a mapping"
            )

        if not isinstance(
            universe_definition,
            UniverseDefinition,
        ):
            raise TypeError(
                "universe_definition must be a "
                "UniverseDefinition"
            )

        if type(require_point_in_time) is not bool:
            raise TypeError(
                "require_point_in_time must be a bool"
            )

        if not isinstance(
            evidence_reuse_policy,
            EvidenceReusePolicy,
        ):
            raise TypeError(
                "evidence_reuse_policy must be an "
                "EvidenceReusePolicy"
            )

        if (
            not isinstance(registered_at, datetime)
            or registered_at.utcoffset() is None
        ):
            raise ValueError(
                "registered_at must be a timezone-aware datetime"
            )

        snapshots = tuple(
            universe_snapshots
        )

        for snapshot in snapshots:
            if not isinstance(
                snapshot,
                UniverseSnapshot,
            ):
                raise TypeError(
                    "universe_snapshots must contain "
                    "UniverseSnapshot values"
                )

            if (
                snapshot.definition.definition_id
                != universe_definition.definition_id
            ):
                raise ValueError(
                    "universe snapshot does not belong to "
                    "the registered universe definition"
                )

        resolved = resolve_universe_snapshots(
            research_range,
            snapshots,
            require_point_in_time=(
                require_point_in_time
            ),
        )

        variants = (
            _normalize_parameter_variants(
                parameter_variants
            )
        )

        resolved_payload = [
            _resolved_snapshot_payload(item)
            for item in resolved
        ]

        plan_payload = {
            "study_id": study_id,
            "research_intent": research_intent,
            "strategy_procedure_id": (
                strategy_procedure_id
            ),
            "timeframe": timeframe,
            "research_range": _range_payload(
                research_range
            ),
            "timezone": timezone,
            "initial_capital": float(
                initial_capital
            ),
            "risk_economic_configuration": dict(
                risk_economic_configuration
            ),
            "parameter_variants": [
                {
                    "fingerprint": fingerprint,
                    "configuration": payload,
                }
                for fingerprint, payload
                in variants
            ],
            "universe_definition": (
                _definition_payload(
                    universe_definition
                )
            ),
            "resolved_universe_snapshots": (
                resolved_payload
            ),
            "require_point_in_time": (
                require_point_in_time
            ),
            "data_treatment_basis": dict(
                data_treatment_basis
            ),
            "repository_revision": (
                repository_revision
            ),
            "evidence_reuse_policy": (
                evidence_reuse_policy.value
            ),
        }

        plan_bytes = canonical_bytes(
            plan_payload,
            schema=STUDY_REVISION_SCHEMA_ID,
        )

        study_revision_id = (
            "sha256:"
            + hashlib.sha256(
                plan_bytes
            ).hexdigest()
        )

        episodes = _build_membership_episodes(
            study_revision_id=(
                study_revision_id
            ),
            resolved=resolved,
        )

        trial_count = (
            len(episodes)
            * len(variants)
        )

        if (
            trial_count
            > self.max_trials_per_revision
        ):
            raise ValueError(
                "registered Trial population "
                f"{trial_count} exceeds backend limit "
                f"{self.max_trials_per_revision}; "
                "registration rejected before persistence"
            )

        plan_artifact = (
            self.artifact_store.persist_bytes(
                plan_bytes,
                artifact_kind=(
                    ResearchArtifactKind.STUDY_REVISION_PLAN
                ),
                schema_id=(
                    STUDY_REVISION_SCHEMA_ID
                ),
                created_at=registered_at,
            )
        )

        if (
            plan_artifact.artifact_id
            != study_revision_id
        ):
            raise RuntimeError(
                "StudyRevision plan artifact identity "
                "does not match canonical plan identity"
            )

        self.catalog_store.save_artifact(
            plan_artifact
        )

        membership_artifacts = {}

        for episode in episodes:
            artifact = (
                self.artifact_store.persist_bytes(
                    episode.evidence_bytes,
                    artifact_kind=(
                        ResearchArtifactKind
                        .TRIAL_MEMBERSHIP_EVIDENCE
                    ),
                    schema_id=(
                        TRIAL_MEMBERSHIP_EVIDENCE_SCHEMA_ID
                    ),
                    created_at=registered_at,
                )
            )

            if (
                artifact.artifact_id
                != episode.evidence_fingerprint
            ):
                raise RuntimeError(
                    "membership evidence artifact identity "
                    "does not match canonical evidence"
                )

            self.catalog_store.save_artifact(
                artifact
            )

            membership_artifacts[
                episode.evidence_fingerprint
            ] = artifact

        trials = []
        events = []

        for episode in episodes:
            for (
                parameter_fingerprint,
                _,
            ) in variants:
                trial_id = canonical_fingerprint(
                    {
                        "study_revision_id": (
                            study_revision_id
                        ),
                        "instrument_id": (
                            episode.instrument_id
                        ),
                        "membership_episode": {
                            "start": episode.start,
                            "end": episode.end,
                        },
                        "membership_evidence_fingerprint": (
                            episode.evidence_fingerprint
                        ),
                        "parameter_configuration_fingerprint": (
                            parameter_fingerprint
                        ),
                    },
                    schema=TRIAL_IDENTITY_SCHEMA_ID,
                )

                trial = Trial(
                    trial_id=trial_id,
                    study_revision_id=(
                        study_revision_id
                    ),
                    instrument_id=(
                        episode.instrument_id
                    ),
                    membership_episode_start=(
                        episode.start
                    ),
                    membership_episode_end=(
                        episode.end
                    ),
                    membership_evidence_fingerprint=(
                        episode.evidence_fingerprint
                    ),
                    membership_evidence_artifact_id=(
                        membership_artifacts[
                            episode.evidence_fingerprint
                        ].artifact_id
                    ),
                    parameter_configuration_fingerprint=(
                        parameter_fingerprint
                    ),
                    registered_at=registered_at,
                    disposition=(
                        TrialDisposition.PENDING
                    ),
                    disposition_at=registered_at,
                )

                event_id = canonical_fingerprint(
                    {
                        "trial_id": trial_id,
                        "sequence_number": 1,
                        "new_disposition": (
                            TrialDisposition.PENDING.value
                        ),
                    },
                    schema=(
                        TRIAL_DISPOSITION_EVENT_SCHEMA_ID
                    ),
                )

                event = TrialDispositionEvent(
                    event_id=event_id,
                    trial_id=trial_id,
                    sequence_number=1,
                    previous_disposition=None,
                    new_disposition=(
                        TrialDisposition.PENDING
                    ),
                    occurred_at=registered_at,
                )

                trials.append(
                    trial
                )
                events.append(
                    event
                )

        trials_tuple = tuple(
            sorted(
                trials,
                key=lambda trial: (
                    trial.membership_episode_start,
                    trial.membership_episode_end,
                    trial.instrument_id,
                    trial.membership_evidence_fingerprint,
                    trial.parameter_configuration_fingerprint,
                    trial.trial_id,
                ),
            )
        )

        event_by_trial = {
            event.trial_id: event
            for event in events
        }

        events_tuple = tuple(
            event_by_trial[
                trial.trial_id
            ]
            for trial in trials_tuple
        )

        revision, persisted_trials = (
            self.catalog_store
            .save_registered_revision_population(
                study_id=study_id,
                study_revision_id=(
                    study_revision_id
                ),
                plan_artifact_id=(
                    plan_artifact.artifact_id
                ),
                repository_revision=(
                    repository_revision
                ),
                evidence_reuse_policy=(
                    evidence_reuse_policy
                ),
                registered_at=registered_at,
                trials=trials_tuple,
                initial_events=events_tuple,
            )
        )

        return RegisteredStudyPopulation(
            revision=revision,
            trials=persisted_trials,
        )

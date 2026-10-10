"""Resolve one registered Trial into its frozen execution plan.

BEHAVIOR IMPACT: ADDED
PRIMARY BEHAVIOR IDS: RESEARCH-RULE-014, RESEARCH-RULE-017
PRESERVED BEHAVIOR IDS: RESEARCH-RULE-010, RESEARCH-RULE-011

This module resolves only immutable registered research intent.
It does not invent strategy mappings, provider mappings, execute
financial logic, create RunAttempts, reuse evidence or terminalize jobs.
"""

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping

from core.market_data.historical_coverage import TimeRange
from core.research.models.registered_study import (
    EvidenceReusePolicy,
    STUDY_REVISION_SCHEMA_ID,
)
from core.research.models.research_catalog import (
    ResearchArtifactKind,
)
from core.research.registered_study_registration import (
    PARAMETER_VARIANT_SCHEMA_ID,
    resolve_registered_data_treatment_basis,
)
from core.research.reproducibility import (
    canonical_fingerprint,
    decode_canonical_bytes,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)


@dataclass(frozen=True)
class RegisteredTrialExecutionPlan:
    trial_id: str
    study_revision_id: str
    instrument_id: str
    strategy_procedure_id: str
    timeframe: str
    research_range: TimeRange
    trial_range: TimeRange
    timezone: str
    initial_capital: float
    risk_economic_configuration: Mapping[str, Any]
    parameter_configuration: Mapping[str, Any]
    data_treatment_basis: Mapping[str, Any]
    repository_revision: str
    evidence_reuse_policy: EvidenceReusePolicy

    def __post_init__(self) -> None:
        for field_name, value in (
            ("trial_id", self.trial_id),
            ("study_revision_id", self.study_revision_id),
            ("instrument_id", self.instrument_id),
            (
                "strategy_procedure_id",
                self.strategy_procedure_id,
            ),
            ("timeframe", self.timeframe),
            ("timezone", self.timezone),
            (
                "repository_revision",
                self.repository_revision,
            ),
        ):
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"{field_name} must be a non-empty string"
                )

        if not isinstance(
            self.research_range,
            TimeRange,
        ):
            raise TypeError(
                "research_range must be a TimeRange"
            )

        if not isinstance(
            self.trial_range,
            TimeRange,
        ):
            raise TypeError(
                "trial_range must be a TimeRange"
            )

        if (
            self.trial_range.start
            < self.research_range.start
            or self.trial_range.end
            > self.research_range.end
        ):
            raise ValueError(
                "trial_range must be contained within "
                "the registered research_range"
            )

        if (
            not isinstance(
                self.initial_capital,
                (int, float),
            )
            or isinstance(self.initial_capital, bool)
            or not math.isfinite(
                float(self.initial_capital)
            )
            or self.initial_capital <= 0
        ):
            raise ValueError(
                "initial_capital must be finite and positive"
            )

        for field_name in (
            "risk_economic_configuration",
            "parameter_configuration",
            "data_treatment_basis",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, Mapping):
                raise TypeError(
                    f"{field_name} must be a mapping"
                )
            object.__setattr__(
                self,
                field_name,
                MappingProxyType(dict(value)),
            )

        resolve_registered_data_treatment_basis(
            self.data_treatment_basis
        )

        if not isinstance(
            self.evidence_reuse_policy,
            EvidenceReusePolicy,
        ):
            raise TypeError(
                "evidence_reuse_policy must be "
                "an EvidenceReusePolicy"
            )


class RegisteredTrialExecutionPlanResolver:
    """Fail-closed resolver for one immutable registered Trial plan."""

    def __init__(
        self,
        *,
        catalog_store: SQLiteResearchCatalogStore,
        artifact_store: ContentAddressedResearchArtifactStore,
    ):
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

        self.catalog_store = catalog_store
        self.artifact_store = artifact_store

    @staticmethod
    def _require_mapping(
        plan: Mapping[str, Any],
        field_name: str,
    ) -> dict[str, Any]:
        value = plan.get(field_name)

        if not isinstance(value, dict):
            raise ValueError(
                f"registered plan {field_name} must be a mapping"
            )

        return value

    @staticmethod
    def _require_string(
        plan: Mapping[str, Any],
        field_name: str,
    ) -> str:
        value = plan.get(field_name)

        if not isinstance(value, str) or not value:
            raise ValueError(
                f"registered plan {field_name} "
                "must be a non-empty string"
            )

        return value

    def resolve(
        self,
        trial_id: str,
    ) -> RegisteredTrialExecutionPlan:
        trial = self.catalog_store.load_trial(
            trial_id
        )

        if trial is None:
            raise ValueError(
                f"Trial does not exist: {trial_id}"
            )

        revision = (
            self.catalog_store.load_study_revision(
                trial.study_revision_id
            )
        )

        if revision is None:
            raise ValueError(
                "Trial StudyRevision does not exist"
            )

        if (
            revision.study_revision_id
            != revision.plan_artifact_id
        ):
            raise ValueError(
                "StudyRevision identity must match "
                "its plan artifact identity"
            )

        artifact = self.catalog_store.load_artifact(
            revision.plan_artifact_id
        )

        if artifact is None:
            raise ValueError(
                "StudyRevision plan artifact metadata "
                "does not exist"
            )

        if (
            artifact.artifact_kind
            is not ResearchArtifactKind.STUDY_REVISION_PLAN
            or artifact.schema_id
            != STUDY_REVISION_SCHEMA_ID
        ):
            raise ValueError(
                "StudyRevision plan artifact metadata "
                "has the wrong kind or schema"
            )

        raw = self.artifact_store.load_bytes(
            artifact.artifact_id
        )

        if len(raw) != artifact.byte_count:
            raise ValueError(
                "StudyRevision plan artifact byte count "
                "does not match metadata"
            )

        plan = decode_canonical_bytes(
            raw,
            schema=STUDY_REVISION_SCHEMA_ID,
        )

        if not isinstance(plan, dict):
            raise ValueError(
                "registered StudyRevision plan must "
                "decode to a mapping"
            )

        if (
            plan.get("study_id")
            != revision.study_id
        ):
            raise ValueError(
                "registered plan study_id does not "
                "match StudyRevision"
            )

        repository_revision = (
            self._require_string(
                plan,
                "repository_revision",
            )
        )

        if (
            repository_revision
            != revision.repository_revision
        ):
            raise ValueError(
                "registered plan repository revision "
                "does not match StudyRevision"
            )

        reuse_policy_value = self._require_string(
            plan,
            "evidence_reuse_policy",
        )

        try:
            reuse_policy = EvidenceReusePolicy(
                reuse_policy_value
            )
        except ValueError as error:
            raise ValueError(
                "registered plan evidence reuse policy "
                "is unsupported"
            ) from error

        if (
            reuse_policy
            is not revision.evidence_reuse_policy
        ):
            raise ValueError(
                "registered plan evidence reuse policy "
                "does not match StudyRevision"
            )

        variants = plan.get(
            "parameter_variants"
        )

        if (
            not isinstance(variants, list)
            or not variants
        ):
            raise ValueError(
                "registered plan parameter_variants "
                "must be a non-empty list"
            )

        matching_configuration = None
        seen_fingerprints = set()

        for item in variants:
            if (
                not isinstance(item, dict)
                or set(item)
                != {"fingerprint", "configuration"}
            ):
                raise ValueError(
                    "registered parameter variant must "
                    "contain exactly fingerprint and configuration"
                )

            fingerprint = item["fingerprint"]
            configuration = item["configuration"]

            if (
                not isinstance(fingerprint, str)
                or not isinstance(
                    configuration,
                    dict,
                )
            ):
                raise ValueError(
                    "registered parameter variant has "
                    "invalid field types"
                )

            actual_fingerprint = (
                canonical_fingerprint(
                    configuration,
                    schema=(
                        PARAMETER_VARIANT_SCHEMA_ID
                    ),
                )
            )

            if actual_fingerprint != fingerprint:
                raise ValueError(
                    "registered parameter variant "
                    "fingerprint does not match configuration"
                )

            if fingerprint in seen_fingerprints:
                raise ValueError(
                    "registered plan contains duplicate "
                    "parameter variant fingerprints"
                )

            seen_fingerprints.add(
                fingerprint
            )

            if (
                fingerprint
                == trial.parameter_configuration_fingerprint
            ):
                matching_configuration = dict(
                    configuration
                )

        if matching_configuration is None:
            raise ValueError(
                "Trial parameter configuration fingerprint "
                "is not present in its registered plan"
            )

        research_range = self._require_mapping(
            plan,
            "research_range",
        )

        if set(research_range) != {"start", "end"}:
            raise ValueError(
                "registered plan research_range must "
                "contain exactly start and end"
            )

        resolved_range = TimeRange(
            research_range["start"],
            research_range["end"],
        )

        trial_range = TimeRange(
            trial.membership_episode_start,
            trial.membership_episode_end,
        )

        if (
            trial_range.start < resolved_range.start
            or trial_range.end > resolved_range.end
        ):
            raise ValueError(
                "Trial membership episode is outside "
                "the registered StudyRevision research range"
            )

        initial_capital = plan.get(
            "initial_capital"
        )

        return RegisteredTrialExecutionPlan(
            trial_id=trial.trial_id,
            study_revision_id=(
                revision.study_revision_id
            ),
            instrument_id=trial.instrument_id,
            strategy_procedure_id=(
                self._require_string(
                    plan,
                    "strategy_procedure_id",
                )
            ),
            timeframe=self._require_string(
                plan,
                "timeframe",
            ),
            research_range=resolved_range,
            trial_range=trial_range,
            timezone=self._require_string(
                plan,
                "timezone",
            ),
            initial_capital=initial_capital,
            risk_economic_configuration=(
                self._require_mapping(
                    plan,
                    "risk_economic_configuration",
                )
            ),
            parameter_configuration=(
                matching_configuration
            ),
            data_treatment_basis=(
                self._require_mapping(
                    plan,
                    "data_treatment_basis",
                )
            ),
            repository_revision=(
                repository_revision
            ),
            evidence_reuse_policy=(
                reuse_policy
            ),
        )

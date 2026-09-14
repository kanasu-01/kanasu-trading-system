"""Immutable logical model for persisted research reproducibility evidence."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import re

from core.market_data.historical_coverage import TimeRange
from core.runtime.dataset_context import DatasetContext


_FINGERPRINT_PATTERN = re.compile(r"^sha256:[0-9a-f]{64}$")


class ResearchEvidenceStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    FAILED = "FAILED"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class ResearchEvidence:
    evidence_id: str
    created_at: datetime
    status: ResearchEvidenceStatus
    dataset_context: DatasetContext
    requested_range: TimeRange
    dataset_fingerprint: str | None = None
    configuration_fingerprint: str | None = None
    result_fingerprint: str | None = None
    provenance: tuple[tuple[str, str], ...] | Mapping[str, str] = ()
    repository_revision: str | None = None
    summary: str = ""
    artifact_references: tuple[str, ...] | list[str] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, str) or not self.evidence_id:
            raise ValueError("evidence_id must be a non-empty string")
        if not isinstance(self.created_at, datetime):
            raise TypeError("research evidence created_at must be a datetime")
        if self.created_at.utcoffset() is None:
            raise ValueError("research evidence created_at must be timezone-aware")
        if not isinstance(self.status, ResearchEvidenceStatus):
            raise TypeError("status must be a ResearchEvidenceStatus")
        if not isinstance(self.dataset_context, DatasetContext):
            raise TypeError("dataset_context must be a DatasetContext")
        if not isinstance(self.requested_range, TimeRange):
            raise TypeError("requested_range must be a TimeRange")

        fingerprint_values = (
            self.dataset_fingerprint,
            self.configuration_fingerprint,
            self.result_fingerprint,
        )
        for value in fingerprint_values:
            if value is not None and not _FINGERPRINT_PATTERN.fullmatch(value):
                raise ValueError(
                    "fingerprint must use sha256:<64 lowercase hexadecimal>"
                )
        if (
            self.status is ResearchEvidenceStatus.ACCEPTED
            and any(value is None for value in fingerprint_values)
        ):
            raise ValueError(
                "ACCEPTED evidence requires dataset, configuration, "
                "and result fingerprints"
            )

        normalized_provenance = self._normalize_provenance(self.provenance)
        if not isinstance(self.artifact_references, (list, tuple)):
            raise TypeError(
                "artifact references must be an ordered list or tuple"
            )
        normalized_artifacts = tuple(self.artifact_references)
        if any(not isinstance(value, str) for value in normalized_artifacts):
            raise TypeError("artifact references must be strings")
        if self.repository_revision is not None and not isinstance(
            self.repository_revision,
            str,
        ):
            raise TypeError("repository_revision must be a string or None")
        if not isinstance(self.summary, str):
            raise TypeError("summary must be a string")

        object.__setattr__(self, "provenance", normalized_provenance)
        object.__setattr__(self, "artifact_references", normalized_artifacts)

    @staticmethod
    def _normalize_provenance(
        provenance: tuple[tuple[str, str], ...] | Mapping[str, str],
    ) -> tuple[tuple[str, str], ...]:
        items = (
            list(provenance.items())
            if isinstance(provenance, Mapping)
            else list(provenance)
        )
        normalized: list[tuple[str, str]] = []
        for item in items:
            if not isinstance(item, (list, tuple)) or len(item) != 2:
                raise TypeError("provenance must contain key/value pairs")
            key, value = item
            if not isinstance(key, str) or not isinstance(value, str):
                raise TypeError("provenance keys and values must be strings")
            normalized.append((key, value))

        normalized.sort(key=lambda item: item[0])
        if len({key for key, _ in normalized}) != len(normalized):
            raise ValueError("provenance keys must be unique")
        return tuple(normalized)

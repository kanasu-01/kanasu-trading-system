from datetime import datetime, timedelta, timezone
import re

import pytest

from core.market_data.historical_coverage import TimeRange
from core.research.models.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStatus,
)
from core.runtime.dataset_context import DatasetContext


INDIA = timezone(timedelta(hours=5, minutes=30))
CREATED_AT = datetime(2026, 2, 3, 10, 11, 12, 345678, tzinfo=INDIA)
CONTEXT = DatasetContext("RELIANCE", "15m", "Asia/Kolkata")
REQUEST = TimeRange(CREATED_AT, CREATED_AT + timedelta(hours=1))


def fingerprint(character: str) -> str:
    value = f"sha256:{character * 64}"
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", value)
    return value


def evidence(**changes) -> ResearchEvidence:
    values = {
        "evidence_id": "evidence-001",
        "created_at": CREATED_AT,
        "status": ResearchEvidenceStatus.ACCEPTED,
        "dataset_context": CONTEXT,
        "requested_range": REQUEST,
        "dataset_fingerprint": fingerprint("a"),
        "configuration_fingerprint": fingerprint("b"),
        "result_fingerprint": fingerprint("c"),
        "provenance": {"source_policy": "LOCAL_ONLY", "provider": "fixture"},
        "repository_revision": "abc1234",
        "summary": "Deterministic reference run",
        "artifact_references": ("trades.json", "equity.csv"),
    }
    values.update(changes)
    return ResearchEvidence(**values)


def test_research_evidence_is_immutable_and_normalizes_metadata():
    record = evidence()

    assert record.provenance == (
        ("provider", "fixture"),
        ("source_policy", "LOCAL_ONLY"),
    )
    assert record.artifact_references == ("trades.json", "equity.csv")
    with pytest.raises(AttributeError):
        record.status = ResearchEvidenceStatus.FAILED


def test_artifact_reference_list_normalizes_to_tuple():
    record = evidence(artifact_references=["trades.json", "equity.csv"])

    assert record.artifact_references == ("trades.json", "equity.csv")


@pytest.mark.parametrize(
    "artifact_references",
    [
        "trades.json",
        b"trades.json",
        {"trades.json"},
        {"primary": "trades.json"},
    ],
)
def test_artifact_references_reject_non_ordered_collections(
    artifact_references,
):
    with pytest.raises(TypeError, match="ordered list or tuple"):
        evidence(artifact_references=artifact_references)


@pytest.mark.parametrize(
    "missing",
    [
        "dataset_fingerprint",
        "configuration_fingerprint",
        "result_fingerprint",
    ],
)
def test_accepted_evidence_requires_all_three_fingerprints(missing):
    with pytest.raises(ValueError, match="ACCEPTED evidence requires"):
        evidence(**{missing: None})


@pytest.mark.parametrize("bad_value", ["", "sha256:ABC", "sha256:" + "g" * 64])
def test_supplied_fingerprint_format_is_validated(bad_value):
    with pytest.raises(ValueError, match="fingerprint"):
        evidence(dataset_fingerprint=bad_value)


def test_created_at_must_be_timezone_aware():
    with pytest.raises(ValueError, match="timezone-aware"):
        evidence(created_at=CREATED_AT.replace(tzinfo=None))


def test_created_at_must_be_a_datetime():
    with pytest.raises(TypeError, match="must be a datetime"):
        evidence(created_at="2026-02-03T10:11:12+05:30")


def test_timezone_aware_created_at_remains_valid():
    assert evidence(created_at=CREATED_AT).created_at == CREATED_AT


@pytest.mark.parametrize(
    "status",
    [ResearchEvidenceStatus.FAILED, ResearchEvidenceStatus.INCOMPLETE],
)
def test_nonaccepted_evidence_may_contain_partial_identity(status):
    record = evidence(
        status=status,
        configuration_fingerprint=None,
        result_fingerprint=None,
    )

    assert record.status is status
    assert record.dataset_fingerprint == fingerprint("a")
    assert record.configuration_fingerprint is None
    assert record.result_fingerprint is None

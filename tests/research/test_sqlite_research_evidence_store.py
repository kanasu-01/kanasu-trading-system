from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.research.models.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStatus,
)
from core.research.sqlite_research_evidence_store import (
    SQLiteResearchEvidenceStore,
)
from core.runtime.dataset_context import DatasetContext


INDIA = timezone(timedelta(hours=5, minutes=30))
CREATED_AT = datetime(2026, 3, 4, 11, 22, 33, 456789, tzinfo=INDIA)
CONTEXT = DatasetContext("RELIANCE", "15m", "Asia/Kolkata")
REQUEST = TimeRange(CREATED_AT, CREATED_AT + timedelta(hours=1))


def fingerprint(character: str) -> str:
    return f"sha256:{character * 64}"


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
        "provenance": {"provider": "fixture", "source_policy": "LOCAL_ONLY"},
        "repository_revision": "abc1234",
        "summary": "Reference result",
        "artifact_references": ("trades.json", "equity.csv"),
    }
    values.update(changes)
    return ResearchEvidence(**values)


def test_accepted_evidence_round_trips_through_fresh_store(tmp_path):
    path = tmp_path / "research" / "evidence.sqlite3"
    original = evidence()
    SQLiteResearchEvidenceStore(path).save(original)

    loaded = SQLiteResearchEvidenceStore(path).load(original.evidence_id)

    assert loaded == original
    assert loaded is not original
    assert loaded.created_at.isoformat(timespec="microseconds") == (
        original.created_at.isoformat(timespec="microseconds")
    )
    assert loaded.provenance == original.provenance
    assert loaded.repository_revision == original.repository_revision
    assert loaded.summary == original.summary
    assert loaded.artifact_references == original.artifact_references


@pytest.mark.parametrize(
    "status",
    [ResearchEvidenceStatus.FAILED, ResearchEvidenceStatus.INCOMPLETE],
)
def test_nonaccepted_status_survives_persistence(status, tmp_path):
    record = evidence(
        evidence_id=f"evidence-{status.value.lower()}",
        status=status,
        result_fingerprint=None,
    )
    path = tmp_path / "evidence.sqlite3"
    SQLiteResearchEvidenceStore(path).save(record)

    loaded = SQLiteResearchEvidenceStore(path).load(record.evidence_id)

    assert loaded == record
    assert loaded.status is status
    assert loaded.status is not ResearchEvidenceStatus.ACCEPTED


def test_duplicate_evidence_id_is_rejected_without_overwrite(tmp_path):
    path = tmp_path / "evidence.sqlite3"
    store = SQLiteResearchEvidenceStore(path)
    original = evidence()
    store.save(original)

    with pytest.raises(ValueError, match="already exists"):
        store.save(evidence(summary="replacement must not win"))

    assert SQLiteResearchEvidenceStore(path).load(original.evidence_id) == original


def test_missing_evidence_returns_none(tmp_path):
    store = SQLiteResearchEvidenceStore(tmp_path / "evidence.sqlite3")

    assert store.load("does-not-exist") is None


def test_evidence_store_is_separate_from_historical_storage(tmp_path):
    historical_path = tmp_path / "historical.sqlite3"
    evidence_path = tmp_path / "research-evidence.sqlite3"
    candle = Candle(
        timestamp=CREATED_AT,
        open=100.0,
        high=103.0,
        low=99.0,
        close=102.0,
        volume=500.0,
    )
    historical = SQLiteCandleStore(historical_path)
    historical.save_retrieval(CONTEXT, [candle], [REQUEST])

    SQLiteResearchEvidenceStore(evidence_path).save(evidence())

    assert historical_path != evidence_path
    assert SQLiteCandleStore(historical_path).load(CONTEXT, REQUEST.start, REQUEST.end) == [candle]
    assert SQLiteCandleStore(historical_path).load_coverage(CONTEXT) == [REQUEST]
    with sqlite3.connect(historical_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
    assert "research_evidence" not in tables

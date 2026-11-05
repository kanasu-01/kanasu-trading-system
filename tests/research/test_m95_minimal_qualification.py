from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
import sqlite3

import pytest

from core.research.models.qualification import (
    CriterionOutcome,
    EvidenceValidity,
    QualificationOutcome,
)
from core.research.models.qualification_policy import QualificationPolicy
from core.research.models.registered_study import TrialDisposition
from core.research.qualification_service import (
    QualificationOperationalError,
    QualificationService,
)
from core.research.sqlite_qualification_store import SQLiteQualificationStore
from core.research.study_aggregation import (
    StudyAggregationError,
    StudyAggregationService,
)


NOW = datetime(2026, 11, 3, 9, 0, tzinfo=timezone.utc)
F = lambda ch: "sha256:" + (ch * 64)


def _trial(disposition=TrialDisposition.EXECUTED):
    return SimpleNamespace(
        trial_id=F("1"),
        study_revision_id=F("2"),
        experiment_spec_id=F("3"),
        parameter_configuration_fingerprint=F("4"),
        disposition=disposition,
    )


def _snapshot(trial):
    attempt = SimpleNamespace(
        attempt_id="attempt-1",
        evidence_id="evidence-1",
        result_artifact_id=F("5"),
    )
    event = SimpleNamespace(causing_job_id="job-1")
    job = SimpleNamespace(
        job_id="job-1",
        attempt_id="attempt-1",
        reused_attempt_id=None,
    )
    return SimpleNamespace(
        trial=trial,
        disposition_events=(event,),
        jobs=(job,),
        owned_attempts=(("attempt-1", attempt),),
        reused_attempts=(),
    )


class FakeCatalog:
    def __init__(self, trial):
        self.trial = trial

    def load_trial(self, trial_id):
        return self.trial if trial_id == self.trial.trial_id else None

    def load_research_trial_detail_snapshot(self, trial_id):
        return _snapshot(self.trial)


class FakeQualificationStore:
    def __init__(self, policy):
        self.policy = policy
        self.candidates = {}
        self.decisions = []

    def load_active_policy(self):
        return self.policy

    def save_candidate_revision(self, candidate):
        self.candidates[candidate.candidate_revision_id] = candidate
        return candidate

    def append_decision(self, decision):
        self.decisions.append(decision)

    def load_current_decision(self, trial_id):
        matches = [
            item
            for item in self.decisions
            if item.trial_id == trial_id and item.policy_id == self.policy.policy_id
        ]
        return matches[-1] if matches else None


def _service(policy, trial=None):
    trial = trial or _trial()
    store = FakeQualificationStore(policy)
    return (
        QualificationService(
            catalog_store=FakeCatalog(trial),
            artifact_store=SimpleNamespace(),
            qualification_store=store,
        ),
        store,
        trial,
    )


def _verified(monkeypatch, trades):
    monkeypatch.setattr(
        StudyAggregationService,
        "load_verified_trial_backtest",
        lambda self, trial_id: SimpleNamespace(
            result_artifact_id=F("5"),
            payload={"trades": trades},
        ),
    )


def test_exact_equality_is_eligible_without_display_rounding(monkeypatch):
    _verified(monkeypatch, ({"pnl": 10.0}, {"pnl": 0.0}))
    service, store, trial = _service(QualificationPolicy(1, Decimal("50")))

    decision = service.evaluate_selected_trial(trial.trial_id, evaluated_at=NOW)

    assert decision.outcome is QualificationOutcome.ELIGIBLE
    assert decision.criterion_outcome is CriterionOutcome.SATISFIED
    assert decision.profitable_trade_count == 1
    assert decision.completed_trade_count == 2
    assert decision.rate_numerator == 100
    assert decision.rate_denominator == 2
    assert service.current_eligibility(trial.trial_id) == decision.candidate_revision_id
    assert len(store.decisions) == 1


def test_exact_fraction_below_high_precision_threshold_is_rejected(monkeypatch):
    _verified(monkeypatch, ({"pnl": 10.0}, {"pnl": 0.0}))
    service, _, trial = _service(
        QualificationPolicy(1, Decimal("50.0000000000000000000000000001"))
    )

    decision = service.evaluate_selected_trial(trial.trial_id, evaluated_at=NOW)

    assert decision.outcome is QualificationOutcome.REJECTED
    assert decision.criterion_outcome is CriterionOutcome.NOT_SATISFIED
    assert service.current_eligibility(trial.trial_id) is None


def test_verified_zero_trade_result_is_insufficient_but_keeps_lineage(monkeypatch):
    _verified(monkeypatch, ())
    service, _, trial = _service(QualificationPolicy(1, Decimal("0")))

    decision = service.evaluate_selected_trial(trial.trial_id, evaluated_at=NOW)

    assert decision.evidence_validity is EvidenceValidity.VALID
    assert decision.outcome is QualificationOutcome.INSUFFICIENT
    assert decision.completed_trade_count == 0
    assert decision.profitable_trade_count == 0
    assert decision.rate_denominator is None
    assert decision.candidate_revision_id is not None


def test_non_result_bearing_selected_trial_is_insufficient(monkeypatch):
    trial = _trial(TrialDisposition.FAILED)
    service, _, _ = _service(QualificationPolicy(1, Decimal("50")), trial)

    decision = service.evaluate_selected_trial(trial.trial_id, evaluated_at=NOW)

    assert decision.evidence_validity is EvidenceValidity.INSUFFICIENT
    assert decision.outcome is QualificationOutcome.INSUFFICIENT
    assert decision.candidate_revision_id is None


def test_invalid_saved_evidence_is_not_rejected_economically(monkeypatch):
    def fail(self, trial_id):
        raise StudyAggregationError("identity mismatch")

    monkeypatch.setattr(
        StudyAggregationService,
        "load_verified_trial_backtest",
        fail,
    )
    service, store, trial = _service(QualificationPolicy(1, Decimal("50")))

    decision = service.evaluate_selected_trial(trial.trial_id, evaluated_at=NOW)

    assert decision.evidence_validity is EvidenceValidity.INVALID
    assert decision.criterion_outcome is CriterionOutcome.NOT_EVALUATED
    assert decision.outcome is QualificationOutcome.INVALID
    assert len(store.decisions) == 1


def test_storage_failure_is_operational_and_creates_no_decision(monkeypatch):
    def fail(self, trial_id):
        try:
            raise sqlite3.OperationalError("database unavailable")
        except sqlite3.OperationalError as error:
            raise StudyAggregationError("cannot verify") from error

    monkeypatch.setattr(
        StudyAggregationService,
        "load_verified_trial_backtest",
        fail,
    )
    service, store, trial = _service(QualificationPolicy(1, Decimal("50")))

    with pytest.raises(QualificationOperationalError):
        service.evaluate_selected_trial(trial.trial_id, evaluated_at=NOW)

    assert store.decisions == []


def test_no_active_policy_fails_without_decision():
    service, store, trial = _service(QualificationPolicy(1, Decimal("50")))
    store.policy = None

    with pytest.raises(QualificationOperationalError, match="no active"):
        service.evaluate_selected_trial(trial.trial_id, evaluated_at=NOW)

    assert store.decisions == []


def test_sqlite_policy_activation_is_monotonic(tmp_path):
    store = SQLiteQualificationStore(tmp_path / "research.sqlite3")
    p1 = QualificationPolicy(1, Decimal("50"))
    p2 = QualificationPolicy(2, Decimal("60"))
    store.register_policy(p1, created_at=NOW)
    store.register_policy(p2, created_at=NOW)

    store.activate_policy(p1.policy_id, activated_at=NOW)
    assert store.load_active_policy() == p1
    store.activate_policy(p2.policy_id, activated_at=NOW)
    assert store.load_active_policy() == p2

    with pytest.raises(ValueError, match="newer version"):
        store.activate_policy(p1.policy_id, activated_at=NOW)


def test_genuine_v5_research_database_migrates_to_v7(tmp_path):
    from core.research import research_schema

    path = tmp_path / "research-v5.sqlite3"
    connection = sqlite3.connect(path)
    try:
        connection.execute(research_schema._CREATE_RESEARCH_EVIDENCE_TABLE)
        for statement in research_schema._CREATE_V1_CATALOG_TABLES:
            connection.execute(statement)
        for statement in research_schema._CREATE_V2_TABLES:
            connection.execute(statement)
        for statement in research_schema._CREATE_V3_TABLES:
            connection.execute(statement)
        for statement in research_schema._CREATE_V4_TABLES:
            connection.execute(statement)
        for statement in research_schema._CREATE_V5_TABLES:
            connection.execute(statement)
        for statement in research_schema._CREATE_V2_INDEXES:
            connection.execute(statement)
        connection.execute(
            "INSERT INTO studies (study_id, created_at, display_title, archived) "
            "VALUES (?, ?, ?, ?)",
            (F("9"), NOW.isoformat(), "preserved", 0),
        )
        connection.execute("PRAGMA user_version = 5")
        connection.commit()
    finally:
        connection.close()

    SQLiteQualificationStore(path)

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 8
        assert connection.execute(
            "SELECT display_title FROM studies WHERE study_id = ?", (F("9"),)
        ).fetchone() == ("preserved",)
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert {
            "qualification_policies",
            "qualification_policy_activations",
            "fixed_candidate_revisions",
            "qualification_decisions",
        } <= tables
    finally:
        connection.close()

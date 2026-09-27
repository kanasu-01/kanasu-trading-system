from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

import core.research.backtest_research_orchestrator as orchestration
from core.backtest.backtest_result import BacktestResult
from core.config.backtest_config import BacktestConfig
from core.entities.candle import Candle
from core.research.backtest_research_orchestrator import (
    BacktestResearchOrchestrator,
)
from core.research.models.research_catalog import (
    RunAttemptState,
)
from core.research.models.research_evidence import (
    ResearchEvidenceStatus,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.software_identity import SoftwareIdentity
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)
from core.research.sqlite_research_evidence_store import (
    SQLiteResearchEvidenceStore,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.strategy_factory import create_strategy


INDIA = timezone(timedelta(hours=5, minutes=30))
START = datetime(2026, 1, 5, 9, 15, tzinfo=INDIA)
END = START + timedelta(minutes=45)
CREATED_AT = datetime(
    2026,
    9,
    28,
    2,
    20,
    tzinfo=INDIA,
)
REVISION = "d21c204da909f3e2c6201c8ca9e8af005074372f"


class StaticIdentityProvider:
    def __init__(self, identity):
        self.identity = identity

    def resolve(self):
        return self.identity


def config():
    return BacktestConfig(
        symbol="RELIANCE",
        timeframe="15m",
        strategy_name="sma_crossover",
        start=START,
        end=END,
        initial_capital=100000,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        strategy_params={
            "fast_period": 1,
            "slow_period": 2,
        },
        timezone="Asia/Kolkata",
    )


def context():
    return DatasetContext(
        symbol="RELIANCE",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )


def candles():
    return [
        Candle(
            timestamp=START + timedelta(minutes=15 * index),
            open=float(value),
            high=float(value + 1),
            low=float(value - 1),
            close=float(value),
            volume=1000.0,
        )
        for index, value in enumerate([100, 102, 101])
    ]


def row_count(path, table):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]


def make_orchestrator(
    tmp_path,
    identity,
    *,
    retrieve,
    execute,
    evidence_id="evidence-001",
):
    database = tmp_path / "research.sqlite3"

    catalog = SQLiteResearchCatalogStore(
        database,
        attempt_id_factory=lambda: "attempt-001",
    )
    evidence = SQLiteResearchEvidenceStore(database)
    artifacts = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )

    service = BacktestResearchOrchestrator(
        catalog_store=catalog,
        evidence_store=evidence,
        artifact_store=artifacts,
        software_identity_provider=StaticIdentityProvider(
            identity
        ),
        evidence_id_factory=lambda: evidence_id,
        clock=lambda: CREATED_AT,
        retrieve_candles=retrieve,
        execute_candles=execute,
    )

    return service, catalog, evidence, database


def test_clean_execution_uses_one_exact_candle_sequence_and_accepts_evidence(
    tmp_path,
    monkeypatch,
):
    exact_candles = candles()
    captured = {
        "retrieval_count": 0,
    }

    def retrieve(**kwargs):
        captured["retrieval_count"] += 1
        return exact_candles

    def execute(**kwargs):
        captured["executed"] = kwargs["candles"]
        return BacktestResult(
            trades=[],
            bar_records=[],
            session_id="runtime-001",
        )

    original_fingerprint = orchestration.dataset_fingerprint

    def fingerprint(context_value, request, values):
        captured["fingerprinted"] = values
        return original_fingerprint(
            context_value,
            request,
            values,
        )

    monkeypatch.setattr(
        orchestration,
        "dataset_fingerprint",
        fingerprint,
    )

    service, catalog, evidence_store, _ = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=retrieve,
        execute=execute,
    )

    execution = service.execute(
        historical_source=object(),
        strategy=create_strategy(config()),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
    )

    assert captured["retrieval_count"] == 1
    assert captured["fingerprinted"] is exact_candles
    assert captured["executed"] is exact_candles

    assert execution.attempt_id == "attempt-001"
    assert execution.evidence_id == "evidence-001"
    assert (
        execution.evidence_status
        is ResearchEvidenceStatus.ACCEPTED
    )

    evidence = evidence_store.load("evidence-001")
    assert evidence.status is ResearchEvidenceStatus.ACCEPTED
    assert evidence.repository_revision == REVISION
    assert evidence.dataset_fingerprint is not None
    assert evidence.configuration_fingerprint is not None
    assert evidence.result_fingerprint is not None
    assert len(evidence.artifact_references) == 2

    attempt = catalog.load_run_attempt("attempt-001")
    assert attempt.state is RunAttemptState.SUCCEEDED
    assert attempt.runtime_session_id == "runtime-001"
    assert attempt.evidence_id == "evidence-001"
    assert attempt.result_artifact_id is not None

    spec = catalog.load_experiment_spec(
        attempt.experiment_spec_id
    )
    assert spec.repository_revision == REVISION


@pytest.mark.parametrize(
    "identity",
    [
        SoftwareIdentity(REVISION, False),
        SoftwareIdentity(None, None),
    ],
)
def test_nonexact_software_identity_never_fabricates_spec_or_attempt(
    tmp_path,
    identity,
):
    values = candles()

    service, _, evidence_store, database = make_orchestrator(
        tmp_path,
        identity,
        retrieve=lambda **kwargs: values,
        execute=lambda **kwargs: BacktestResult(
            trades=[],
            bar_records=[],
            session_id="runtime-incomplete",
        ),
    )

    execution = service.execute(
        historical_source=object(),
        strategy=create_strategy(config()),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
    )

    assert execution.attempt_id is None
    assert (
        execution.evidence_status
        is ResearchEvidenceStatus.INCOMPLETE
    )

    evidence = evidence_store.load(execution.evidence_id)
    assert evidence.status is ResearchEvidenceStatus.INCOMPLETE
    assert evidence.repository_revision is None
    assert evidence.result_fingerprint is not None
    assert len(evidence.artifact_references) == 2

    assert row_count(database, "experiment_specs") == 0
    assert row_count(database, "run_attempts") == 0


def test_retrieval_failure_persists_incomplete_evidence_without_attempt(
    tmp_path,
):
    def fail_retrieval(**kwargs):
        raise RuntimeError("history unavailable")

    def must_not_execute(**kwargs):
        pytest.fail("execution must not follow retrieval failure")

    service, _, evidence_store, database = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=fail_retrieval,
        execute=must_not_execute,
        evidence_id="evidence-retrieval",
    )

    with pytest.raises(
        RuntimeError,
        match="history unavailable",
    ):
        service.execute(
            historical_source=object(),
            strategy=create_strategy(config()),
            config=config(),
            runtime_context=RuntimeContext(
                risk_per_trade_pct=1.0
            ),
            dataset_context=context(),
        )

    evidence = evidence_store.load("evidence-retrieval")
    assert evidence.status is ResearchEvidenceStatus.INCOMPLETE
    assert evidence.dataset_fingerprint is None
    assert evidence.result_fingerprint is None
    assert evidence.artifact_references == ()

    assert row_count(database, "experiment_specs") == 0
    assert row_count(database, "run_attempts") == 0


def test_execution_failure_creates_failed_evidence_and_failed_attempt(
    tmp_path,
):
    values = candles()

    def fail_execution(**kwargs):
        assert kwargs["candles"] is values
        raise RuntimeError("engine failed")

    service, catalog, evidence_store, _ = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: values,
        execute=fail_execution,
        evidence_id="evidence-failed",
    )

    with pytest.raises(
        RuntimeError,
        match="engine failed",
    ):
        service.execute(
            historical_source=object(),
            strategy=create_strategy(config()),
            config=config(),
            runtime_context=RuntimeContext(
                risk_per_trade_pct=1.0
            ),
            dataset_context=context(),
        )

    evidence = evidence_store.load("evidence-failed")
    assert evidence.status is ResearchEvidenceStatus.FAILED
    assert evidence.dataset_fingerprint is not None
    assert evidence.configuration_fingerprint is not None
    assert evidence.result_fingerprint is None
    assert len(evidence.artifact_references) == 1

    attempt = catalog.load_run_attempt("attempt-001")
    assert attempt.state is RunAttemptState.FAILED
    assert attempt.evidence_id == "evidence-failed"
    assert (
        attempt.failure_classification
        == "backtest_execution_failed"
    )
    assert attempt.failure_message == "engine failed"
    assert attempt.result_artifact_id is None

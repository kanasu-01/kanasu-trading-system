from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

import core.research.backtest_research_orchestrator as orchestration
from core.backtest.backtest_result import BacktestResult
from core.backtest.bar_record import BarRecord
from core.config.backtest_config import BacktestConfig
from core.entities.candle import Candle
from core.research.backtest_research_orchestrator import (
    BacktestResearchOrchestrator,
    PreparedBacktestResearchSpecification,
)
from core.research.models.research_catalog import (
    ResearchArtifactKind,
    RunAttemptState,
)
from core.research.models.research_evidence import (
    ResearchEvidenceStatus,
)
from core.research.reproducibility import (
    BACKTEST_RESULT_SCHEMA,
    canonical_bytes,
    decode_canonical_bytes,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
    research_artifact_reference,
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
    assert (
        captured["fingerprinted"]
        is captured["executed"]
    )
    assert (
        captured["fingerprinted"]
        is not exact_candles
    )
    assert (
        captured["fingerprinted"]
        == exact_candles
    )

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
        assert kwargs["candles"] is not values
        assert kwargs["candles"] == values
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
        == "unknown_failure"
    )
    assert attempt.failure_message == "engine failed"
    assert attempt.result_artifact_id is None



def test_exact_success_uses_atomic_terminal_transaction(
    tmp_path,
    monkeypatch,
):
    values = candles()
    service, catalog, evidence_store, _ = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: values,
        execute=lambda **kwargs: BacktestResult(
            trades=[],
            bar_records=[],
            session_id="runtime-atomic",
        ),
        evidence_id="evidence-atomic",
    )

    calls = []
    original = catalog.terminalize_attempt_with_evidence

    def atomic_terminal(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(
        catalog,
        "terminalize_attempt_with_evidence",
        atomic_terminal,
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

    assert len(calls) == 1
    _, kwargs = calls[0]
    assert kwargs["state"] is RunAttemptState.SUCCEEDED
    assert kwargs["result_artifact"] is not None
    assert kwargs["evidence"].evidence_id == "evidence-atomic"

    persisted = catalog.load_run_attempt(execution.attempt_id)
    assert persisted.state is RunAttemptState.SUCCEEDED
    assert persisted.evidence_id == execution.evidence_id
    assert evidence_store.load(
        execution.evidence_id
    ).status is ResearchEvidenceStatus.ACCEPTED


def test_exact_failure_uses_atomic_terminal_transaction(
    tmp_path,
    monkeypatch,
):
    values = candles()

    def fail_execution(**kwargs):
        raise RuntimeError("atomic engine failure")

    service, catalog, evidence_store, _ = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: values,
        execute=fail_execution,
        evidence_id="evidence-atomic-failure",
    )

    calls = []
    original = catalog.terminalize_attempt_with_evidence

    def atomic_terminal(*args, **kwargs):
        calls.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(
        catalog,
        "terminalize_attempt_with_evidence",
        atomic_terminal,
    )

    with pytest.raises(
        RuntimeError,
        match="atomic engine failure",
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

    assert len(calls) == 1
    _, kwargs = calls[0]
    assert kwargs["state"] is RunAttemptState.FAILED
    assert kwargs.get("result_artifact") is None
    assert (
        kwargs["evidence"].status
        is ResearchEvidenceStatus.FAILED
    )

    attempt = catalog.load_run_attempt("attempt-001")
    assert attempt.state is RunAttemptState.FAILED
    assert evidence_store.load(
        "evidence-atomic-failure"
    ).status is ResearchEvidenceStatus.FAILED


def test_terminal_persistence_failure_does_not_claim_durable_success(
    tmp_path,
    monkeypatch,
):
    values = candles()
    service, catalog, evidence_store, _ = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: values,
        execute=lambda **kwargs: BacktestResult(
            trades=[],
            bar_records=[],
            session_id="runtime-not-durable",
        ),
        evidence_id="evidence-must-not-commit",
    )

    def fail_terminal(*args, **kwargs):
        raise RuntimeError("terminal transaction unavailable")

    monkeypatch.setattr(
        catalog,
        "terminalize_attempt_with_evidence",
        fail_terminal,
    )

    with pytest.raises(
        RuntimeError,
        match="terminal transaction unavailable",
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

    attempt = catalog.load_run_attempt("attempt-001")
    assert attempt.state is RunAttemptState.RUNNING
    assert attempt.evidence_id is None
    assert attempt.result_artifact_id is None
    assert evidence_store.load(
        "evidence-must-not-commit"
    ) is None


def test_prepare_specification_resolves_exact_spec_without_attempt_or_execution(
    tmp_path,
):
    values = candles()

    def must_not_execute(**kwargs):
        pytest.fail(
            "specification preparation must not execute Backtest"
        )

    service, catalog, evidence_store, database = make_orchestrator(
        tmp_path,
        SoftwareIdentity(
            REVISION,
            True,
        ),
        retrieve=lambda **kwargs: values,
        execute=must_not_execute,
        evidence_id="evidence-not-created",
    )

    prepared = service.prepare_specification(
        historical_source=object(),
        strategy=create_strategy(
            config()
        ),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
    )

    assert isinstance(
        prepared,
        PreparedBacktestResearchSpecification,
    )

    assert prepared.candles is values
    assert prepared.identity.is_exact
    assert prepared.experiment_spec_id is not None
    assert prepared.manifest_artifact_id is not None
    assert prepared.manifest_reference.startswith(
        "artifact:sha256:"
    )

    persisted_spec = (
        catalog.load_experiment_spec(
            prepared.experiment_spec_id
        )
    )

    assert persisted_spec is not None
    assert (
        persisted_spec.repository_revision
        == REVISION
    )

    assert row_count(
        database,
        "experiment_specs",
    ) == 1

    assert row_count(
        database,
        "run_attempts",
    ) == 0

    assert row_count(
        database,
        "research_evidence",
    ) == 0

    assert (
        evidence_store.load(
            "evidence-not-created"
        )
        is None
    )


def test_execute_delegates_through_preparation_seam(
    tmp_path,
    monkeypatch,
):
    values = candles()

    service, _, _, _ = make_orchestrator(
        tmp_path,
        SoftwareIdentity(
            REVISION,
            True,
        ),
        retrieve=lambda **kwargs: values,
        execute=lambda **kwargs: BacktestResult(
            trades=[],
            bar_records=[],
            session_id="runtime-preparation-seam",
        ),
        evidence_id="evidence-preparation-seam",
    )

    original = (
        service.prepare_specification
    )

    calls = []

    def tracked_prepare(**kwargs):
        calls.append(kwargs)

        return original(
            **kwargs
        )

    monkeypatch.setattr(
        service,
        "prepare_specification",
        tracked_prepare,
    )

    execution = service.execute(
        historical_source=object(),
        strategy=create_strategy(
            config()
        ),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
    )

    assert len(calls) == 1
    assert execution.attempt_id == "attempt-001"
    assert (
        execution.evidence_status
        is ResearchEvidenceStatus.ACCEPTED
    )


def test_exact_reuse_resolver_accepts_only_verified_accepted_execution(
    tmp_path,
):
    service, catalog, _, database = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: candles(),
        execute=lambda **kwargs: BacktestResult(
            trades=[],
            bar_records=[],
            session_id="runtime-reuse-source",
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

    source_attempt = catalog.load_run_attempt(
        execution.attempt_id
    )
    assert source_attempt is not None

    before = row_count(database, "run_attempts")

    reusable = service.find_exact_reusable_execution(
        source_attempt.experiment_spec_id
    )

    assert reusable is not None
    assert reusable.attempt == source_attempt
    assert (
        reusable.evidence.status
        is ResearchEvidenceStatus.ACCEPTED
    )
    assert (
        reusable.result_artifact.artifact_id
        == source_attempt.result_artifact_id
    )
    assert row_count(database, "run_attempts") == before



def test_exact_reuse_resolver_rejects_missing_manifest_reference(
    tmp_path,
):
    service, catalog, _, database = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: candles(),
        execute=lambda **kwargs: BacktestResult(
            trades=[],
            bar_records=[],
            session_id="runtime-reuse-missing-manifest-reference",
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

    source_attempt = catalog.load_run_attempt(
        execution.attempt_id
    )
    assert source_attempt is not None
    assert source_attempt.evidence_id is not None
    assert source_attempt.result_artifact_id is not None

    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE research_evidence
            SET artifact_references = ?
            WHERE evidence_id = ?
            """,
            (
                (
                    '["'
                    + research_artifact_reference(
                        source_attempt.result_artifact_id
                    )
                    + '"]'
                ),
                source_attempt.evidence_id,
            ),
        )
        connection.commit()

    assert (
        service.find_exact_reusable_execution(
            source_attempt.experiment_spec_id
        )
        is None
    )



def test_exact_reuse_resolver_rejects_incomplete_evidence(
    tmp_path,
):
    service, catalog, _, database = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: candles(),
        execute=lambda **kwargs: BacktestResult(
            trades=[],
            bar_records=[],
            session_id="runtime-reuse-rejected",
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

    source_attempt = catalog.load_run_attempt(
        execution.attempt_id
    )
    assert source_attempt is not None
    assert source_attempt.evidence_id is not None

    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            UPDATE research_evidence
            SET status = 'INCOMPLETE'
            WHERE evidence_id = ?
            """,
            (source_attempt.evidence_id,),
        )
        connection.commit()

    before = row_count(database, "run_attempts")

    assert (
        service.find_exact_reusable_execution(
            source_attempt.experiment_spec_id
        )
        is None
    )
    assert row_count(database, "run_attempts") == before


def test_execute_prepared_uses_supplied_attempt_without_duplicate(
    tmp_path,
):
    service, catalog, _, database = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: candles(),
        execute=lambda **kwargs: BacktestResult(
            trades=[],
            bar_records=[],
            session_id="runtime-supplied-attempt",
        ),
    )

    prepared = service.prepare_specification(
        historical_source=object(),
        strategy=create_strategy(config()),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
    )

    assert prepared.experiment_spec_id is not None

    attempt = catalog.create_running_attempt(
        experiment_spec_id=prepared.experiment_spec_id,
        created_at=CREATED_AT,
    )

    calls = []

    def terminalize(attempt_id, **kwargs):
        calls.append((attempt_id, kwargs["state"]))
        return catalog.terminalize_attempt_with_evidence(
            attempt_id,
            **kwargs,
        )

    before = row_count(database, "run_attempts")

    execution = service._execute_prepared_internal(
        prepared=prepared,
        strategy=create_strategy(config()),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
        attempt=attempt,
        attempt_terminalizer=terminalize,
    )

    assert row_count(database, "run_attempts") == before
    assert execution.attempt_id == attempt.attempt_id
    assert calls == [
        (
            attempt.attempt_id,
            RunAttemptState.SUCCEEDED,
        )
    ]

    persisted = catalog.load_run_attempt(
        attempt.attempt_id
    )
    assert persisted is not None
    assert persisted.state is RunAttemptState.SUCCEEDED
    assert persisted.runtime_session_id == "runtime-supplied-attempt"


def test_execute_prepared_terminalizes_supplied_attempt_on_failure(
    tmp_path,
):
    def fail_execute(**kwargs):
        raise RuntimeError("m94d supplied-attempt failure")

    service, catalog, _, database = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: candles(),
        execute=fail_execute,
        evidence_id="evidence-supplied-failure",
    )

    prepared = service.prepare_specification(
        historical_source=object(),
        strategy=create_strategy(config()),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
    )

    assert prepared.experiment_spec_id is not None

    attempt = catalog.create_running_attempt(
        experiment_spec_id=prepared.experiment_spec_id,
        created_at=CREATED_AT,
    )

    calls = []

    def terminalize(attempt_id, **kwargs):
        calls.append((attempt_id, kwargs["state"]))
        return catalog.terminalize_attempt_with_evidence(
            attempt_id,
            **kwargs,
        )

    before = row_count(database, "run_attempts")

    with pytest.raises(
        RuntimeError,
        match="m94d supplied-attempt failure",
    ):
        service._execute_prepared_internal(
            prepared=prepared,
            strategy=create_strategy(config()),
            config=config(),
            runtime_context=RuntimeContext(
                risk_per_trade_pct=1.0
            ),
            dataset_context=context(),
            attempt=attempt,
            attempt_terminalizer=terminalize,
        )

    assert row_count(database, "run_attempts") == before
    assert calls == [
        (
            attempt.attempt_id,
            RunAttemptState.FAILED,
        )
    ]

    persisted = catalog.load_run_attempt(
        attempt.attempt_id
    )
    assert persisted is not None
    assert persisted.state is RunAttemptState.FAILED
    assert (
        persisted.failure_classification
        == "unknown_failure"
    )


def _m94g1_prepared_environment(tmp_path):
    execution_calls = []

    def execute(**kwargs):
        execution_calls.append(kwargs)
        return BacktestResult(
            trades=[],
            bar_records=[],
            session_id="runtime-m94g1-drift",
        )

    service, _, _, _ = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: candles(),
        execute=execute,
        evidence_id="evidence-m94g1-drift",
    )

    cfg = config()
    strategy = create_strategy(cfg)
    runtime_context = RuntimeContext(
        risk_per_trade_pct=1.0
    )
    dataset_context = context()

    prepared = service.prepare_specification(
        historical_source=object(),
        strategy=strategy,
        config=cfg,
        runtime_context=runtime_context,
        dataset_context=dataset_context,
    )

    return (
        service,
        prepared,
        strategy,
        cfg,
        runtime_context,
        dataset_context,
        execution_calls,
    )


def test_m94h1_manifest_io_race_executes_verified_private_snapshot(
    tmp_path,
    monkeypatch,
):
    from threading import Event, Thread

    (
        service,
        prepared,
        strategy,
        cfg,
        runtime_context,
        dataset_context,
        execution_calls,
    ) = _m94g1_prepared_environment(
        tmp_path
    )

    original_capital = cfg.initial_capital
    started = Event()
    release = Event()
    original_load = (
        service.artifact_store.load_bytes
    )
    blocked_once = {
        "value": False,
    }

    def blocking_load(artifact_id):
        if (
            artifact_id
            == prepared.manifest_artifact_id
            and not blocked_once["value"]
        ):
            blocked_once["value"] = True
            started.set()
            if not release.wait(5):
                raise RuntimeError(
                    "test manifest barrier timed out"
                )

        return original_load(
            artifact_id
        )

    monkeypatch.setattr(
        service.artifact_store,
        "load_bytes",
        blocking_load,
    )

    errors = []

    def run_execution():
        try:
            service.execute_prepared(
                prepared=prepared,
                strategy=strategy,
                config=cfg,
                runtime_context=runtime_context,
                dataset_context=dataset_context,
            )
        except Exception as error:
            errors.append(error)

    thread = Thread(
        target=run_execution,
        daemon=True,
    )
    thread.start()

    assert started.wait(5)

    cfg.initial_capital = (
        original_capital * 2
    )

    release.set()
    thread.join(5)

    assert not thread.is_alive()
    assert errors == []
    assert len(execution_calls) == 1
    assert (
        execution_calls[0]["config"]
        is not cfg
    )
    assert (
        execution_calls[0]["config"].initial_capital
        == original_capital
    )


def test_m94g1_execute_prepared_rejects_initial_capital_drift(
    tmp_path,
):
    (
        service,
        prepared,
        strategy,
        cfg,
        runtime_context,
        dataset_context,
        execution_calls,
    ) = _m94g1_prepared_environment(tmp_path)

    cfg.initial_capital = 200000

    with pytest.raises(
        ValueError,
        match="prepared.*execution|execution.*prepared|identity",
    ):
        service.execute_prepared(
            prepared=prepared,
            strategy=strategy,
            config=cfg,
            runtime_context=runtime_context,
            dataset_context=dataset_context,
        )

    assert execution_calls == []


def test_m94g1_execute_prepared_rejects_runtime_economic_drift(
    tmp_path,
):
    (
        service,
        prepared,
        strategy,
        cfg,
        _,
        dataset_context,
        execution_calls,
    ) = _m94g1_prepared_environment(tmp_path)

    drifted_runtime = RuntimeContext(
        risk_per_trade_pct=2.0
    )

    with pytest.raises(
        ValueError,
        match="prepared.*execution|execution.*prepared|identity",
    ):
        service.execute_prepared(
            prepared=prepared,
            strategy=strategy,
            config=cfg,
            runtime_context=drifted_runtime,
            dataset_context=dataset_context,
        )

    assert execution_calls == []


def test_m94g1_execute_prepared_rejects_strategy_parameter_drift(
    tmp_path,
):
    (
        service,
        prepared,
        strategy,
        cfg,
        runtime_context,
        dataset_context,
        execution_calls,
    ) = _m94g1_prepared_environment(tmp_path)

    strategy.slow_period = 3

    with pytest.raises(
        ValueError,
        match="prepared.*execution|execution.*prepared|identity",
    ):
        service.execute_prepared(
            prepared=prepared,
            strategy=strategy,
            config=cfg,
            runtime_context=runtime_context,
            dataset_context=dataset_context,
        )

    assert execution_calls == []


def test_m94g1_execute_prepared_rejects_dataset_context_drift(
    tmp_path,
):
    (
        service,
        prepared,
        strategy,
        cfg,
        runtime_context,
        _,
        execution_calls,
    ) = _m94g1_prepared_environment(tmp_path)

    drifted_context = DatasetContext(
        symbol="TCS",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )

    with pytest.raises(
        ValueError,
        match="prepared.*execution|execution.*prepared|identity",
    ):
        service.execute_prepared(
            prepared=prepared,
            strategy=strategy,
            config=cfg,
            runtime_context=runtime_context,
            dataset_context=drifted_context,
        )

    assert execution_calls == []


def test_m94g1_execute_prepared_rejects_candle_content_drift(
    tmp_path,
):
    (
        service,
        prepared,
        strategy,
        cfg,
        runtime_context,
        dataset_context,
        execution_calls,
    ) = _m94g1_prepared_environment(tmp_path)

    original = prepared.candles[0]
    prepared.candles[0] = Candle(
        timestamp=original.timestamp,
        open=original.open + 1.0,
        high=original.high + 1.0,
        low=original.low + 1.0,
        close=original.close + 1.0,
        volume=original.volume,
    )

    with pytest.raises(
        ValueError,
        match="prepared.*execution|execution.*prepared|identity",
    ):
        service.execute_prepared(
            prepared=prepared,
            strategy=strategy,
            config=cfg,
            runtime_context=runtime_context,
            dataset_context=dataset_context,
        )

    assert execution_calls == []


def test_execute_prepared_supplied_attempt_requires_terminalizer(
    tmp_path,
):
    execution_calls = []

    def execute(**kwargs):
        execution_calls.append(kwargs)
        return BacktestResult(
            trades=[],
            bar_records=[],
            session_id=(
                "runtime-m94j-missing-terminalizer"
            ),
        )

    service, catalog, _, database = (
        make_orchestrator(
            tmp_path,
            SoftwareIdentity(
                REVISION,
                True,
            ),
            retrieve=lambda **kwargs: candles(),
            execute=execute,
        )
    )

    prepared = service.prepare_specification(
        historical_source=object(),
        strategy=create_strategy(config()),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
    )

    assert prepared.experiment_spec_id is not None

    attempt = catalog.create_running_attempt(
        experiment_spec_id=(
            prepared.experiment_spec_id
        ),
        created_at=CREATED_AT,
    )

    before = row_count(
        database,
        "run_attempts",
    )

    with pytest.raises(
        ValueError,
        match=(
            "supplied RunAttempt requires "
            "attempt_terminalizer"
        ),
    ):
        service._execute_prepared_internal(
            prepared=prepared,
            strategy=create_strategy(config()),
            config=config(),
            runtime_context=RuntimeContext(
                risk_per_trade_pct=1.0
            ),
            dataset_context=context(),
            attempt=attempt,
        )

    assert execution_calls == []
    assert (
        row_count(
            database,
            "run_attempts",
        )
        == before
    )

    persisted = catalog.load_run_attempt(
        attempt.attempt_id
    )

    assert persisted is not None
    assert (
        persisted.state
        is RunAttemptState.RUNNING
    )



@pytest.mark.parametrize(
    "case",
    (
        "trade_quantity_zero",
        "negative_transaction_cost",
        "inconsistent_net_pnl",
        "inconsistent_gross_pnl",
        "inconsistent_return_pct",
        "inconsistent_gross_pnl_no_exit_time",
        "inconsistent_return_pct_no_exit_time",
        "zero_exit_price_no_exit_time",
        "negative_exit_price_no_exit_time",
        "incorrect_marked_equity",
        "drawdown_below_minus_one",
        "incomplete_execution_fields",
    ),
)
def test_m94l_exact_reuse_rejects_additional_canonical_counterexamples(
    tmp_path,
    case,
):
    service, catalog, _, database = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: candles(),
        execute=lambda **kwargs: BacktestResult(
            trades=[],
            bar_records=[
                BarRecord(
                    timestamp=START,
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1000.0,
                    strategy="m94l-reuse-fixture",
                    state=None,
                    signal=None,
                    execution_event=None,
                    execution_price=None,
                    execution_quantity=None,
                    decision_snapshot={},
                    equity=100_000.0,
                    cash=100_000.0,
                    position_size=0.0,
                    drawdown=0.0,
                ),
            ],
            session_id="runtime-m94l-reuse-source",
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

    source_attempt = catalog.load_run_attempt(
        execution.attempt_id
    )

    assert source_attempt is not None
    assert source_attempt.evidence_id is not None
    assert source_attempt.result_artifact_id is not None

    source_result_id = (
        source_attempt.result_artifact_id
    )

    payload = decode_canonical_bytes(
        service.artifact_store.load_bytes(
            source_result_id
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    if case in {
        "trade_quantity_zero",
        "negative_transaction_cost",
        "inconsistent_net_pnl",
        "inconsistent_gross_pnl",
        "inconsistent_return_pct",
        "inconsistent_gross_pnl_no_exit_time",
        "inconsistent_return_pct_no_exit_time",
        "zero_exit_price_no_exit_time",
        "negative_exit_price_no_exit_time",
    }:
        payload["trades"].append(
            {
                "symbol": "RELIANCE",
                "entry_time": START,
                "entry_price": 100.0,
                "exit_time": END,
                "exit_price": 101.0,
                "stop_price": 99.0,
                "quantity": 1,
                "direction": "LONG",
                "exit_reason": "fixture",
                "pnl": 1.0,
                "gross_pnl": 1.0,
                "transaction_cost": 0.0,
                "pnl_pct": 1.0,
            }
        )

        if case == "trade_quantity_zero":
            payload["trades"][0]["quantity"] = 0
        elif case == "negative_transaction_cost":
            payload["trades"][0][
                "transaction_cost"
            ] = -100.0
        elif case == "inconsistent_net_pnl":
            payload["trades"][0]["pnl"] = 2.0
        elif case in {
            "inconsistent_gross_pnl",
            "inconsistent_gross_pnl_no_exit_time",
        }:
            payload["trades"][0]["gross_pnl"] = 2.0
            payload["trades"][0]["pnl"] = 2.0
        elif case in {
            "inconsistent_return_pct",
            "inconsistent_return_pct_no_exit_time",
        }:
            payload["trades"][0]["pnl_pct"] = 99.0
        elif case in {
            "zero_exit_price_no_exit_time",
            "negative_exit_price_no_exit_time",
        }:
            trade = payload["trades"][0]
            trade["exit_price"] = (
                0.0
                if case == "zero_exit_price_no_exit_time"
                else -1.0
            )
            gross = (
                (trade["exit_price"] - trade["entry_price"])
                * trade["quantity"]
            )
            trade["gross_pnl"] = gross
            trade["pnl"] = gross - trade["transaction_cost"]
            trade["pnl_pct"] = (
                (trade["exit_price"] - trade["entry_price"])
                / trade["entry_price"]
            ) * 100
        else:
            raise AssertionError(case)

        if case.endswith("_no_exit_time"):
            payload["trades"][0]["exit_time"] = None

    elif case == "incorrect_marked_equity":
        record = payload["bar_records"][0]
        record["position_size"] = 1.0
        record["cash"] = record["equity"] - 1.0

    elif case == "drawdown_below_minus_one":
        assert payload["bar_records"][0]["equity"] > 0
        payload["bar_records"][0]["drawdown"] = -2.0

    elif case == "incomplete_execution_fields":
        record = payload["bar_records"][0]
        record["execution_event"] = None
        record["execution_price"] = None
        record["execution_quantity"] = 1

    else:
        raise AssertionError(
            f"unknown fixture case: {case}"
        )

    invalid_bytes = canonical_bytes(
        payload,
        schema=BACKTEST_RESULT_SCHEMA,
    )

    invalid_artifact = (
        service.artifact_store.persist_bytes(
            invalid_bytes,
            artifact_kind=(
                ResearchArtifactKind.BACKTEST_RESULT
            ),
            schema_id=BACKTEST_RESULT_SCHEMA,
            created_at=CREATED_AT,
        )
    )

    catalog.save_artifact(
        invalid_artifact
    )

    old_reference = research_artifact_reference(
        source_result_id
    )
    new_reference = research_artifact_reference(
        invalid_artifact.artifact_id
    )

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            """
            SELECT artifact_references
            FROM research_evidence
            WHERE evidence_id = ?
            """,
            (source_attempt.evidence_id,),
        ).fetchone()

        assert row is not None

        references = json.loads(
            row[0]
        )

        assert old_reference in references

        references = [
            (
                new_reference
                if reference == old_reference
                else reference
            )
            for reference in references
        ]

        connection.execute(
            """
            UPDATE run_attempts
            SET result_artifact_id = ?
            WHERE attempt_id = ?
            """,
            (
                invalid_artifact.artifact_id,
                source_attempt.attempt_id,
            ),
        )

        connection.execute(
            """
            UPDATE research_evidence
            SET
                result_fingerprint = ?,
                artifact_references = ?
            WHERE evidence_id = ?
            """,
            (
                invalid_artifact.artifact_id,
                json.dumps(
                    references,
                    separators=(",", ":"),
                ),
                source_attempt.evidence_id,
            ),
        )

        connection.commit()

    before = row_count(
        database,
        "run_attempts",
    )

    assert (
        service.find_exact_reusable_execution(
            source_attempt.experiment_spec_id
        )
        is None
    )

    assert (
        row_count(
            database,
            "run_attempts",
        )
        == before
    )


def test_exact_reuse_resolver_rejects_malformed_canonical_result(
    tmp_path,
    monkeypatch,
):
    service, catalog, _, database = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: candles(),
        execute=lambda **kwargs: BacktestResult(
            trades=[],
            bar_records=[],
            session_id="runtime-m94j-r03-source",
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

    source_attempt = catalog.load_run_attempt(
        execution.attempt_id
    )

    assert source_attempt is not None
    assert source_attempt.result_artifact_id is not None

    validation_calls = []

    def reject_malformed(payload):
        validation_calls.append(payload)
        raise ValueError(
            "malformed canonical Backtest result"
        )

    monkeypatch.setattr(
        orchestration,
        "decode_stable_backtest_result_bytes",
        reject_malformed,
    )

    before = row_count(
        database,
        "run_attempts",
    )

    assert (
        service.find_exact_reusable_execution(
            source_attempt.experiment_spec_id
        )
        is None
    )

    assert len(validation_calls) == 1
    assert (
        row_count(
            database,
            "run_attempts",
        )
        == before
    )


def test_m94m_public_prepared_execution_refuses_supplied_attempt_before_engine(
    tmp_path,
):
    execution_calls = []

    def execute(**kwargs):
        execution_calls.append(kwargs)
        return BacktestResult(
            trades=[],
            bar_records=[],
            session_id="unexpected-public-supplied-execution",
        )

    service, catalog, _, database = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: candles(),
        execute=execute,
    )

    prepared = service.prepare_specification(
        historical_source=object(),
        strategy=create_strategy(config()),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
    )

    assert prepared.experiment_spec_id is not None

    attempt = catalog.create_running_attempt(
        experiment_spec_id=prepared.experiment_spec_id,
        created_at=CREATED_AT,
    )

    before_count = row_count(database, "run_attempts")

    with pytest.raises(
        TypeError,
        match="unexpected keyword argument 'attempt'",
    ):
        service.execute_prepared(
            prepared=prepared,
            strategy=create_strategy(config()),
            config=config(),
            runtime_context=RuntimeContext(
                risk_per_trade_pct=1.0
            ),
            dataset_context=context(),
            attempt=attempt,
            attempt_terminalizer=lambda *args, **kwargs: None,
        )

    assert execution_calls == []
    assert row_count(database, "run_attempts") == before_count

    persisted = catalog.load_run_attempt(attempt.attempt_id)
    assert persisted is not None
    assert persisted.state is RunAttemptState.RUNNING



def test_m94m_stale_internal_supplied_attempt_cannot_reexecute(
    tmp_path,
):
    execution_calls = []

    def execute(**kwargs):
        execution_calls.append(kwargs)
        return BacktestResult(
            trades=[],
            bar_records=[],
            session_id="runtime-m94m-stale",
        )

    service, catalog, _, database = make_orchestrator(
        tmp_path,
        SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: candles(),
        execute=execute,
    )

    prepared = service.prepare_specification(
        historical_source=object(),
        strategy=create_strategy(config()),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
    )

    assert prepared.experiment_spec_id is not None

    attempt = catalog.create_running_attempt(
        experiment_spec_id=prepared.experiment_spec_id,
        created_at=CREATED_AT,
    )

    arguments = dict(
        prepared=prepared,
        strategy=create_strategy(config()),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
        attempt=attempt,
        attempt_terminalizer=(
            catalog.terminalize_attempt_with_evidence
        ),
    )

    service._execute_prepared_internal(**arguments)

    assert len(execution_calls) == 1
    assert row_count(database, "run_attempts") == 1

    persisted = catalog.load_run_attempt(attempt.attempt_id)
    assert persisted is not None
    assert persisted.state is RunAttemptState.SUCCEEDED

    with pytest.raises(
        ValueError,
        match="durably RUNNING",
    ):
        service._execute_prepared_internal(**arguments)

    assert len(execution_calls) == 1
    assert row_count(database, "run_attempts") == 1




def test_m94q_fractional_result_is_not_reused_and_fresh_execution_remains_available(
    tmp_path,
):
    database = tmp_path / "research.sqlite3"

    attempt_ids = iter(
        (
            "attempt-m94q-source",
            "attempt-m94q-fresh",
        )
    )
    evidence_ids = iter(
        (
            "evidence-m94q-source",
            "evidence-m94q-fresh",
        )
    )

    catalog = SQLiteResearchCatalogStore(
        database,
        attempt_id_factory=lambda: next(attempt_ids),
    )
    evidence_store = SQLiteResearchEvidenceStore(
        database
    )
    artifact_store = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )

    execution_calls = []

    def execute(**kwargs):
        execution_calls.append(kwargs)
        return BacktestResult(
            trades=[],
            bar_records=[
                BarRecord(
                    timestamp=START,
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1000.0,
                    strategy="m94q-reuse-fixture",
                    state=None,
                    signal=None,
                    execution_event=None,
                    execution_price=None,
                    execution_quantity=None,
                    decision_snapshot={},
                    equity=100_000.0,
                    cash=100_000.0,
                    position_size=0.0,
                    drawdown=0.0,
                ),
            ],
            session_id=(
                "runtime-m94q-"
                + str(len(execution_calls))
            ),
        )

    service = BacktestResearchOrchestrator(
        catalog_store=catalog,
        evidence_store=evidence_store,
        artifact_store=artifact_store,
        software_identity_provider=StaticIdentityProvider(
            SoftwareIdentity(
                REVISION,
                True,
            )
        ),
        evidence_id_factory=lambda: next(
            evidence_ids
        ),
        clock=lambda: CREATED_AT,
        retrieve_candles=lambda **kwargs: candles(),
        execute_candles=execute,
    )

    source = service.execute(
        historical_source=object(),
        strategy=create_strategy(config()),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
    )

    source_attempt = catalog.load_run_attempt(
        source.attempt_id
    )

    assert source_attempt is not None
    assert source_attempt.evidence_id is not None
    assert source_attempt.result_artifact_id is not None

    source_result_id = (
        source_attempt.result_artifact_id
    )

    payload = decode_canonical_bytes(
        artifact_store.load_bytes(
            source_result_id
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    record = payload["bar_records"][0]
    record["position_size"] = 1.5
    record["cash"] = (
        record["equity"]
        - record["position_size"] * record["close"]
    )

    fractional_bytes = canonical_bytes(
        payload,
        schema=BACKTEST_RESULT_SCHEMA,
    )

    fractional_artifact = (
        artifact_store.persist_bytes(
            fractional_bytes,
            artifact_kind=(
                ResearchArtifactKind.BACKTEST_RESULT
            ),
            schema_id=BACKTEST_RESULT_SCHEMA,
            created_at=CREATED_AT,
        )
    )

    catalog.save_artifact(
        fractional_artifact
    )

    old_reference = research_artifact_reference(
        source_result_id
    )
    new_reference = research_artifact_reference(
        fractional_artifact.artifact_id
    )

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            """
            SELECT artifact_references
            FROM research_evidence
            WHERE evidence_id = ?
            """,
            (source_attempt.evidence_id,),
        ).fetchone()

        assert row is not None

        references = json.loads(
            row[0]
        )

        references = [
            (
                new_reference
                if reference == old_reference
                else reference
            )
            for reference in references
        ]

        connection.execute(
            """
            UPDATE run_attempts
            SET result_artifact_id = ?
            WHERE attempt_id = ?
            """,
            (
                fractional_artifact.artifact_id,
                source_attempt.attempt_id,
            ),
        )

        connection.execute(
            """
            UPDATE research_evidence
            SET
                result_fingerprint = ?,
                artifact_references = ?
            WHERE evidence_id = ?
            """,
            (
                fractional_artifact.artifact_id,
                json.dumps(
                    references,
                    separators=(",", ":"),
                ),
                source_attempt.evidence_id,
            ),
        )

        connection.commit()

    before_reuse_lookup = row_count(
        database,
        "run_attempts",
    )

    assert before_reuse_lookup == 1

    reusable = service.find_exact_reusable_execution(
        source_attempt.experiment_spec_id
    )

    assert reusable is None

    assert (
        row_count(
            database,
            "run_attempts",
        )
        == before_reuse_lookup
    )

    fresh = service.execute(
        historical_source=object(),
        strategy=create_strategy(config()),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
    )

    assert fresh.attempt_id == "attempt-m94q-fresh"
    assert len(execution_calls) == 2

    assert (
        row_count(
            database,
            "run_attempts",
        )
        == 2
    )

    fresh_attempt = catalog.load_run_attempt(
        fresh.attempt_id
    )

    assert fresh_attempt is not None
    assert (
        fresh_attempt.state
        is RunAttemptState.SUCCEEDED
    )
    assert (
        fresh_attempt.experiment_spec_id
        == source_attempt.experiment_spec_id
    )



def test_m94q_negative_cash_result_is_not_reused_and_fresh_execution_remains_available(
    tmp_path,
):
    database = tmp_path / "research.sqlite3"

    attempt_ids = iter(
        (
            "attempt-m94q-negative-cash-source",
            "attempt-m94q-negative-cash-fresh",
        )
    )
    evidence_ids = iter(
        (
            "evidence-m94q-negative-cash-source",
            "evidence-m94q-negative-cash-fresh",
        )
    )

    catalog = SQLiteResearchCatalogStore(
        database,
        attempt_id_factory=lambda: next(attempt_ids),
    )
    evidence_store = SQLiteResearchEvidenceStore(
        database
    )
    artifact_store = ContentAddressedResearchArtifactStore(
        tmp_path / "artifacts"
    )

    execution_calls = []

    def execute(**kwargs):
        execution_calls.append(kwargs)
        return BacktestResult(
            trades=[],
            bar_records=[
                BarRecord(
                    timestamp=START,
                    open=100.0,
                    high=101.0,
                    low=99.0,
                    close=100.0,
                    volume=1000.0,
                    strategy="m94q-reuse-fixture",
                    state=None,
                    signal=None,
                    execution_event=None,
                    execution_price=None,
                    execution_quantity=None,
                    decision_snapshot={},
                    equity=100_000.0,
                    cash=100_000.0,
                    position_size=0.0,
                    drawdown=0.0,
                ),
            ],
            session_id=(
                "runtime-m94q-"
                + str(len(execution_calls))
            ),
        )

    service = BacktestResearchOrchestrator(
        catalog_store=catalog,
        evidence_store=evidence_store,
        artifact_store=artifact_store,
        software_identity_provider=StaticIdentityProvider(
            SoftwareIdentity(
                REVISION,
                True,
            )
        ),
        evidence_id_factory=lambda: next(
            evidence_ids
        ),
        clock=lambda: CREATED_AT,
        retrieve_candles=lambda **kwargs: candles(),
        execute_candles=execute,
    )

    source = service.execute(
        historical_source=object(),
        strategy=create_strategy(config()),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
    )

    source_attempt = catalog.load_run_attempt(
        source.attempt_id
    )

    assert source_attempt is not None
    assert source_attempt.evidence_id is not None
    assert source_attempt.result_artifact_id is not None

    source_result_id = (
        source_attempt.result_artifact_id
    )

    payload = decode_canonical_bytes(
        artifact_store.load_bytes(
            source_result_id
        ),
        schema=BACKTEST_RESULT_SCHEMA,
    )

    record = payload["bar_records"][0]
    record["position_size"] = 2000.0
    record["cash"] = -100_000.0

    assert record["equity"] == (
        record["cash"]
        + record["position_size"] * record["close"]
    )

    negative_cash_bytes = canonical_bytes(
        payload,
        schema=BACKTEST_RESULT_SCHEMA,
    )

    negative_cash_artifact = (
        artifact_store.persist_bytes(
            negative_cash_bytes,
            artifact_kind=(
                ResearchArtifactKind.BACKTEST_RESULT
            ),
            schema_id=BACKTEST_RESULT_SCHEMA,
            created_at=CREATED_AT,
        )
    )

    catalog.save_artifact(
        negative_cash_artifact
    )

    old_reference = research_artifact_reference(
        source_result_id
    )
    new_reference = research_artifact_reference(
        negative_cash_artifact.artifact_id
    )

    with sqlite3.connect(database) as connection:
        row = connection.execute(
            """
            SELECT artifact_references
            FROM research_evidence
            WHERE evidence_id = ?
            """,
            (source_attempt.evidence_id,),
        ).fetchone()

        assert row is not None

        references = json.loads(
            row[0]
        )

        references = [
            (
                new_reference
                if reference == old_reference
                else reference
            )
            for reference in references
        ]

        connection.execute(
            """
            UPDATE run_attempts
            SET result_artifact_id = ?
            WHERE attempt_id = ?
            """,
            (
                negative_cash_artifact.artifact_id,
                source_attempt.attempt_id,
            ),
        )

        connection.execute(
            """
            UPDATE research_evidence
            SET
                result_fingerprint = ?,
                artifact_references = ?
            WHERE evidence_id = ?
            """,
            (
                negative_cash_artifact.artifact_id,
                json.dumps(
                    references,
                    separators=(",", ":"),
                ),
                source_attempt.evidence_id,
            ),
        )

        connection.commit()

    before_reuse_lookup = row_count(
        database,
        "run_attempts",
    )

    assert before_reuse_lookup == 1

    reusable = service.find_exact_reusable_execution(
        source_attempt.experiment_spec_id
    )

    assert reusable is None

    assert (
        row_count(
            database,
            "run_attempts",
        )
        == before_reuse_lookup
    )

    fresh = service.execute(
        historical_source=object(),
        strategy=create_strategy(config()),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
    )

    assert fresh.attempt_id == "attempt-m94q-negative-cash-fresh"
    assert len(execution_calls) == 2

    assert (
        row_count(
            database,
            "run_attempts",
        )
        == 2
    )

    fresh_attempt = catalog.load_run_attempt(
        fresh.attempt_id
    )

    assert fresh_attempt is not None
    assert (
        fresh_attempt.state
        is RunAttemptState.SUCCEEDED
    )
    assert (
        fresh_attempt.experiment_spec_id
        == source_attempt.experiment_spec_id
    )


@pytest.mark.parametrize("case", ["opening_1e-8", "trade_fee", "entry_fee", "foreign_symbol", "negative_cash"])
@pytest.mark.parametrize("exact", [True, False])
def test_m94q_stabilization_standalone_validates_before_acceptance(tmp_path, case, exact):
    from core.config.execution_config import ExecutionConfig
    from tests.research.test_m94d_claimed_research_job_executor import _stabilization_result

    service, catalog, evidence, database = make_orchestrator(
        tmp_path, SoftwareIdentity(REVISION, exact), retrieve=lambda **kwargs: candles(),
        execute=lambda **kwargs: _stabilization_result(case),
    )
    # The fixture symbol is ABC; match its manifest except for the explicit foreign-symbol case.
    dataset = DatasetContext(symbol="ABC", timeframe="15m", timezone="Asia/Kolkata")
    settings = config()
    settings.symbol = "ABC"
    with pytest.raises(ValueError):
        service.execute(historical_source=object(), strategy=create_strategy(settings), config=settings,
                        runtime_context=RuntimeContext(execution_config=ExecutionConfig(brokerage_enabled=False)), dataset_context=dataset)
    assert evidence.load("evidence-001").status is ResearchEvidenceStatus.FAILED
    assert row_count(database, "run_attempts") == int(exact)
    if exact:
        attempt = catalog.load_run_attempt("attempt-001")
        assert attempt.state is RunAttemptState.FAILED
        assert attempt.result_artifact_id is None


@pytest.mark.parametrize("scenario", ["open", "losing", "zero_trade", "samebar", "slippage", "brokerage"])
def test_m94q_stabilization_real_engine_fresh_and_reusable(tmp_path, scenario):
    from core.config.execution_config import ExecutionConfig
    from core.runtime.backtest_runtime import execute_backtest_candles
    from core.strategies.signal import SignalType
    from tests.backtest.test_m4_7_backtest_validity_integration import IntegrationStrategy, candle

    signals = {} if scenario == "zero_trade" else {1: SignalType.BUY}
    strategy = IntegrationStrategy(signals, rejection_midpoint=None, scenario=scenario)
    protective = scenario == "samebar"
    values = [
        candle(0, open_price=100., high=101., low=99., close=100.),
        candle(1, open_price=100., high=111., low=97. if protective else 99., close=99. if protective else 110.),
    ]
    settings = config()
    if scenario == "losing":
        strategy = IntegrationStrategy(
            {1: SignalType.BUY, 3: SignalType.SELL},
            rejection_midpoint=None, scenario=scenario,
        )
        values = [
            candle(0, open_price=100., high=101., low=99., close=100.),
            candle(1, open_price=100., high=102., low=99., close=101.),
            candle(2, open_price=101., high=102., low=99., close=100.),
            candle(3, open_price=99., high=100., low=98.5, close=99.),
        ]
        settings.end = START + timedelta(hours=1)
    service, catalog, _, _ = make_orchestrator(
        tmp_path, SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: values, execute=execute_backtest_candles,
    )
    execution = service.execute(
        historical_source=object(), strategy=strategy, config=settings,
        runtime_context=RuntimeContext(execution_config=ExecutionConfig(
            brokerage_enabled=scenario == "brokerage", slippage_enabled=scenario == "slippage",
        )), dataset_context=context(),
    )
    assert execution.evidence_status is ResearchEvidenceStatus.ACCEPTED
    if scenario == "zero_trade":
        assert execution.result.trades == []
        assert execution.result.bar_records[-1].position_size == 0
    elif protective or scenario == "losing":
        assert len(execution.result.trades) == 1
        assert execution.result.trades[0].pnl < 0
        if protective:
            assert execution.result.trades[0].entry_time == execution.result.trades[0].exit_time
        else:
            assert execution.result.trades[0].entry_time < execution.result.trades[0].exit_time
    else:
        assert execution.result.bar_records[-1].position_size > 0
        assert execution.result.bar_records[-1].execution_event == "BUY"
    attempt = catalog.load_run_attempt(execution.attempt_id)
    assert service.find_exact_reusable_execution(attempt.experiment_spec_id) is not None


def test_m94q_stabilization_persists_validated_private_result(tmp_path, monkeypatch):
    from tests.research.test_m94d_claimed_research_job_executor import _stabilization_result
    from core.research.reproducibility import decode_stable_backtest_result_bytes

    original = _stabilization_result("valid")
    # Match the ordinary fixture manifest's execution symbol.
    original.trades[0].symbol = "RELIANCE"
    service, catalog, _, _ = make_orchestrator(
        tmp_path, SoftwareIdentity(REVISION, True),
        retrieve=lambda **kwargs: candles(), execute=lambda **kwargs: original,
    )
    persist = service.artifact_store.persist_backtest_result

    def mutate_caller_result(result, **kwargs):
        original.trades[0].symbol = "FOREIGN"
        original.bar_records[1].cash = -1.
        return persist(result, **kwargs)

    monkeypatch.setattr(service.artifact_store, "persist_backtest_result", mutate_caller_result)
    execution = service.execute(historical_source=object(), strategy=create_strategy(config()), config=config(),
                                runtime_context=RuntimeContext(), dataset_context=context())
    attempt = catalog.load_run_attempt(execution.attempt_id)
    persisted = decode_stable_backtest_result_bytes(service.artifact_store.load_bytes(attempt.result_artifact_id))
    assert persisted["trades"][0]["symbol"] == "RELIANCE"
    assert persisted["bar_records"][1]["cash"] > 0
    assert execution.result is not original

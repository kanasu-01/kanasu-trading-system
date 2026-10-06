from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

import core.research.backtest_research_orchestrator as orchestration
from core.backtest.backtest_result import BacktestResult
from core.config.backtest_config import BacktestConfig
from core.entities.candle import Candle
from core.research.backtest_research_orchestrator import (
    BacktestResearchOrchestrator,
    PreparedBacktestResearchSpecification,
)
from core.research.models.research_catalog import (
    RunAttemptState,
)
from core.research.models.research_evidence import (
    ResearchEvidenceStatus,
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

    execution = service.execute_prepared(
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
        service.execute_prepared(
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
        service.execute_prepared(
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

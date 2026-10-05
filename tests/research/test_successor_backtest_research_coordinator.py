from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

import core.research.backtest_research_orchestrator as orchestration
from core.backtest.backtest_result import BacktestResult
from core.config.backtest_config import BacktestConfig
from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.research.backtest_research_orchestrator import (
    AuthoritativeResearchStateError,
    BacktestResearchOrchestrator,
)
from core.research.models.dataset import (
    DatasetIdentityV2,
    PriceAdjustmentBasis,
    ProviderBindingProvenance,
)
from core.research.models.research_catalog import (
    ResearchArtifactKind,
    RunAttemptState,
)
from core.research.models.research_evidence import (
    ResearchEvidenceStatus,
)
from core.research.reproducibility import (
    dataset_fingerprint,
)
from core.research.research_artifact_store import (
    ContentAddressedResearchArtifactStore,
)
from core.research.software_identity import (
    SoftwareIdentity,
)
from core.research.sqlite_research_catalog_store import (
    SQLiteResearchCatalogStore,
)
from core.research.sqlite_research_evidence_store import (
    SQLiteResearchEvidenceStore,
)
from core.research.successor_backtest_research_coordinator import (
    SuccessorBacktestResearchCoordinator,
)
from core.research.successor_historical_retrieval import (
    SuccessorHistoricalRetrievalResult,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.strategy_factory import create_strategy


INDIA = timezone(
    timedelta(hours=5, minutes=30)
)

START = datetime(
    2026,
    1,
    5,
    9,
    15,
    tzinfo=INDIA,
)

END = START + timedelta(minutes=45)

CREATED_AT = datetime(
    2026,
    9,
    29,
    17,
    30,
    tzinfo=timezone.utc,
)

REVISION = (
    "de64101eb7d4ed653f5e8eaabd3ec125e7f81d32"
)

INSTRUMENT_ID = "NSE-EQ-ABC"


class StaticIdentityProvider:
    def resolve(self):
        return SoftwareIdentity(
            REVISION,
            True,
        )


class StaticSuccessorRetrieval:
    def __init__(
        self,
        result=None,
        error=None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    def retrieve(
        self,
        context,
        request,
        *,
        instrument_id,
        provider,
        price_adjustment_basis,
    ):
        self.calls.append(
            {
                "context": context,
                "request": request,
                "instrument_id": instrument_id,
                "provider": provider,
                "price_adjustment_basis": (
                    price_adjustment_basis
                ),
            }
        )

        if self.error is not None:
            raise self.error

        return self.result


def config():
    return BacktestConfig(
        symbol="ABC",
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
        symbol="ABC",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )


def candles():
    values = (
        100.0,
        101.0,
        102.0,
    )

    return [
        Candle(
            timestamp=(
                START
                + timedelta(
                    minutes=15 * index
                )
            ),
            open=value,
            high=value + 1.0,
            low=value - 1.0,
            close=value,
            volume=1000.0,
        )
        for index, value in enumerate(values)
    ]


def successor_result():
    request = TimeRange(
        START,
        END,
    )

    return SuccessorHistoricalRetrievalResult(
        candles=tuple(candles()),
        source="provider:angelone",
        binding_segments=(
            ProviderBindingProvenance(
                binding_id="angelone-abc-v1",
                provider="angelone",
                applied_range=request,
            ),
        ),
        coverage=(request,),
        stream_usages=(),
    )


def row_count(path, table):
    with sqlite3.connect(path) as connection:
        return connection.execute(
            f"SELECT COUNT(*) FROM {table}"
        ).fetchone()[0]


def make_orchestrator(
    tmp_path,
    *,
    execute,
    evidence_id,
):
    database = (
        tmp_path / "research.sqlite3"
    )

    catalog = SQLiteResearchCatalogStore(
        database,
        attempt_id_factory=(
            lambda: "attempt-001"
        ),
    )

    evidence = SQLiteResearchEvidenceStore(
        database
    )

    artifacts = (
        ContentAddressedResearchArtifactStore(
            tmp_path / "artifacts"
        )
    )

    def legacy_retrieve_must_not_run(
        **kwargs,
    ):
        pytest.fail(
            "legacy retrieval must not run "
            "for successor coordinator"
        )

    orchestrator = BacktestResearchOrchestrator(
        catalog_store=catalog,
        evidence_store=evidence,
        artifact_store=artifacts,
        software_identity_provider=(
            StaticIdentityProvider()
        ),
        evidence_id_factory=(
            lambda: evidence_id
        ),
        clock=lambda: CREATED_AT,
        retrieve_candles=(
            legacy_retrieve_must_not_run
        ),
        execute_candles=execute,
    )

    return (
        orchestrator,
        catalog,
        evidence,
        artifacts,
        database,
    )


def dataset_artifacts(
    evidence_record,
    catalog,
):
    artifacts = []

    for reference in (
        evidence_record.artifact_references
    ):
        artifact_id = reference.removeprefix(
            "artifact:"
        )

        artifact = catalog.load_artifact(
            artifact_id
        )

        if (
            artifact is not None
            and artifact.artifact_kind
            is ResearchArtifactKind.DATASET_REFERENCE
        ):
            artifacts.append(artifact)

    return artifacts


def test_successor_execution_attaches_dataset_reference_and_uses_exact_candles(
    tmp_path,
    monkeypatch,
):
    captured = {}

    def execute(**kwargs):
        captured["executed"] = kwargs["candles"]

        return BacktestResult(
            trades=[],
            bar_records=[],
            session_id="runtime-successor",
        )

    (
        orchestrator,
        catalog,
        evidence_store,
        artifact_store,
        _,
    ) = make_orchestrator(
        tmp_path,
        execute=execute,
        evidence_id="evidence-successor",
    )

    retrieval_service = StaticSuccessorRetrieval(
        result=successor_result()
    )

    coordinator = (
        SuccessorBacktestResearchCoordinator(
            retrieval_service=(
                retrieval_service
            ),
            orchestrator=orchestrator,
            clock=lambda: CREATED_AT,
        )
    )

    original_fingerprint = (
        orchestration.dataset_fingerprint
    )

    def fingerprint(
        context_value,
        request,
        values,
    ):
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

    execution = coordinator.execute(
        strategy=create_strategy(
            config()
        ),
        config=config(),
        runtime_context=RuntimeContext(
            risk_per_trade_pct=1.0
        ),
        dataset_context=context(),
        instrument_id=INSTRUMENT_ID,
        provider="angelone",
        price_adjustment_basis=(
            PriceAdjustmentBasis.UNKNOWN
        ),
    )

    assert (
        captured["fingerprinted"]
        is captured["executed"]
    )

    assert captured["executed"] == candles()

    assert execution.attempt_id == (
        "attempt-001"
    )

    assert (
        execution.evidence_status
        is ResearchEvidenceStatus.ACCEPTED
    )

    evidence = evidence_store.load(
        "evidence-successor"
    )

    assert evidence is not None

    assert len(
        evidence.artifact_references
    ) == 3

    references = dataset_artifacts(
        evidence,
        catalog,
    )

    assert len(references) == 1

    dataset_artifact = references[0]

    payload = artifact_store.load_bytes(
        dataset_artifact.artifact_id
    )

    assert b"angelone-abc-v1" in payload
    assert INSTRUMENT_ID.encode() in payload
    assert (
        b"price adjustment basis is unknown"
        in payload
    )

    expected_identity = DatasetIdentityV2(
        instrument_id=INSTRUMENT_ID,
        requested_range=TimeRange(
            START,
            END,
        ),
        timeframe="15m",
        timezone="Asia/Kolkata",
        price_adjustment_basis=(
            PriceAdjustmentBasis.UNKNOWN
        ),
        candles=captured["executed"],
    )

    assert (
        expected_identity.dataset_id.encode()
        in payload
    )

    expected_v1 = dataset_fingerprint(
        context(),
        TimeRange(
            START,
            END,
        ),
        captured["executed"],
    )

    assert (
        evidence.dataset_fingerprint
        == expected_v1
    )

    assert (
        evidence.dataset_fingerprint
        != expected_identity.dataset_id
    )


def test_successor_retrieval_failure_keeps_existing_incomplete_evidence_semantics(
    tmp_path,
):
    (
        orchestrator,
        _,
        evidence_store,
        _,
        database,
    ) = make_orchestrator(
        tmp_path,
        execute=lambda **kwargs: pytest.fail(
            "execution must not run"
        ),
        evidence_id="evidence-retrieval-failed",
    )

    coordinator = (
        SuccessorBacktestResearchCoordinator(
            retrieval_service=(
                StaticSuccessorRetrieval(
                    error=RuntimeError(
                        "successor history unavailable"
                    )
                )
            ),
            orchestrator=orchestrator,
            clock=lambda: CREATED_AT,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="successor history unavailable",
    ):
        coordinator.execute(
            strategy=create_strategy(
                config()
            ),
            config=config(),
            runtime_context=RuntimeContext(
                risk_per_trade_pct=1.0
            ),
            dataset_context=context(),
            instrument_id=INSTRUMENT_ID,
            provider="angelone",
            price_adjustment_basis=(
                PriceAdjustmentBasis.UNKNOWN
            ),
        )

    evidence = evidence_store.load(
        "evidence-retrieval-failed"
    )

    assert evidence is not None

    assert (
        evidence.status
        is ResearchEvidenceStatus.INCOMPLETE
    )

    assert evidence.summary == (
        "historical_data_retrieval_failed: "
        "successor history unavailable"
    )

    assert (
        evidence.artifact_references
        == ()
    )

    assert (
        row_count(
            database,
            "experiment_specs",
        )
        == 0
    )

    assert (
        row_count(
            database,
            "run_attempts",
        )
        == 0
    )




def test_dataset_reference_persistence_failure_propagates_authoritative_state_failure(
    tmp_path,
    monkeypatch,
):
    (
        orchestrator,
        _,
        evidence_store,
        artifact_store,
        database,
    ) = make_orchestrator(
        tmp_path,
        execute=lambda **kwargs: pytest.fail(
            "execution must not run"
        ),
        evidence_id=(
            "evidence-reference-persist-failed"
        ),
    )

    retrieval_service = StaticSuccessorRetrieval(
        result=successor_result()
    )

    def fail_persist(
        reference,
        *,
        created_at,
    ):
        raise OSError(
            "dataset reference persistence failed"
        )

    monkeypatch.setattr(
        artifact_store,
        "persist_dataset_reference",
        fail_persist,
    )

    coordinator = (
        SuccessorBacktestResearchCoordinator(
            retrieval_service=(
                retrieval_service
            ),
            orchestrator=orchestrator,
            clock=lambda: CREATED_AT,
        )
    )

    with pytest.raises(
        AuthoritativeResearchStateError,
        match=(
            "dataset reference persistence failed"
        ),
    ):
        coordinator.execute(
            strategy=create_strategy(
                config()
            ),
            config=config(),
            runtime_context=RuntimeContext(
                risk_per_trade_pct=1.0
            ),
            dataset_context=context(),
            instrument_id=INSTRUMENT_ID,
            provider="angelone",
            price_adjustment_basis=(
                PriceAdjustmentBasis.UNKNOWN
            ),
        )

    assert len(
        retrieval_service.calls
    ) == 1

    evidence = evidence_store.load(
        "evidence-reference-persist-failed"
    )

    assert evidence is None

    assert (
        row_count(
            database,
            "research_artifacts",
        )
        == 0
    )

    assert (
        row_count(
            database,
            "experiment_specs",
        )
        == 0
    )

    assert (
        row_count(
            database,
            "run_attempts",
        )
        == 0
    )


def test_dataset_reference_catalog_failure_propagates_authoritative_state_failure(
    tmp_path,
    monkeypatch,
):
    (
        orchestrator,
        catalog,
        evidence_store,
        artifact_store,
        database,
    ) = make_orchestrator(
        tmp_path,
        execute=lambda **kwargs: pytest.fail(
            "execution must not run"
        ),
        evidence_id=(
            "evidence-reference-catalog-failed"
        ),
    )

    retrieval_service = StaticSuccessorRetrieval(
        result=successor_result()
    )

    captured = {}

    def fail_catalog_registration(
        artifact,
    ):
        assert (
            artifact.artifact_kind
            is ResearchArtifactKind.DATASET_REFERENCE
        )

        captured["artifact"] = artifact

        raise ValueError(
            "dataset reference catalog registration failed"
        )

    monkeypatch.setattr(
        catalog,
        "save_artifact",
        fail_catalog_registration,
    )

    coordinator = (
        SuccessorBacktestResearchCoordinator(
            retrieval_service=(
                retrieval_service
            ),
            orchestrator=orchestrator,
            clock=lambda: CREATED_AT,
        )
    )

    with pytest.raises(
        AuthoritativeResearchStateError,
        match=(
            "dataset reference catalog registration failed"
        ),
    ):
        coordinator.execute(
            strategy=create_strategy(
                config()
            ),
            config=config(),
            runtime_context=RuntimeContext(
                risk_per_trade_pct=1.0
            ),
            dataset_context=context(),
            instrument_id=INSTRUMENT_ID,
            provider="angelone",
            price_adjustment_basis=(
                PriceAdjustmentBasis.UNKNOWN
            ),
        )

    assert len(
        retrieval_service.calls
    ) == 1

    evidence = evidence_store.load(
        "evidence-reference-catalog-failed"
    )

    assert evidence is None

    assert (
        row_count(
            database,
            "experiment_specs",
        )
        == 0
    )

    assert (
        row_count(
            database,
            "run_attempts",
        )
        == 0
    )

def test_execution_failure_keeps_dataset_reference_in_failed_evidence(
    tmp_path,
):
    def fail_execute(**kwargs):
        raise RuntimeError(
            "successor engine failed"
        )

    (
        orchestrator,
        catalog,
        evidence_store,
        artifact_store,
        _,
    ) = make_orchestrator(
        tmp_path,
        execute=fail_execute,
        evidence_id="evidence-execution-failed",
    )

    coordinator = (
        SuccessorBacktestResearchCoordinator(
            retrieval_service=(
                StaticSuccessorRetrieval(
                    result=successor_result()
                )
            ),
            orchestrator=orchestrator,
            clock=lambda: CREATED_AT,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="successor engine failed",
    ):
        coordinator.execute(
            strategy=create_strategy(
                config()
            ),
            config=config(),
            runtime_context=RuntimeContext(
                risk_per_trade_pct=1.0
            ),
            dataset_context=context(),
            instrument_id=INSTRUMENT_ID,
            provider="angelone",
            price_adjustment_basis=(
                PriceAdjustmentBasis.UNKNOWN
            ),
        )

    evidence = evidence_store.load(
        "evidence-execution-failed"
    )

    assert evidence is not None

    assert (
        evidence.status
        is ResearchEvidenceStatus.FAILED
    )

    assert len(
        evidence.artifact_references
    ) == 2

    references = dataset_artifacts(
        evidence,
        catalog,
    )

    assert len(references) == 1

    assert artifact_store.load_bytes(
        references[0].artifact_id
    )

    attempt = catalog.load_run_attempt(
        "attempt-001"
    )

    assert attempt is not None

    assert (
        attempt.state
        is RunAttemptState.FAILED
    )


def test_legacy_orchestrator_execution_still_uses_original_retrieval_path(
    tmp_path,
):
    values = candles()

    database = (
        tmp_path / "legacy-research.sqlite3"
    )

    catalog = SQLiteResearchCatalogStore(
        database,
        attempt_id_factory=(
            lambda: "attempt-legacy"
        ),
    )

    evidence_store = (
        SQLiteResearchEvidenceStore(
            database
        )
    )

    artifacts = (
        ContentAddressedResearchArtifactStore(
            tmp_path / "legacy-artifacts"
        )
    )

    captured = {
        "retrieval_count": 0,
    }

    def retrieve(**kwargs):
        captured["retrieval_count"] += 1
        return values

    def execute(**kwargs):
        captured["executed"] = kwargs[
            "candles"
        ]

        return BacktestResult(
            trades=[],
            bar_records=[],
            session_id="runtime-legacy",
        )

    orchestrator = BacktestResearchOrchestrator(
        catalog_store=catalog,
        evidence_store=evidence_store,
        artifact_store=artifacts,
        software_identity_provider=(
            StaticIdentityProvider()
        ),
        evidence_id_factory=(
            lambda: "evidence-legacy"
        ),
        clock=lambda: CREATED_AT,
        retrieve_candles=retrieve,
        execute_candles=execute,
    )

    execution = orchestrator.execute(
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

    assert captured["retrieval_count"] == 1
    assert captured["executed"] is not values
    assert captured["executed"] == values

    evidence = evidence_store.load(
        execution.evidence_id
    )

    assert evidence is not None

    assert len(
        evidence.artifact_references
    ) == 2

    assert dataset_artifacts(
        evidence,
        catalog,
    ) == []

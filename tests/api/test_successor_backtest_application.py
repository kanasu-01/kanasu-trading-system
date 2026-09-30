from datetime import datetime, timedelta, timezone

import pytest

import api.backtest_application as application
from api.backtest_application import (
    SuccessorBacktestApplicationContext,
)
from api.models.backtest_models import (
    BacktestRunRequest,
)
from core.backtest.backtest_result import (
    BacktestResult,
)
from core.config.app_config import AppConfig
from core.entities.candle import Candle
from core.market_data.historical_coverage import (
    TimeRange,
)
from core.research.models.dataset import (
    PriceAdjustmentBasis,
    ProviderBindingProvenance,
)
from core.research.models.research_catalog import (
    ResearchArtifactKind,
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
from core.research.successor_historical_retrieval import (
    SuccessorHistoricalRetrievalResult,
)


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

REVISION = (
    "488cb285ea9d431f8624e3da801a305825a92b4e"
)

INSTRUMENT_ID = (
    "instrument:test:nse:eq:reliance"
)


class StaticIdentityProvider:
    def resolve(self):
        return SoftwareIdentity(
            repository_revision=REVISION,
            worktree_clean=True,
        )


class StaticSuccessorRetrieval:
    def __init__(
        self,
        result=None,
    ):
        self.result = result
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

        return self.result


def config_for(tmp_path):
    return AppConfig(
        risk_per_trade_pct=1.0,
        research_database_path=str(
            tmp_path / "research.sqlite3"
        ),
        research_artifact_root=str(
            tmp_path / "research_artifacts"
        ),
    )


def request():
    return BacktestRunRequest(
        symbol="RELIANCE",
        timeframe="15m",
        strategy_id="sma_crossover",
        start=START,
        end=END,
        timezone="Asia/Kolkata",
        initial_capital=100000,
        strategy_params={
            "fast_period": 1,
            "slow_period": 2,
        },
    )


def candles():
    values = (
        100.0,
        101.0,
        102.0,
    )

    return tuple(
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
    )


def successor_result():
    requested = TimeRange(
        START,
        END,
    )

    return SuccessorHistoricalRetrievalResult(
        candles=candles(),
        source="provider:angelone",
        binding_segments=(
            ProviderBindingProvenance(
                binding_id=(
                    "angelone-test-binding"
                ),
                provider="angelone",
                applied_range=requested,
            ),
        ),
        coverage=(requested,),
        stream_usages=(),
    )


def successor_context(
    retrieval_service,
    *,
    request_symbol="RELIANCE",
):
    return SuccessorBacktestApplicationContext(
        request_symbol=request_symbol,
        instrument_id=INSTRUMENT_ID,
        provider="angelone",
        price_adjustment_basis=(
            PriceAdjustmentBasis.UNKNOWN
        ),
        retrieval_service=(
            retrieval_service
        ),
    )


def dataset_reference_artifacts(
    evidence,
    catalog,
):
    found = []

    for reference in evidence.artifact_references:
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
            found.append(artifact)

    return found


def test_opt_in_successor_path_attaches_dataset_reference_without_legacy_source(
    tmp_path,
    monkeypatch,
):
    retrieval = StaticSuccessorRetrieval(
        successor_result()
    )

    captured = {}

    def legacy_source_must_not_be_created(
        _config,
    ):
        pytest.fail(
            "legacy source must not be created "
            "for explicit successor context"
        )

    def execute(**kwargs):
        captured["candles"] = kwargs[
            "candles"
        ]

        return BacktestResult(
            trades=[],
            bar_records=[],
            session_id="successor-app",
        )

    monkeypatch.setattr(
        application,
        "create_historical_source",
        legacy_source_must_not_be_created,
    )

    monkeypatch.setattr(
        application,
        "execute_backtest_candles",
        execute,
    )

    app_config = config_for(
        tmp_path
    )

    response = application.execute_backtest_request(
        request(),
        app_config=app_config,
        software_identity_provider=(
            StaticIdentityProvider()
        ),
        successor_context=(
            successor_context(
                retrieval
            )
        ),
    )

    assert response.run_id == (
        "successor-app"
    )

    assert response.evidence_status == (
        "ACCEPTED"
    )

    assert len(retrieval.calls) == 1

    call = retrieval.calls[0]

    assert call["instrument_id"] == (
        INSTRUMENT_ID
    )

    assert call["provider"] == (
        "angelone"
    )

    assert (
        call["price_adjustment_basis"]
        is PriceAdjustmentBasis.UNKNOWN
    )

    assert tuple(
        captured["candles"]
    ) == candles()

    evidence_store = (
        SQLiteResearchEvidenceStore(
            app_config.research_database_path
        )
    )

    evidence = evidence_store.load(
        response.evidence_id
    )

    assert evidence is not None

    assert len(
        evidence.artifact_references
    ) == 3

    catalog = SQLiteResearchCatalogStore(
        app_config.research_database_path
    )

    references = (
        dataset_reference_artifacts(
            evidence,
            catalog,
        )
    )

    assert len(references) == 1

    artifact_path = (
        tmp_path
        / "research_artifacts"
        / references[0].relative_path
    )

    payload = artifact_path.read_bytes()

    assert INSTRUMENT_ID.encode() in payload
    assert b"angelone-test-binding" in payload
    assert (
        b"price adjustment basis is unknown"
        in payload
    )


def test_default_application_path_remains_legacy_when_successor_context_absent(
    tmp_path,
    monkeypatch,
):
    source = object()
    values = list(
        candles()
    )

    captured = {
        "source_creations": 0,
        "retrievals": 0,
    }

    def create_source(_config):
        captured[
            "source_creations"
        ] += 1

        return source

    def retrieve(**kwargs):
        captured["retrievals"] += 1

        assert (
            kwargs["historical_source"]
            is source
        )

        return values

    class SuccessorMustNotBeCreated:
        def __init__(self, **kwargs):
            pytest.fail(
                "successor coordinator must not "
                "be created by default"
            )

    monkeypatch.setattr(
        application,
        "create_historical_source",
        create_source,
    )

    monkeypatch.setattr(
        application,
        "retrieve_backtest_candles",
        retrieve,
    )

    monkeypatch.setattr(
        application,
        "execute_backtest_candles",
        lambda **kwargs: BacktestResult(
            trades=[],
            bar_records=[],
            session_id="legacy-app",
        ),
    )

    monkeypatch.setattr(
        application,
        "SuccessorBacktestResearchCoordinator",
        SuccessorMustNotBeCreated,
    )

    response = application.execute_backtest_request(
        request(),
        app_config=config_for(tmp_path),
        software_identity_provider=(
            StaticIdentityProvider()
        ),
    )

    assert response.run_id == "legacy-app"

    assert (
        captured["source_creations"]
        == 1
    )

    assert captured["retrievals"] == 1


def test_successor_context_rejects_ambiguous_legacy_source(
    tmp_path,
):
    retrieval = StaticSuccessorRetrieval(
        successor_result()
    )

    with pytest.raises(
        ValueError,
        match=(
            "historical_source and "
            "successor_context"
        ),
    ):
        application.execute_backtest_request(
            request(),
            app_config=config_for(
                tmp_path
            ),
            historical_source=object(),
            software_identity_provider=(
                StaticIdentityProvider()
            ),
            successor_context=(
                successor_context(
                    retrieval
                )
            ),
        )

    assert retrieval.calls == []


def test_successor_context_rejects_request_symbol_mismatch(
    tmp_path,
):
    retrieval = StaticSuccessorRetrieval(
        successor_result()
    )

    with pytest.raises(
        ValueError,
        match="symbol does not match",
    ):
        application.execute_backtest_request(
            request(),
            app_config=config_for(
                tmp_path
            ),
            software_identity_provider=(
                StaticIdentityProvider()
            ),
            successor_context=(
                successor_context(
                    retrieval,
                    request_symbol="OTHER",
                )
            ),
        )

    assert retrieval.calls == []

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import sqlite3
from uuid import UUID

import pytest

import core.backtest.backtest_engine as backtest_engine_module
from core.backtest.backtest_engine import BacktestEngine
from core.backtest.backtest_result import BacktestResult
from core.config.backtest_config import BacktestConfig
from core.config.execution_config import ExecutionConfig
from core.config.historical_source_policy import HistoricalSourcePolicy
from core.entities.candle import Candle
from core.entities.candle_series import CandleSeries
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_retrieval import HistoricalFetchResult
from core.market_data.historical_source import HistoricalSource
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.research.models.research_evidence import (
    ResearchEvidence,
    ResearchEvidenceStatus,
)
from core.research.reproducibility import (
    backtest_configuration_fingerprint,
    dataset_fingerprint,
    stable_backtest_result_fingerprint,
)
from core.research.sqlite_research_evidence_store import (
    SQLiteResearchEvidenceStore,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import SignalType


INDIA = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
START = datetime(2026, 4, 6, 9, 15, 0, 123456, tzinfo=INDIA)
REQUEST = TimeRange(START, START + timedelta(minutes=90))
CONTEXT = DatasetContext("RELIANCE", "15m", "Asia/Kolkata")
EVIDENCE_TIME = datetime(2026, 4, 7, 12, 30, 15, 654321, tzinfo=INDIA)
FRESH_SESSION_ID = UUID("11111111-1111-1111-1111-111111111111")
LOCAL_SESSION_ID = UUID("22222222-2222-2222-2222-222222222222")
EFFECTIVE_RISK_PER_TRADE_PCT = 1.0
EXECUTION_CONFIG = ExecutionConfig(
    slippage_pct=0.0007,
    slippage_enabled=True,
    brokerage_enabled=True,
)


def accepted_candles() -> list[Candle]:
    values = [
        (0, 100.0, 102.0, 99.5, 101.0, 1010.0),
        (15, 102.0, 104.0, 101.0, 103.0, 1125.0),
        (30, 104.0, 108.0, 103.5, 107.0, 1260.0),
        (45, 106.0, 109.0, 105.0, 108.0, 1395.0),
        (60, 108.0, 111.0, 107.0, 110.0, 1540.0),
        (75, 110.0, 114.0, 109.0, 113.0, 1685.0),
    ]
    return [
        Candle(
            timestamp=START + timedelta(minutes=minutes),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
        )
        for (
            minutes,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
        ) in values
    ]


def backtest_config(**changes) -> BacktestConfig:
    values = {
        "symbol": CONTEXT.symbol,
        "timeframe": CONTEXT.timeframe,
        "strategy_name": "reproducibility_integration",
        "start": REQUEST.start,
        "end": REQUEST.end,
        "initial_capital": 100_000.0,
        "enable_replay": False,
        "enable_visualization": False,
        "enable_exports": False,
        "strategy_params": {"scenario": "two_round_trips"},
        "timezone": CONTEXT.timezone,
    }
    values.update(changes)
    return BacktestConfig(**values)


class DeterministicResearchStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="DeterministicResearchStrategy",
            params={"scenario": "two_round_trips"},
        )
        self._bar_number = 0
        self._decision = "NONE"

    def on_new_candle(self, series: CandleSeries) -> SignalType | None:
        self._bar_number = len(series)
        signal = {
            1: SignalType.BUY,
            3: SignalType.SELL,
            4: SignalType.BUY,
            6: SignalType.SELL,
        }.get(self._bar_number)
        self._decision = signal.value if signal is not None else "HOLD"
        return signal

    def reset(self) -> None:
        self._bar_number = 0
        self._decision = "NONE"

    def get_debug_state(self) -> dict:
        return {
            "bar_number": self._bar_number,
            "decision": self._decision,
        }


class RecordingProvider:
    def __init__(self, result: HistoricalFetchResult):
        self.result = result
        self.requests: list[tuple[DatasetContext, TimeRange]] = []

    def fetch(
        self,
        context: DatasetContext,
        request: TimeRange,
    ) -> HistoricalFetchResult:
        self.requests.append((context, request))
        return self.result


class FailingProvider:
    def fetch(self, context: DatasetContext, request: TimeRange):
        raise RuntimeError("deterministic provider failure")


class ProviderFactory:
    def __init__(self, provider=None):
        self.provider = provider
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.provider is None:
            pytest.fail("durable local rerun constructed a provider")
        return self.provider


def run_backtest(
    monkeypatch,
    candles: list[Candle],
    session_id: UUID,
    config: BacktestConfig,
) -> BacktestResult:
    monkeypatch.setattr(
        backtest_engine_module.uuid,
        "uuid4",
        lambda: session_id,
    )
    return BacktestEngine(
        strategy=DeterministicResearchStrategy(),
        initial_capital=config.initial_capital,
        runtime_context=RuntimeContext(execution_config=EXECUTION_CONFIG),
        dataset_context=CONTEXT,
    ).run_stream(candles)


def fingerprints(
    candles: list[Candle],
    config: BacktestConfig,
    result: BacktestResult,
) -> tuple[str, str, str]:
    return (
        dataset_fingerprint(CONTEXT, REQUEST, candles),
        backtest_configuration_fingerprint(
            CONTEXT,
            REQUEST,
            config,
            EXECUTION_CONFIG,
            effective_risk_per_trade_pct=EFFECTIVE_RISK_PER_TRADE_PCT,
        ),
        stable_backtest_result_fingerprint(result),
    )


def accepted_evidence(
    evidence_id: str,
    identity: tuple[str, str, str],
    provenance: dict[str, str],
) -> ResearchEvidence:
    return ResearchEvidence(
        evidence_id=evidence_id,
        created_at=EVIDENCE_TIME,
        status=ResearchEvidenceStatus.ACCEPTED,
        dataset_context=CONTEXT,
        requested_range=REQUEST,
        dataset_fingerprint=identity[0],
        configuration_fingerprint=identity[1],
        result_fingerprint=identity[2],
        provenance=provenance,
        repository_revision="m3.8d-test-revision",
        summary="Deterministic M3.8d reference run",
        artifact_references=("trades.json", "equity.csv"),
    )


def assert_stable_result_parity(
    fresh: BacktestResult,
    local: BacktestResult,
) -> None:
    assert fresh.session_id != local.session_id
    assert fresh.trades == local.trades
    assert fresh.bar_records == local.bar_records
    assert fresh.equity_curve == local.equity_curve
    assert len(fresh.trades) == 2
    execution_records = [
        record
        for record in fresh.bar_records
        if record.execution_event is not None
    ]
    assert [record.execution_event for record in execution_records] == [
        "BUY",
        "SELL",
        "BUY",
        "SELL",
    ]
    assert all(record.execution_price is not None for record in execution_records)
    assert all(
        record.execution_quantity is not None
        for record in execution_records
    )
    assert [record.cash for record in fresh.bar_records] == [
        record.cash for record in local.bar_records
    ]
    assert [record.equity for record in fresh.bar_records] == [
        record.equity for record in local.bar_records
    ]
    assert [record.position_size for record in fresh.bar_records] == [
        record.position_size for record in local.bar_records
    ]
    assert [record.drawdown for record in fresh.bar_records] == [
        record.drawdown for record in local.bar_records
    ]


def table_names(database_path) -> set[str]:
    with sqlite3.connect(database_path) as connection:
        return {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }


@pytest.mark.parametrize(
    "warm_policy",
    [
        pytest.param(HistoricalSourcePolicy.LOCAL_ONLY, id="local-only"),
        pytest.param(HistoricalSourcePolicy.LOCAL_FIRST, id="local-first"),
    ],
)
def test_fresh_and_durable_local_runs_have_matching_reproducibility_identity(
    tmp_path,
    monkeypatch,
    warm_policy,
):
    monkeypatch.chdir(tmp_path)
    historical_path = tmp_path / "historical.sqlite3"
    evidence_path = tmp_path / "research-evidence.sqlite3"
    config = backtest_config()
    provider = RecordingProvider(
        HistoricalFetchResult(
            candles=tuple(accepted_candles()),
            coverage=(REQUEST,),
        )
    )
    fresh_factory = ProviderFactory(provider)

    fresh_candles = HistoricalSource(
        SQLiteCandleStore(historical_path),
        HistoricalSourcePolicy.PROVIDER_BACKED,
        fresh_factory,
    ).retrieve(CONTEXT, REQUEST)
    fresh_result = run_backtest(
        monkeypatch,
        fresh_candles,
        FRESH_SESSION_ID,
        config,
    )
    fresh_identity = fingerprints(fresh_candles, config, fresh_result)
    reference = accepted_evidence(
        "provider-reference",
        fresh_identity,
        {"source_policy": "PROVIDER_BACKED", "provider": "deterministic"},
    )
    SQLiteResearchEvidenceStore(evidence_path).save(reference)

    warm_factory = ProviderFactory()
    local_candles = HistoricalSource(
        SQLiteCandleStore(historical_path),
        warm_policy,
        warm_factory,
    ).retrieve(CONTEXT, REQUEST)
    local_result = run_backtest(
        monkeypatch,
        local_candles,
        LOCAL_SESSION_ID,
        config,
    )
    local_identity = fingerprints(local_candles, config, local_result)
    local_evidence = accepted_evidence(
        "local-rerun",
        local_identity,
        {"source_policy": warm_policy.value, "provider": "none"},
    )
    SQLiteResearchEvidenceStore(evidence_path).save(local_evidence)

    repeat_factory = ProviderFactory()
    repeated_local_candles = HistoricalSource(
        SQLiteCandleStore(historical_path),
        HistoricalSourcePolicy.LOCAL_ONLY,
        repeat_factory,
    ).retrieve(CONTEXT, REQUEST)

    assert provider.requests == [(CONTEXT, REQUEST)]
    assert fresh_factory.calls == 1
    assert warm_factory.calls == 0
    assert repeat_factory.calls == 0
    assert fresh_candles == local_candles == repeated_local_candles
    assert_stable_result_parity(fresh_result, local_result)
    assert fresh_identity == local_identity
    assert fresh_identity[2] == stable_backtest_result_fingerprint(local_result)
    assert reference.provenance != local_evidence.provenance
    assert (
        reference.dataset_fingerprint,
        reference.configuration_fingerprint,
        reference.result_fingerprint,
    ) == (
        local_evidence.dataset_fingerprint,
        local_evidence.configuration_fingerprint,
        local_evidence.result_fingerprint,
    )

    reloaded_reference = SQLiteResearchEvidenceStore(evidence_path).load(
        reference.evidence_id
    )
    reloaded_local = SQLiteResearchEvidenceStore(evidence_path).load(
        local_evidence.evidence_id
    )
    assert reloaded_reference == reference
    assert reloaded_local == local_evidence

    changed_research_config = backtest_config(initial_capital=125_000.0)
    changed_config_fingerprint = backtest_configuration_fingerprint(
        CONTEXT,
        REQUEST,
        changed_research_config,
        EXECUTION_CONFIG,
        effective_risk_per_trade_pct=EFFECTIVE_RISK_PER_TRADE_PCT,
    )
    assert changed_config_fingerprint != fresh_identity[1]

    presentation_only_config = backtest_config(
        enable_replay=True,
        enable_visualization=True,
        enable_exports=True,
    )
    presentation_config_fingerprint = backtest_configuration_fingerprint(
        CONTEXT,
        REQUEST,
        presentation_only_config,
        EXECUTION_CONFIG,
        effective_risk_per_trade_pct=EFFECTIVE_RISK_PER_TRADE_PCT,
    )
    assert presentation_config_fingerprint == fresh_identity[1]

    with pytest.raises(ValueError, match="already exists"):
        SQLiteResearchEvidenceStore(evidence_path).save(
            replace(reference, summary="must not overwrite reference")
        )
    assert SQLiteResearchEvidenceStore(evidence_path).load(
        reference.evidence_id
    ) == reference

    assert historical_path != evidence_path
    assert historical_path.exists()
    assert evidence_path.exists()
    assert "research_evidence" not in table_names(historical_path)
    assert not {"candles", "retrieval_coverage"} & table_names(evidence_path)


def test_provider_failure_creates_no_false_accepted_evidence(
    tmp_path,
):
    historical_path = tmp_path / "historical.sqlite3"
    evidence_path = tmp_path / "research-evidence.sqlite3"
    evidence_store = SQLiteResearchEvidenceStore(evidence_path)
    provider_factory = ProviderFactory(FailingProvider())

    with pytest.raises(RuntimeError, match="deterministic provider failure"):
        HistoricalSource(
            SQLiteCandleStore(historical_path),
            HistoricalSourcePolicy.PROVIDER_BACKED,
            provider_factory,
        ).retrieve(CONTEXT, REQUEST)

    assert provider_factory.calls == 1
    assert SQLiteCandleStore(historical_path).load_coverage(CONTEXT) == []
    assert evidence_store.load("false-accepted") is None

    incomplete = ResearchEvidence(
        evidence_id="incomplete-provider-run",
        created_at=EVIDENCE_TIME,
        status=ResearchEvidenceStatus.INCOMPLETE,
        dataset_context=CONTEXT,
        requested_range=REQUEST,
        provenance={
            "source_policy": "PROVIDER_BACKED",
            "failure": "provider retrieval",
        },
        summary="Provider failed before accepted evidence was available",
        artifact_references=(),
    )
    evidence_store.save(incomplete)

    reloaded = SQLiteResearchEvidenceStore(evidence_path).load(
        incomplete.evidence_id
    )
    assert reloaded == incomplete
    assert reloaded.status is ResearchEvidenceStatus.INCOMPLETE
    assert reloaded.status is not ResearchEvidenceStatus.ACCEPTED

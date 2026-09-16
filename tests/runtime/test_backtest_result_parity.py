from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

import core.backtest.backtest_engine as backtest_engine_module
import core.runtime.backtest_runtime as backtest_runtime_module
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
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy
from core.strategies.signal import SignalType


INDIA = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
START = datetime(2026, 1, 2, 9, 15, tzinfo=INDIA)
REQUEST = TimeRange(START, START + timedelta(minutes=90))
DATASET_CONTEXT = DatasetContext(
    symbol="RELIANCE",
    timeframe="15m",
    timezone="Asia/Kolkata",
)
FRESH_SESSION_ID = UUID("11111111-1111-1111-1111-111111111111")
WARM_SESSION_ID = UUID("22222222-2222-2222-2222-222222222222")


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


def backtest_config() -> BacktestConfig:
    return BacktestConfig(
        symbol=DATASET_CONTEXT.symbol,
        timeframe=DATASET_CONTEXT.timeframe,
        strategy_name="deterministic_parity",
        start=REQUEST.start,
        end=REQUEST.end,
        initial_capital=100_000.0,
        enable_replay=False,
        enable_visualization=False,
        enable_exports=False,
        strategy_params={"scenario": "two_round_trips"},
        timezone=DATASET_CONTEXT.timezone,
    )


def runtime_context() -> RuntimeContext:
    return RuntimeContext(
        execution_config=ExecutionConfig(
            slippage_pct=0.0007,
            slippage_enabled=True,
            brokerage_enabled=True,
        )
    )


class DeterministicParityStrategy(BaseStrategy):
    def __init__(self):
        super().__init__(
            name="DeterministicParity",
            params={"scenario": "two_round_trips"},
        )
        self._bar_number = 0
        self._decision = "NONE"

    def on_new_candle(
        self,
        series: CandleSeries,
    ) -> SignalType | None:
        self._bar_number = len(series)
        signal = {
            1: SignalType.BUY,
            2: SignalType.SELL,
            3: SignalType.BUY,
            5: SignalType.SELL,
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
    def __init__(self, candles: list[Candle]):
        self.result = HistoricalFetchResult(
            candles=tuple(candles),
            coverage=(REQUEST,),
        )
        self.requests: list[tuple[DatasetContext, TimeRange]] = []

    def fetch(
        self,
        context: DatasetContext,
        request: TimeRange,
    ) -> HistoricalFetchResult:
        self.requests.append((context, request))
        return self.result


class ProviderFactory:
    def __init__(self, provider=None):
        self.provider = provider
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.provider is None:
            pytest.fail("warm local Backtest constructed a provider")
        return self.provider


def run_and_capture_result(
    monkeypatch,
    historical_source: HistoricalSource,
    session_id: UUID,
) -> BacktestResult:
    captured: list[BacktestResult] = []
    monkeypatch.setattr(
        backtest_engine_module.uuid,
        "uuid4",
        lambda: session_id,
    )
    monkeypatch.setattr(
        backtest_runtime_module,
        "print_performance_summary",
        captured.append,
    )

    backtest_runtime_module.run_backtest(
        historical_source=historical_source,
        strategy=DeterministicParityStrategy(),
        config=backtest_config(),
        runtime_context=runtime_context(),
        dataset_context=DATASET_CONTEXT,
    )

    assert len(captured) == 1
    return captured[0]


def assert_stable_backtest_parity(
    fresh: BacktestResult,
    warm: BacktestResult,
) -> None:
    assert fresh.session_id == "11111111"
    assert warm.session_id == "22222222"
    assert fresh.session_id != warm.session_id

    assert fresh.trades == warm.trades
    assert fresh.bar_records == warm.bar_records
    assert fresh.equity_curve == warm.equity_curve

    assert len(fresh.trades) == 2
    assert [record.execution_event for record in fresh.bar_records] == [
        None,
        "BUY",
        "SELL",
        "BUY",
        None,
        "SELL",
    ]
    execution_records = [
        record
        for record in fresh.bar_records
        if record.execution_event is not None
    ]
    assert all(record.execution_price is not None for record in execution_records)
    assert all(
        record.execution_quantity is not None
        for record in execution_records
    )
    assert all(record.decision_snapshot for record in fresh.bar_records)
    assert [record.cash for record in fresh.bar_records] == [
        record.cash for record in warm.bar_records
    ]
    assert [record.equity for record in fresh.bar_records] == [
        record.equity for record in warm.bar_records
    ]
    assert [record.position_size for record in fresh.bar_records] == [
        record.position_size for record in warm.bar_records
    ]
    assert [record.drawdown for record in fresh.bar_records] == [
        record.drawdown for record in warm.bar_records
    ]


@pytest.mark.parametrize(
    "warm_policy",
    [
        pytest.param(HistoricalSourcePolicy.LOCAL_ONLY, id="local-only"),
        pytest.param(HistoricalSourcePolicy.LOCAL_FIRST, id="local-first"),
    ],
)
def test_provider_backed_and_durable_local_backtests_have_stable_parity(
    tmp_path,
    monkeypatch,
    warm_policy,
):
    monkeypatch.chdir(tmp_path)
    database_path = tmp_path / "candles.sqlite"
    provider = RecordingProvider(accepted_candles())
    fresh_factory = ProviderFactory(provider)
    fresh = run_and_capture_result(
        monkeypatch,
        HistoricalSource(
            SQLiteCandleStore(database_path),
            HistoricalSourcePolicy.PROVIDER_BACKED,
            fresh_factory,
        ),
        FRESH_SESSION_ID,
    )

    warm_factory = ProviderFactory()
    warm = run_and_capture_result(
        monkeypatch,
        HistoricalSource(
            SQLiteCandleStore(database_path),
            warm_policy,
            warm_factory,
        ),
        WARM_SESSION_ID,
    )

    assert provider.requests == [(DATASET_CONTEXT, REQUEST)]
    assert fresh_factory.calls == 1
    assert warm_factory.calls == 0
    assert_stable_backtest_parity(fresh, warm)


def test_cold_and_warm_local_first_backtests_have_stable_parity(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)
    database_path = tmp_path / "candles.sqlite"
    provider = RecordingProvider(accepted_candles())
    cold_factory = ProviderFactory(provider)
    cold = run_and_capture_result(
        monkeypatch,
        HistoricalSource(
            SQLiteCandleStore(database_path),
            HistoricalSourcePolicy.LOCAL_FIRST,
            cold_factory,
        ),
        FRESH_SESSION_ID,
    )

    warm_factory = ProviderFactory()
    warm = run_and_capture_result(
        monkeypatch,
        HistoricalSource(
            SQLiteCandleStore(database_path),
            HistoricalSourcePolicy.LOCAL_FIRST,
            warm_factory,
        ),
        WARM_SESSION_ID,
    )

    assert provider.requests == [(DATASET_CONTEXT, REQUEST)]
    assert cold_factory.calls == 1
    assert warm_factory.calls == 0
    assert_stable_backtest_parity(cold, warm)

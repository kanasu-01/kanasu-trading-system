from datetime import datetime, timedelta, timezone

import pytest

import api.backtest_application as application
from api.models.backtest_models import BacktestRunRequest
from core.backtest.backtest_result import BacktestResult
from core.backtest.bar_record import BarRecord
from core.config.app_config import AppConfig
from core.entities.candle import Candle
from core.entities.trade import Trade
from core.config.historical_source_policy import HistoricalSourcePolicy
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_source import HistoricalSource
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.research.software_identity import SoftwareIdentity
from core.runtime.dataset_context import DatasetContext


INDIA = timezone(
    timedelta(hours=5, minutes=30),
    name="Asia/Kolkata",
)
START = datetime(
    2026,
    1,
    5,
    9,
    15,
    tzinfo=INDIA,
)
END = START + timedelta(minutes=90)
REVISION = "d21c204da909f3e2c6201c8ca9e8af005074372f"


class StaticSoftwareIdentityProvider:
    def __init__(self, identity):
        self.identity = identity

    def resolve(self):
        return self.identity


def exact_identity_provider():
    return StaticSoftwareIdentityProvider(
        SoftwareIdentity(
            repository_revision=REVISION,
            worktree_clean=True,
        )
    )


def app_config_for_test(
    tmp_path,
    *,
    risk_per_trade_pct=1.0,
):
    return AppConfig(
        risk_per_trade_pct=risk_per_trade_pct,
        research_database_path=str(
            tmp_path / "research.sqlite3"
        ),
        research_artifact_root=str(
            tmp_path / "research_artifacts"
        ),
    )


def sample_candles():
    return [
        Candle(
            timestamp=START + timedelta(minutes=15 * index),
            open=float(value),
            high=float(value + 1),
            low=float(value - 1),
            close=float(value),
            volume=1000.0,
        )
        for index, value in enumerate(
            [100, 102, 104, 103, 101, 100]
        )
    ]


def request() -> BacktestRunRequest:
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


def test_application_runs_real_backtest_from_local_history(
    tmp_path,
    monkeypatch,
):
    monkeypatch.chdir(tmp_path)

    context = DatasetContext(
        symbol="RELIANCE",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )

    candles = sample_candles()

    store = SQLiteCandleStore(
        tmp_path / "history.sqlite"
    )
    store.save_retrieval(
        context,
        candles,
        [TimeRange(START, END)],
    )

    source = HistoricalSource(
        store=store,
        policy=HistoricalSourcePolicy.LOCAL_ONLY,
    )

    response = application.execute_backtest_request(
        request(),
        app_config=app_config_for_test(
            tmp_path,
            risk_per_trade_pct=1.0,
        ),
        historical_source=source,
        software_identity_provider=(
            exact_identity_provider()
        ),
    )

    assert response.status == "completed"
    assert len(response.run_id) == 8
    assert response.attempt_id is not None
    assert response.evidence_id
    assert response.evidence_status == "ACCEPTED"

    assert [
        point.timestamp
        for point in response.equity_curve
    ] == [
        candle.timestamp
        for candle in candles
    ]

    assert response.summary.completed_trade_count == 1
    assert len(response.trades) == 1

    assert (
        response.trades[0].exit_reason
        == "STRATEGY_EXIT"
    )


def test_application_projects_authoritative_result(
    tmp_path,
    monkeypatch,
):
    captured = {}
    real_create_strategy = application.create_strategy
    source = object()
    candles = sample_candles()

    result = BacktestResult(
        session_id="session-123",
        trades=[
            Trade(
                symbol="RELIANCE",
                entry_time=START,
                entry_price=100.0,
                exit_time=START + timedelta(minutes=30),
                exit_price=102.6,
                stop_price=98.0,
                quantity=10,
                direction="LONG",
                exit_reason="STRATEGY_EXIT",
                pnl=240.0,
                gross_pnl=260.0,
                transaction_cost=20.0,
                pnl_pct=2.6,
            ),
        ],
        bar_records=[
            BarRecord(
                timestamp=START,
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1000.0,
                strategy="SMACrossOver",
                state=None,
                signal=None,
                execution_event=None,
                execution_price=None,
                execution_quantity=None,
                decision_snapshot={},
                equity=100000.0,
                cash=100000.0,
                position_size=0,
                drawdown=0.0,
            ),
            BarRecord(
                timestamp=START + timedelta(minutes=15),
                open=102.0,
                high=103.0,
                low=101.0,
                close=102.0,
                volume=1000.0,
                strategy="SMACrossOver",
                state=None,
                signal=None,
                execution_event=None,
                execution_price=None,
                execution_quantity=None,
                decision_snapshot={},
                equity=100250.0,
                cash=100250.0,
                position_size=0,
                drawdown=0.0,
            ),
        ],
    )

    def create_strategy(config):
        captured["config"] = config
        strategy = real_create_strategy(config)
        captured["strategy"] = strategy
        return strategy

    def retrieve_backtest_candles(**kwargs):
        captured.setdefault("retrievals", []).append(kwargs)
        return candles

    def execute_backtest_candles(**kwargs):
        captured["execution"] = kwargs
        return result

    monkeypatch.setattr(
        application,
        "create_strategy",
        create_strategy,
    )
    monkeypatch.setattr(
        application,
        "retrieve_backtest_candles",
        retrieve_backtest_candles,
    )
    monkeypatch.setattr(
        application,
        "execute_backtest_candles",
        execute_backtest_candles,
    )

    response = application.execute_backtest_request(
        request(),
        app_config=app_config_for_test(
            tmp_path,
            risk_per_trade_pct=2.5,
        ),
        historical_source=source,
        software_identity_provider=(
            exact_identity_provider()
        ),
    )

    config = captured["config"]

    assert config.enable_replay is False
    assert config.enable_visualization is False
    assert config.enable_exports is False

    assert config.strategy_params == {
        "fast_period": 1,
        "slow_period": 2,
    }

    assert len(captured["retrievals"]) == 1
    retrieval = captured["retrievals"][0]

    assert retrieval["historical_source"] is source
    assert retrieval["config"] is config
    assert retrieval["dataset_context"] == DatasetContext(
        symbol="RELIANCE",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )

    execution = captured["execution"]

    assert execution["candles"] is candles
    assert execution["strategy"] is captured["strategy"]
    assert execution["config"] is config

    assert (
        execution["runtime_context"].risk_per_trade_pct
        == 2.5
    )

    assert execution["dataset_context"] == retrieval[
        "dataset_context"
    ]

    assert response.run_id == "session-123"
    assert response.attempt_id is not None
    assert response.evidence_id
    assert response.evidence_status == "ACCEPTED"

    assert [
        point.equity
        for point in response.equity_curve
    ] == [
        100000.0,
        100250.0,
    ]

    assert response.summary.net_realized_pnl == 240.0
    assert response.summary.account_pnl == 250.0
    assert response.summary.account_return_pct == 0.25

    trade = response.trades[0]

    assert trade.net_pnl == 240.0
    assert trade.gross_pnl == 260.0
    assert trade.transaction_cost == 20.0
    assert trade.instrument_return_pct == 2.6


def test_application_returns_authoritative_empty_result(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        application,
        "retrieve_backtest_candles",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        application,
        "execute_backtest_candles",
        lambda **kwargs: BacktestResult(
            trades=[],
            bar_records=[],
            session_id="empty-run",
        ),
    )

    response = application.execute_backtest_request(
        request(),
        app_config=app_config_for_test(tmp_path),
        historical_source=object(),
        software_identity_provider=(
            exact_identity_provider()
        ),
    )

    assert response.run_id == "empty-run"
    assert response.attempt_id is not None
    assert response.evidence_id
    assert response.evidence_status == "ACCEPTED"
    assert response.trades == []
    assert response.equity_curve == []

    assert response.summary.completed_trade_count == 0
    assert response.summary.account_pnl == 0.0
    assert response.summary.account_return_pct == 0.0
    assert response.summary.max_equity_drawdown_pct == 0.0


def test_application_propagates_historical_retrieval_failure(
    tmp_path,
    monkeypatch,
):
    def fail_retrieval(**kwargs):
        raise RuntimeError("historical backend failed")

    def must_not_execute(**kwargs):
        pytest.fail(
            "Backtest execution must not follow retrieval failure"
        )

    monkeypatch.setattr(
        application,
        "retrieve_backtest_candles",
        fail_retrieval,
    )
    monkeypatch.setattr(
        application,
        "execute_backtest_candles",
        must_not_execute,
    )

    with pytest.raises(
        RuntimeError,
        match="historical backend failed",
    ):
        application.execute_backtest_request(
            request(),
            app_config=app_config_for_test(tmp_path),
            historical_source=object(),
            software_identity_provider=(
                exact_identity_provider()
            ),
        )


def test_application_propagates_backtest_execution_failure(
    tmp_path,
    monkeypatch,
):
    candles = sample_candles()

    monkeypatch.setattr(
        application,
        "retrieve_backtest_candles",
        lambda **kwargs: candles,
    )

    def fail_execution(**kwargs):
        assert kwargs["candles"] is candles
        raise RuntimeError("backtest execution failed")

    monkeypatch.setattr(
        application,
        "execute_backtest_candles",
        fail_execution,
    )

    with pytest.raises(
        RuntimeError,
        match="backtest execution failed",
    ):
        application.execute_backtest_request(
            request(),
            app_config=app_config_for_test(tmp_path),
            historical_source=object(),
            software_identity_provider=(
                exact_identity_provider()
            ),
        )


def test_application_exposes_incomplete_identity_without_attempt(
    tmp_path,
    monkeypatch,
):
    candles = sample_candles()

    monkeypatch.setattr(
        application,
        "retrieve_backtest_candles",
        lambda **kwargs: candles,
    )
    monkeypatch.setattr(
        application,
        "execute_backtest_candles",
        lambda **kwargs: BacktestResult(
            trades=[],
            bar_records=[],
            session_id="dirty-runtime",
        ),
    )

    response = application.execute_backtest_request(
        request(),
        app_config=app_config_for_test(tmp_path),
        historical_source=object(),
        software_identity_provider=(
            StaticSoftwareIdentityProvider(
                SoftwareIdentity(
                    repository_revision=REVISION,
                    worktree_clean=False,
                )
            )
        ),
    )

    assert response.run_id == "dirty-runtime"
    assert response.attempt_id is None
    assert response.evidence_id
    assert response.evidence_status == "INCOMPLETE"

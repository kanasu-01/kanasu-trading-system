import threading
from datetime import datetime, timedelta, timezone

import api.backtest_application as backtest_application
import api.routes.paper_trading_routes as paper_routes
from api.paper_trading_application import PaperTradingApplication
from core.config.app_config import AppConfig
from core.config.historical_source_policy import HistoricalSourcePolicy
from core.entities.candle import Candle
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_source import HistoricalSource
from core.market_data.sqlite_candle_store import SQLiteCandleStore
from core.paper_trading.paper_trading_session import PaperTradingSession
from core.runtime.dataset_context import DatasetContext
from core.runtime.paper_runtime import PreparedLivePaperRun


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

PAPER_END = datetime(
    2026,
    1,
    5,
    15,
    30,
    tzinfo=INDIA,
)


class ControlledRuntime:
    def __init__(self):
        self.started = threading.Event()
        self.stopped = threading.Event()
        self.stop_calls = 0

    def wait_until_started(
        self,
        timeout_seconds=None,
    ):
        return self.started.wait(
            timeout_seconds
        )

    def run_until(self, **_kwargs):
        self.started.set()
        self.stopped.wait(timeout=5.0)

    def stop(self):
        self.stop_calls += 1
        self.stopped.set()


def prepared_paper_run(
    runtime: ControlledRuntime,
) -> PreparedLivePaperRun:
    session = PaperTradingSession(
        session_id="paper-integration-1",
        strategy_name="SMACrossOver",
        symbol="RELIANCE",
        initial_capital=100000,
    )

    class PortfolioManagerStub:
        @staticmethod
        def snapshot():
            from types import SimpleNamespace

            return SimpleNamespace(
                cash=100000.0,
                position_size=0.0,
                position_value=0.0,
                equity=100000.0,
                realized_pnl=0.0,
                unrealized_pnl=0.0,
                total_pnl=0.0,
                peak_equity=100000.0,
                drawdown=0.0,
            )

    class ExecutionEngineStub:
        portfolio_manager = PortfolioManagerStub()
        completed_trades = []
        most_recent_execution = None
        last_execution_event = None
        last_execution_price = None
        last_execution_quantity = None

        @staticmethod
        def get_runtime_position(_symbol):
            return None

    session.execution_engine = ExecutionEngineStub()

    return PreparedLivePaperRun(
        session=session,
        runtime=runtime,
        state_lock=threading.RLock(),
        session_end=PAPER_END,
        now=lambda: PAPER_END - timedelta(hours=1),
        clock_interval_seconds=0.0,
    )


def test_route_backtest_runs_authoritative_application_path(
    tmp_path,
    monkeypatch,
):
    context = DatasetContext(
        symbol="RELIANCE",
        timeframe="15m",
        timezone="Asia/Kolkata",
    )

    candles = [
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

    store = SQLiteCandleStore(
        tmp_path / "history.sqlite3"
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

    monkeypatch.setattr(
        backtest_application,
        "load_app_config",
        lambda: AppConfig(
            risk_per_trade_pct=1.0,
        ),
    )

    monkeypatch.setattr(
        backtest_application,
        "create_historical_source",
        lambda _config: source,
    )

    import asyncio
    from api.models.backtest_models import BacktestRunRequest
    import api.routes.backtest_routes as backtest_routes

    response = asyncio.run(
        backtest_routes.run_backtest(
            BacktestRunRequest(
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
        )
    )

    payload = response.model_dump(mode="json")

    assert payload["status"] == "completed"
    assert payload["run_id"] != "bt_mock_001"
    assert len(payload["run_id"]) == 8

    assert (
        payload["summary"]["completed_trade_count"]
        == 1
    )

    assert len(payload["equity_curve"]) == len(candles)
    assert len(payload["trades"]) == 1

    assert (
        payload["trades"][0]["exit_reason"]
        == "STRATEGY_EXIT"
    )


def test_route_paper_start_status_stop_uses_real_application_ownership(
    monkeypatch,
):
    runtime = ControlledRuntime()

    application = PaperTradingApplication(
        lambda _request: prepared_paper_run(
            runtime
        )
    )

    monkeypatch.setattr(
        paper_routes,
        "paper_trading_application",
        application,
    )

    import asyncio
    from api.models.paper_trading_models import PaperTradingStartRequest

    started = asyncio.run(
        paper_routes.start_paper_trading(
            PaperTradingStartRequest(
                symbol="RELIANCE",
                strategy_id="sma_crossover",
            )
        )
    )

    assert (
        started.session_id
        == "paper-integration-1"
    )

    assert runtime.started.wait(
        timeout=1.0
    )

    running = asyncio.run(
        paper_routes.get_paper_trading_status()
    )

    running_payload = running.model_dump(mode="json")

    assert running_payload["active"] is True
    assert (
        running_payload["snapshot"]["status"]
        == "RUNNING"
    )
    assert (
        running_payload["snapshot"]["cash"]
        == 100000.0
    )
    assert (
        running_payload["snapshot"]["equity"]
        == 100000.0
    )

    stopped = asyncio.run(
        paper_routes.stop_paper_trading()
    )

    assert stopped.status == "STOPPED"

    terminal = asyncio.run(
        paper_routes.get_paper_trading_status()
    )

    assert runtime.stop_calls == 1

    terminal_payload = terminal.model_dump(
        mode="json"
    )

    assert terminal_payload["active"] is False
    assert (
        terminal_payload["snapshot"]["status"]
        == "STOPPED"
    )
    assert (
        terminal_payload["snapshot"]["session_id"]
        == "paper-integration-1"
    )

import asyncio
import json

import api.main as main_module
import api.routes.paper_trading_routes as routes
from api.models.paper_trading_models import (
    PaperTradingStartRequest,
    PaperTradingStartResponse,
    PaperTradingStatusResponse,
    PaperTradingStopResponse,
)
from api.paper_trading_application import (
    PaperLifecycleConflict,
)


def request() -> PaperTradingStartRequest:
    return PaperTradingStartRequest(
        symbol="RELIANCE",
        strategy_id="sma_crossover",
    )


def snapshot_payload(
    *,
    status="RUNNING",
):
    return {
        "session_id": "paper-live-123",
        "status": status,
        "strategy_name": "SMACrossOver",
        "symbol": "RELIANCE",
        "started_at": (
            "2026-01-05T10:00:00+05:30"
            if status != "CREATED"
            else None
        ),
        "stopped_at": (
            "2026-01-05T10:30:00+05:30"
            if status in {
                "STOPPED",
                "FAILED",
            }
            else None
        ),
        "initial_capital": 100000,
        "cash": 100000.0,
        "position_size": 0.0,
        "position_value": 0.0,
        "equity": 100000.0,
        "realized_pnl": 0.0,
        "unrealized_pnl": 0.0,
        "total_pnl": 0.0,
        "peak_equity": 100000.0,
        "drawdown": 0.0,
        "active_position": None,
        "completed_trade_count": 0,
        "last_execution_event": None,
        "last_execution_price": None,
        "last_execution_quantity": None,
        "failure_type": None,
        "failure_message": None,
    }


def test_start_route_delegates_to_threadpool(
    monkeypatch,
):
    captured = {}

    expected = PaperTradingStartResponse(
        **snapshot_payload()
    )

    async def run_in_threadpool(
        function,
        *args,
        **kwargs,
    ):
        captured["function"] = function
        captured["args"] = args
        captured["kwargs"] = kwargs
        return expected

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        run_in_threadpool,
    )

    request_model = request()

    actual = asyncio.run(
        routes.start_paper_trading(
            request_model
        )
    )

    assert actual is expected
    assert (
        captured["function"].__self__
        is routes.paper_trading_application
    )
    assert (
        captured["function"].__name__
        == "start"
    )
    assert captured["args"] == (
        request_model,
    )
    assert captured["kwargs"] == {}


def test_start_route_returns_stable_conflict(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise PaperLifecycleConflict(
            "already running internal detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    result = asyncio.run(
        routes.start_paper_trading(
            request()
        )
    )

    assert result.status_code == 409
    assert json.loads(result.body) == {
        "code": "paper_lifecycle_conflict",
        "message": "Paper trading lifecycle conflict",
    }


def test_start_route_returns_stable_500(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise RuntimeError(
            "secret provider detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    result = asyncio.run(
        routes.start_paper_trading(
            request()
        )
    )

    assert result.status_code == 500
    assert json.loads(result.body) == {
        "code": "paper_start_failed",
        "message": "Paper trading start failed",
    }


def test_status_route_delegates_to_threadpool(
    monkeypatch,
):
    captured = {}

    expected = PaperTradingStatusResponse(
        active=True,
        snapshot=snapshot_payload(),
    )

    async def run_in_threadpool(
        function,
        *args,
        **kwargs,
    ):
        captured["function"] = function
        captured["args"] = args
        captured["kwargs"] = kwargs
        return expected

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        run_in_threadpool,
    )

    actual = asyncio.run(
        routes.get_paper_trading_status()
    )

    assert actual is expected
    assert (
        captured["function"].__self__
        is routes.paper_trading_application
    )
    assert (
        captured["function"].__name__
        == "status"
    )
    assert captured["args"] == ()
    assert captured["kwargs"] == {}


def test_status_route_returns_stable_500(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise RuntimeError(
            "snapshot internal detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    result = asyncio.run(
        routes.get_paper_trading_status()
    )

    assert result.status_code == 500
    assert json.loads(result.body) == {
        "code": "paper_status_failed",
        "message": "Paper trading status failed",
    }


def test_stop_route_delegates_to_threadpool(
    monkeypatch,
):
    captured = {}

    expected = PaperTradingStopResponse(
        **snapshot_payload(
            status="STOPPED"
        )
    )

    async def run_in_threadpool(
        function,
        *args,
        **kwargs,
    ):
        captured["function"] = function
        captured["args"] = args
        captured["kwargs"] = kwargs
        return expected

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        run_in_threadpool,
    )

    actual = asyncio.run(
        routes.stop_paper_trading()
    )

    assert actual is expected
    assert (
        captured["function"].__self__
        is routes.paper_trading_application
    )
    assert (
        captured["function"].__name__
        == "stop"
    )
    assert captured["args"] == ()
    assert captured["kwargs"] == {}


def test_stop_route_returns_stable_conflict(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise PaperLifecycleConflict(
            "no active internal detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    result = asyncio.run(
        routes.stop_paper_trading()
    )

    assert result.status_code == 409
    assert json.loads(result.body) == {
        "code": "paper_lifecycle_conflict",
        "message": "Paper trading lifecycle conflict",
    }


def test_stop_route_returns_stable_500(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise RuntimeError(
            "runtime stop internal detail"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    result = asyncio.run(
        routes.stop_paper_trading()
    )

    assert result.status_code == 500
    assert json.loads(result.body) == {
        "code": "paper_stop_failed",
        "message": "Paper trading stop failed",
    }


def test_paper_http_contract_is_typed():
    schema = main_module.app.openapi()

    start = schema["paths"][
        "/api/paper-trading/start"
    ]["post"]

    assert (
        start["requestBody"]["content"][
            "application/json"
        ]["schema"]
        == {
            "$ref": (
                "#/components/schemas/"
                "PaperTradingStartRequest"
            )
        }
    )

    start_responses = start["responses"]

    assert (
        start_responses["200"]["content"][
            "application/json"
        ]["schema"]
        == {
            "$ref": (
                "#/components/schemas/"
                "PaperTradingStartResponse"
            )
        }
    )
    assert (
        start_responses["409"]["content"][
            "application/json"
        ]["schema"]
        == {
            "$ref": (
                "#/components/schemas/"
                "ApiErrorResponse"
            )
        }
    )
    assert (
        start_responses["422"]["content"][
            "application/json"
        ]["schema"]
        == {
            "$ref": (
                "#/components/schemas/"
                "ApiErrorResponse"
            )
        }
    )
    assert (
        start_responses["500"]["content"][
            "application/json"
        ]["schema"]
        == {
            "$ref": (
                "#/components/schemas/"
                "ApiErrorResponse"
            )
        }
    )

    status = schema["paths"][
        "/api/paper-trading/status"
    ]["get"]

    assert (
        status["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        == {
            "$ref": (
                "#/components/schemas/"
                "PaperTradingStatusResponse"
            )
        }
    )
    assert (
        status["responses"]["500"]["content"][
            "application/json"
        ]["schema"]
        == {
            "$ref": (
                "#/components/schemas/"
                "ApiErrorResponse"
            )
        }
    )

    stop = schema["paths"][
        "/api/paper-trading/stop"
    ]["post"]

    assert (
        stop["responses"]["200"]["content"][
            "application/json"
        ]["schema"]
        == {
            "$ref": (
                "#/components/schemas/"
                "PaperTradingStopResponse"
            )
        }
    )
    assert (
        stop["responses"]["409"]["content"][
            "application/json"
        ]["schema"]
        == {
            "$ref": (
                "#/components/schemas/"
                "ApiErrorResponse"
            )
        }
    )
    assert (
        stop["responses"]["500"]["content"][
            "application/json"
        ]["schema"]
        == {
            "$ref": (
                "#/components/schemas/"
                "ApiErrorResponse"
            )
        }
    )

import asyncio
import json
from datetime import datetime, timedelta, timezone

from fastapi.exceptions import RequestValidationError

import api.main as main_module
import api.routes.backtest_routes as routes
from api.models.backtest_models import (
    BacktestRunRequest,
    BacktestRunResponse,
)
from api.models.common_models import ApiErrorResponse


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
END = START + timedelta(hours=1)


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
            "fast_period": 20,
            "slow_period": 50,
        },
    )


def response() -> BacktestRunResponse:
    return BacktestRunResponse(
        run_id="run-123",
        status="completed",
        symbol="RELIANCE",
        timeframe="15m",
        strategy_id="sma_crossover",
        start=START,
        end=END,
        timezone="Asia/Kolkata",
        summary={
            "completed_trade_count": 0,
            "net_profitable_trade_count": 0,
            "net_losing_trade_count": 0,
            "net_breakeven_trade_count": 0,
            "net_profitable_trade_rate_pct": 0.0,
            "mean_positive_instrument_return_pct": 0.0,
            "mean_negative_instrument_return_pct": 0.0,
            "mean_instrument_return_pct": 0.0,
            "gross_realized_pnl": 0.0,
            "net_realized_pnl": 0.0,
            "mean_net_pnl_per_completed_trade": 0.0,
            "completed_trade_transaction_cost_total": 0.0,
            "account_pnl": 0.0,
            "account_return_pct": 0.0,
            "max_equity_drawdown_pct": 0.0,
        },
        equity_curve=[],
        trades=[],
    )


def test_backtest_route_delegates_to_threadpool(
    monkeypatch,
):
    captured = {}
    expected = response()

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
        routes.run_backtest(request_model)
    )

    assert actual is expected
    assert (
        captured["function"]
        is routes.execute_backtest_request
    )
    assert captured["args"] == (request_model,)
    assert captured["kwargs"] == {}


def test_backtest_route_returns_stable_500(
    monkeypatch,
):
    async def fail(
        function,
        *args,
        **kwargs,
    ):
        raise RuntimeError(
            "historical provider unavailable"
        )

    monkeypatch.setattr(
        routes,
        "run_in_threadpool",
        fail,
    )

    result = asyncio.run(
        routes.run_backtest(request())
    )

    assert result.status_code == 500
    assert json.loads(result.body) == {
        "code": "backtest_execution_failed",
        "message": "Backtest execution failed",
    }


def test_validation_handler_returns_stable_422():
    result = asyncio.run(
        main_module.handle_request_validation_error(
            None,
            RequestValidationError([]),
        )
    )

    assert result.status_code == 422
    assert json.loads(result.body) == {
        "code": "invalid_request",
        "message": "Request validation failed",
    }

    assert (
        main_module.app.exception_handlers[
            RequestValidationError
        ]
        is main_module.handle_request_validation_error
    )


def test_backtest_http_contract_is_typed():
    schema = main_module.app.openapi()
    operation = schema["paths"]["/api/backtest/run"]["post"]

    assert operation["requestBody"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/BacktestRunRequest",
    }

    responses = operation["responses"]

    assert responses["200"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/BacktestRunResponse",
    }
    assert responses["422"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ApiErrorResponse",
    }
    assert responses["500"]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/ApiErrorResponse",
    }

import asyncio

import pytest

from pydantic import ValidationError

from api.models.backtest_models import (
    BacktestRunRequest,
    BacktestSummaryResponse,
    BacktestTradeResponse,
)

from api.models.common_models import (
    ApiErrorResponse,
)

from api.models.paper_trading_models import (
    PaperTradingSnapshotResponse,
    PaperTradingStartRequest,
)

from api.routes.backtest_routes import (
    get_backtest_config,
)

from api.routes.paper_trading_routes import (
    get_paper_trading_config,
)


def _valid_backtest_request(
    **overrides,
) -> dict:
    request = {
        "symbol": "RELIANCE",
        "timeframe": "15m",
        "strategy_id": "sma_crossover",
        "start": (
            "2026-01-05T09:15:00+05:30"
        ),
        "end": (
            "2026-01-05T15:30:00+05:30"
        ),
        "timezone": "Asia/Kolkata",
        "initial_capital": 100000,
        "strategy_params": {
            "fast_period": 20,
            "slow_period": 50,
        },
    }

    request.update(overrides)

    return request


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("symbol", "TCS"),
        ("timeframe", "1m"),
        ("strategy_id", "camarilla"),
        ("timezone", "UTC"),
    ],
)
def test_backtest_request_rejects_unsupported_choices(
    field_name,
    value,
):
    with pytest.raises(ValidationError):
        BacktestRunRequest(
            **_valid_backtest_request(
                **{
                    field_name: value,
                }
            )
        )


@pytest.mark.parametrize(
    "capital",
    [
        0,
        -1,
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_backtest_request_rejects_invalid_capital(
    capital,
):
    with pytest.raises(ValidationError):
        BacktestRunRequest(
            **_valid_backtest_request(
                initial_capital=capital
            )
        )


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (
            "2026-01-05T15:30:00+05:30",
            "2026-01-05T09:15:00+05:30",
        ),
        (
            "2026-01-05T09:15:00+05:30",
            "2026-01-05T09:15:00+05:30",
        ),
        (
            "2026-01-05T09:15:00",
            "2026-01-05T15:30:00+05:30",
        ),
    ],
)
def test_backtest_request_rejects_invalid_time_windows(
    start,
    end,
):
    with pytest.raises(ValidationError):
        BacktestRunRequest(
            **_valid_backtest_request(
                start=start,
                end=end,
            )
        )


@pytest.mark.parametrize(
    "strategy_params",
    [
        {
            "fast_period": 0,
            "slow_period": 50,
        },
        {
            "fast_period": 20,
            "slow_period": 0,
        },
        {
            "fast_period": 50,
            "slow_period": 50,
        },
        {
            "fast_period": 60,
            "slow_period": 50,
        },
        {
            "fast_period": 20,
            "slow_period": 50,
            "unknown": 1,
        },
    ],
)
def test_backtest_request_rejects_invalid_sma_params(
    strategy_params,
):
    with pytest.raises(ValidationError):
        BacktestRunRequest(
            **_valid_backtest_request(
                strategy_params=strategy_params
            )
        )


def test_backtest_request_accepts_supported_contract():
    request = BacktestRunRequest(
        **_valid_backtest_request()
    )

    assert request.symbol == "RELIANCE"
    assert request.timeframe == "15m"

    assert (
        request.strategy_id
        == "sma_crossover"
    )

    assert (
        request.timezone
        == "Asia/Kolkata"
    )

    assert (
        request.strategy_params.fast_period
        == 20
    )

    assert (
        request.strategy_params.slow_period
        == 50
    )


def test_application_config_exposes_only_supported_choices():
    backtest_config = asyncio.run(
        get_backtest_config()
    )

    paper_config = asyncio.run(
        get_paper_trading_config()
    )

    assert [
        item.id
        for item in backtest_config.markets
    ] == [
        "NSE",
    ]

    assert [
        item.symbol
        for item in backtest_config.symbols
    ] == [
        "RELIANCE",
    ]

    assert [
        item.id
        for item in backtest_config.timeframes
    ] == [
        "5m",
        "15m",
    ]

    assert [
        item.id
        for item in backtest_config.strategies
    ] == [
        "sma_crossover",
    ]

    assert (
        backtest_config.timezones
        == ["Asia/Kolkata"]
    )

    assert [
        item.symbol
        for item in paper_config.symbols
    ] == [
        "RELIANCE",
    ]

    assert [
        item.id
        for item in paper_config.strategies
    ] == [
        "sma_crossover",
    ]


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("symbol", "TCS"),
        ("strategy_id", "camarilla"),
    ],
)
def test_paper_start_rejects_unsupported_choices(
    field_name,
    value,
):
    request = {
        "symbol": "RELIANCE",
        "strategy_id": "sma_crossover",
    }

    request[field_name] = value

    with pytest.raises(ValidationError):
        PaperTradingStartRequest(
            **request
        )


def test_backtest_summary_contract_uses_authoritative_keys():
    assert set(
        BacktestSummaryResponse.model_fields
    ) == {
        "completed_trade_count",
        "net_profitable_trade_count",
        "net_losing_trade_count",
        "net_breakeven_trade_count",
        "net_profitable_trade_rate_pct",
        "mean_positive_instrument_return_pct",
        "mean_negative_instrument_return_pct",
        "mean_instrument_return_pct",
        "gross_realized_pnl",
        "net_realized_pnl",
        "mean_net_pnl_per_completed_trade",
        "completed_trade_transaction_cost_total",
        "account_pnl",
        "account_return_pct",
        "max_equity_drawdown_pct",
    }


def test_backtest_trade_contract_uses_unambiguous_pnl_names():
    assert set(
        BacktestTradeResponse.model_fields
    ) == {
        "symbol",
        "entry_time",
        "entry_price",
        "exit_time",
        "exit_price",
        "stop_price",
        "quantity",
        "direction",
        "exit_reason",
        "net_pnl",
        "gross_pnl",
        "transaction_cost",
        "instrument_return_pct",
    }


def test_paper_snapshot_contract_matches_authoritative_snapshot():
    assert set(
        PaperTradingSnapshotResponse.model_fields
    ) == {
        "session_id",
        "status",
        "strategy_name",
        "symbol",
        "started_at",
        "stopped_at",
        "initial_capital",
        "cash",
        "position_size",
        "position_value",
        "equity",
        "realized_pnl",
        "unrealized_pnl",
        "total_pnl",
        "peak_equity",
        "drawdown",
        "active_position",
        "completed_trade_count",
        "last_execution_event",
        "last_execution_price",
        "last_execution_quantity",
        "failure_type",
        "failure_message",
    }


def test_api_error_contract_is_stable():
    error = ApiErrorResponse(
        code="invalid_request",
        message="request is invalid",
    )

    assert error.model_dump() == {
        "code": "invalid_request",
        "message": "request is invalid",
    }

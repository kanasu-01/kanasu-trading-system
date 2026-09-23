from datetime import datetime
from typing import Literal, Self

from pydantic import (
    Field,
    field_validator,
    model_validator,
)

from api.application_catalog import (
    SUPPORTED_STRATEGIES,
    SUPPORTED_SYMBOLS,
    SUPPORTED_TIMEFRAMES,
    SUPPORTED_TIMEZONES,
)

from api.models.common_models import (
    MarketOption,
    StrategyOption,
    StrictApiModel,
    SymbolOption,
    TimeframeOption,
)


def _supported_value(
    value: str,
    *,
    supported: frozenset[str],
    field_name: str,
) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty"
        )

    if normalized not in supported:
        raise ValueError(
            f"unsupported {field_name}: {normalized}"
        )

    return normalized


def _is_aware(value: datetime) -> bool:
    return (
        value.tzinfo is not None
        and value.utcoffset() is not None
    )


class SMACrossoverParams(StrictApiModel):
    fast_period: int = Field(
        default=20,
        gt=0,
    )

    slow_period: int = Field(
        default=50,
        gt=0,
    )

    @model_validator(mode="after")
    def validate_period_order(self) -> Self:
        if self.fast_period >= self.slow_period:
            raise ValueError(
                "fast_period must be < slow_period"
            )

        return self


class BacktestRunRequest(StrictApiModel):
    symbol: str
    timeframe: str
    strategy_id: str

    start: datetime
    end: datetime

    timezone: str

    initial_capital: float = Field(
        gt=0
    )

    strategy_params: SMACrossoverParams = Field(
        default_factory=SMACrossoverParams
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(
        cls,
        value: str,
    ) -> str:
        return _supported_value(
            value,
            supported=SUPPORTED_SYMBOLS,
            field_name="symbol",
        )

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(
        cls,
        value: str,
    ) -> str:
        return _supported_value(
            value,
            supported=SUPPORTED_TIMEFRAMES,
            field_name="timeframe",
        )

    @field_validator("strategy_id")
    @classmethod
    def validate_strategy_id(
        cls,
        value: str,
    ) -> str:
        return _supported_value(
            value,
            supported=SUPPORTED_STRATEGIES,
            field_name="strategy_id",
        )

    @field_validator("timezone")
    @classmethod
    def validate_timezone(
        cls,
        value: str,
    ) -> str:
        return _supported_value(
            value,
            supported=SUPPORTED_TIMEZONES,
            field_name="timezone",
        )

    @model_validator(mode="after")
    def validate_time_window(self) -> Self:
        if _is_aware(self.start) != _is_aware(self.end):
            raise ValueError(
                "start and end must use compatible timezone awareness"
            )

        if self.end <= self.start:
            raise ValueError(
                "end must be after start"
            )

        return self


class BacktestConfigResponse(StrictApiModel):
    markets: list[MarketOption]
    symbols: list[SymbolOption]
    timeframes: list[TimeframeOption]
    strategies: list[StrategyOption]
    timezones: list[str]


class BacktestSummaryResponse(StrictApiModel):
    completed_trade_count: int = Field(
        ge=0
    )

    net_profitable_trade_count: int = Field(
        ge=0
    )

    net_losing_trade_count: int = Field(
        ge=0
    )

    net_breakeven_trade_count: int = Field(
        ge=0
    )

    net_profitable_trade_rate_pct: float
    mean_positive_instrument_return_pct: float
    mean_negative_instrument_return_pct: float
    mean_instrument_return_pct: float

    gross_realized_pnl: float
    net_realized_pnl: float
    mean_net_pnl_per_completed_trade: float
    completed_trade_transaction_cost_total: float

    account_pnl: float
    account_return_pct: float
    max_equity_drawdown_pct: float


class BacktestEquityPoint(StrictApiModel):
    timestamp: datetime
    equity: float


class BacktestTradeResponse(StrictApiModel):
    symbol: str

    entry_time: datetime
    entry_price: float

    exit_time: datetime
    exit_price: float

    stop_price: float
    quantity: int = Field(gt=0)

    direction: str
    exit_reason: str

    net_pnl: float
    gross_pnl: float
    transaction_cost: float
    instrument_return_pct: float


class BacktestRunResponse(StrictApiModel):
    run_id: str

    status: Literal["completed"]

    symbol: str
    timeframe: str
    strategy_id: str

    start: datetime
    end: datetime
    timezone: str

    summary: BacktestSummaryResponse

    equity_curve: list[BacktestEquityPoint]

    trades: list[BacktestTradeResponse]

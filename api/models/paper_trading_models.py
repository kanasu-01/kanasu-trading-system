from typing import Literal

from pydantic import (
    Field,
    field_validator,
)

from api.application_catalog import (
    SUPPORTED_STRATEGIES,
    SUPPORTED_SYMBOLS,
)

from api.models.common_models import (
    StrategyOption,
    StrictApiModel,
    SymbolOption,
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


class PaperTradingConfigResponse(
    StrictApiModel
):
    symbols: list[SymbolOption]
    strategies: list[StrategyOption]


class PaperTradingStartRequest(
    StrictApiModel
):
    symbol: str
    strategy_id: str

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


class PaperPositionSnapshotResponse(
    StrictApiModel
):
    symbol: str
    direction: str

    quantity: int = Field(gt=0)

    entry_time: str
    entry_price: float
    stop_price: float


class PaperTradingSnapshotResponse(
    StrictApiModel
):
    session_id: str

    status: Literal[
        "CREATED",
        "RUNNING",
        "STOPPED",
        "FAILED",
    ]

    strategy_name: str
    symbol: str

    started_at: str | None
    stopped_at: str | None

    initial_capital: float = Field(
        gt=0
    )

    cash: float | None

    position_size: float | None
    position_value: float | None

    equity: float | None

    realized_pnl: float | None
    unrealized_pnl: float | None
    total_pnl: float | None

    peak_equity: float | None
    drawdown: float | None

    active_position: (
        PaperPositionSnapshotResponse | None
    )

    completed_trade_count: int = Field(
        ge=0
    )

    last_execution_event: str | None
    last_execution_price: float | None
    last_execution_quantity: int | None

    failure_type: str | None
    failure_message: str | None


class PaperTradingStatusResponse(
    StrictApiModel
):
    active: bool

    snapshot: (
        PaperTradingSnapshotResponse | None
    )


class PaperTradingStartResponse(
    PaperTradingSnapshotResponse
):
    pass


class PaperTradingStopResponse(
    PaperTradingSnapshotResponse
):
    pass

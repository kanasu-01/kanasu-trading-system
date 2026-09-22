from dataclasses import dataclass


@dataclass(frozen=True)
class PaperPositionSnapshot:
    """Read-only view of the authoritative open paper position."""

    symbol: str
    direction: str
    quantity: int
    entry_time: str
    entry_price: float
    stop_price: float


@dataclass(frozen=True)
class PaperTradingSnapshot:
    """Immutable read-only view of authoritative paper runtime state."""

    session_id: str
    status: str
    strategy_name: str
    symbol: str

    started_at: str | None
    stopped_at: str | None
    initial_capital: float

    cash: float | None
    position_size: float | None
    position_value: float | None
    equity: float | None
    realized_pnl: float | None
    unrealized_pnl: float | None
    total_pnl: float | None
    peak_equity: float | None
    drawdown: float | None

    active_position: PaperPositionSnapshot | None
    completed_trade_count: int

    last_execution_event: str | None
    last_execution_price: float | None
    last_execution_quantity: int | None

    failure_type: str | None
    failure_message: str | None

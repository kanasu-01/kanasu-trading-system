from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.paper_trading.paper_trading_snapshot import (
    PaperPositionSnapshot,
    PaperTradingSnapshot,
)


@dataclass
class PaperTradingSession:
    """Runtime lifecycle and read-only observability for one paper session."""

    session_id: str
    strategy_name: str
    symbol: str
    initial_capital: float

    status: str = "CREATED"

    started_at: datetime | None = None
    stopped_at: datetime | None = None

    failure_type: str | None = None
    failure_message: str | None = None

    feed: Any | None = None
    strategy: Any | None = None
    runtime_context: Any | None = None
    dataset_context: Any | None = None
    strategy_runner: Any | None = None
    execution_engine: Any | None = None

    def start(self) -> None:
        """Mark a newly initialized session as running."""

        if self.status != "CREATED":
            raise RuntimeError(
                f"paper session cannot start from state {self.status}"
            )

        self.status = "RUNNING"
        self.started_at = datetime.now()

    def stop(self) -> None:
        """Mark normal runtime completion without hiding a prior failure."""

        if self.status == "FAILED":
            return

        if self.status == "STOPPED":
            return

        self.status = "STOPPED"
        self.stopped_at = datetime.now()

    def fail(self, failure: Exception) -> None:
        """Record terminal runtime failure while preserving its cause."""

        if self.status in {"FAILED", "STOPPED"}:
            return

        self.status = "FAILED"
        self.stopped_at = datetime.now()
        self.failure_type = type(failure).__name__
        self.failure_message = str(failure)

    def snapshot(self) -> PaperTradingSnapshot:
        """Read current state from execution/portfolio authority."""

        engine = self.execution_engine

        cash = None
        position_size = None
        position_value = None
        equity = None
        realized_pnl = None
        unrealized_pnl = None
        total_pnl = None
        peak_equity = None
        drawdown = None

        active_position = None
        completed_trade_count = 0
        last_execution_event = None
        last_execution_price = None
        last_execution_quantity = None

        if engine is not None:
            portfolio_state = engine.portfolio_manager.snapshot()

            cash = portfolio_state.cash
            position_size = portfolio_state.position_size
            position_value = portfolio_state.position_value
            equity = portfolio_state.equity
            realized_pnl = portfolio_state.realized_pnl
            unrealized_pnl = portfolio_state.unrealized_pnl
            total_pnl = portfolio_state.total_pnl
            peak_equity = portfolio_state.peak_equity
            drawdown = portfolio_state.drawdown

            position = engine.get_runtime_position(self.symbol)

            if position is not None:
                active_position = PaperPositionSnapshot(
                    symbol=position.symbol,
                    direction=position.direction,
                    quantity=position.quantity,
                    entry_time=position.entry_time.isoformat(),
                    entry_price=position.entry_price,
                    stop_price=position.stop_price,
                )

            completed_trade_count = len(engine.completed_trades)
            most_recent_execution = getattr(
                engine,
                "most_recent_execution",
                None,
            )

            if most_recent_execution is None:
                last_execution_event = engine.last_execution_event
                last_execution_price = engine.last_execution_price
                last_execution_quantity = engine.last_execution_quantity
            else:
                (
                    last_execution_event,
                    last_execution_price,
                    last_execution_quantity,
                ) = most_recent_execution

        return PaperTradingSnapshot(
            session_id=self.session_id,
            status=self.status,
            strategy_name=self.strategy_name,
            symbol=self.symbol,
            started_at=(
                self.started_at.isoformat()
                if self.started_at is not None
                else None
            ),
            stopped_at=(
                self.stopped_at.isoformat()
                if self.stopped_at is not None
                else None
            ),
            initial_capital=self.initial_capital,
            cash=cash,
            position_size=position_size,
            position_value=position_value,
            equity=equity,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_pnl=total_pnl,
            peak_equity=peak_equity,
            drawdown=drawdown,
            active_position=active_position,
            completed_trade_count=completed_trade_count,
            last_execution_event=last_execution_event,
            last_execution_price=last_execution_price,
            last_execution_quantity=last_execution_quantity,
            failure_type=self.failure_type,
            failure_message=self.failure_message,
        )

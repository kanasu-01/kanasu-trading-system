from dataclasses import dataclass
from datetime import datetime
from typing import Any
from core.paper_trading.paper_trading_snapshot import (
    PaperTradingSnapshot,
)


@dataclass
class PaperTradingSession:
    """
    Runtime state of a paper trading session.

    Future:
    - Active position tracking
    - PnL tracking
    - Metrics tracking
    - Session persistence
    """

    session_id: str

    strategy_name: str

    symbol: str

    initial_capital: float

    status: str = "CREATED"

    started_at: datetime | None = None

    stopped_at: datetime | None = None

    feed: Any | None = None

    strategy: Any | None = None

    runtime_context: Any | None = None

    dataset_context: Any | None = None

    strategy_runner: Any | None = None

    execution_engine: Any | None = None

    def start(self) -> None:
        """
        Mark session as running.
        Runtime initialization will be added later.
        """

        self.status = "RUNNING"

        self.started_at = datetime.now()

    def stop(self) -> None:
        """
        Mark session as stopped.
        Runtime cleanup will be added later.
        """

        self.status = "STOPPED"

        self.stopped_at = datetime.now()

    def snapshot(self) -> PaperTradingSnapshot:
        """
        Return immutable runtime snapshot.
        """

        return PaperTradingSnapshot(
            status=self.status,
            strategy_name=self.strategy_name,
            symbol=self.symbol,
            started_at=(self.started_at.isoformat() if self.started_at else None),
        )

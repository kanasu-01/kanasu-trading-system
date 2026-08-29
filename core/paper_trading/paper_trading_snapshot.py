from dataclasses import dataclass


@dataclass(frozen=True)
class PaperTradingSnapshot:
    """
    Immutable snapshot of paper trading runtime state.

    Returned to API layer and UI consumers.
    """

    status: str

    strategy_name: str

    symbol: str

    started_at: str | None

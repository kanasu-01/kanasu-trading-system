from datetime import datetime
from typing import Optional

from core.entities.position import Position
from core.entities.trade import Trade


class TradeBuilder:

    @staticmethod
    def build_long_trade(
        position: Position,
        exit_price: float,
        exit_reason: str,
        exit_time: Optional[datetime],
        transaction_cost: float = 0.0,
    ) -> Trade:

        gross_pnl = (exit_price - position.entry_price) * position.quantity

        pnl = gross_pnl - transaction_cost

        pnl_pct = ((exit_price - position.entry_price) / position.entry_price) * 100

        return Trade(
            symbol=position.symbol,
            entry_time=position.entry_time,
            entry_price=position.entry_price,
            exit_time=exit_time,
            exit_price=exit_price,
            stop_price=position.stop_price,
            quantity=position.quantity,
            direction=position.direction,
            exit_reason=exit_reason,
            pnl=pnl,
            gross_pnl=gross_pnl,
            transaction_cost=transaction_cost,
            pnl_pct=pnl_pct,
        )

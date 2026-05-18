from typing import List
from core.entities.trade import Trade
from core.entities.trade import Trade


class PerformanceMetrics:
    """
    Computes performance statistics from completed trades.
    """

    @staticmethod
    def summarize(trades: List[Trade]) -> dict:
        if not trades:
            return {}

        total_trades = len(trades)

        wins = [t for t in trades if t.pnl > 0]
        losses = [t for t in trades if t.pnl <= 0]

        win_count = len(wins)
        loss_count = len(losses)

        win_rate = win_count / total_trades

        avg_win = sum(t.pnl_pct for t in wins) / win_count if win_count > 0 else 0.0

        avg_loss = (
            sum(t.pnl_pct for t in losses) / loss_count if loss_count > 0 else 0.0
        )

        # Expectancy = (Win% × AvgWin) + (Loss% × AvgLoss)
        expectancy = win_rate * avg_win + (1 - win_rate) * avg_loss

        max_drawdown = PerformanceMetrics._max_drawdown(trades)

        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate * 100, 2),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "expectancy_pct": round(expectancy, 2),
            "max_drawdown_pct": round(max_drawdown, 2),
        }

    @staticmethod
    def _max_drawdown(trades: List[Trade]) -> float:
        """
        Simple equity curve drawdown using % returns.
        """
        equity = 0.0
        peak = 0.0
        max_dd = 0.0

        for trade in trades:
            equity += trade.pnl_pct

            if equity > peak:
                peak = equity

            drawdown = equity - peak
            if drawdown < max_dd:
                max_dd = drawdown

        return abs(max_dd)

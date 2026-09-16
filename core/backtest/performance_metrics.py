from math import fsum, isfinite
from typing import List

from core.backtest.backtest_result import BacktestResult
from core.entities.trade import Trade


class PerformanceMetrics:
    """
    Computes authoritative Backtest and legacy trade-only statistics.
    """

    @staticmethod
    def summarize_backtest(result: BacktestResult) -> dict:
        """Summarize completed trades and authoritative recorded equity."""

        trades = result.trades
        equity_values = PerformanceMetrics._validated_equity_values(result)

        total_trades = len(trades)
        profitable_trades = [trade for trade in trades if trade.pnl > 0]
        losing_trades = [trade for trade in trades if trade.pnl < 0]
        breakeven_trades = [trade for trade in trades if trade.pnl == 0]
        positive_instrument_returns = [
            trade.pnl_pct for trade in trades if trade.pnl_pct > 0
        ]
        negative_instrument_returns = [
            trade.pnl_pct for trade in trades if trade.pnl_pct < 0
        ]

        gross_realized_pnl = fsum(trade.gross_pnl for trade in trades)
        net_realized_pnl = fsum(trade.pnl for trade in trades)
        completed_trade_transaction_cost_total = fsum(
            trade.transaction_cost for trade in trades
        )

        if equity_values:
            starting_equity = equity_values[0]
            ending_equity = equity_values[-1]
            account_pnl = ending_equity - starting_equity
            account_return_pct = account_pnl / starting_equity * 100
            max_equity_drawdown_pct = PerformanceMetrics._max_equity_drawdown(
                equity_values
            )
        else:
            account_pnl = 0.0
            account_return_pct = 0.0
            max_equity_drawdown_pct = 0.0

        return {
            "completed_trade_count": total_trades,
            "net_profitable_trade_count": len(profitable_trades),
            "net_losing_trade_count": len(losing_trades),
            "net_breakeven_trade_count": len(breakeven_trades),
            "net_profitable_trade_rate_pct": (
                len(profitable_trades) / total_trades * 100
                if total_trades
                else 0.0
            ),
            "mean_positive_instrument_return_pct": (
                fsum(positive_instrument_returns)
                / len(positive_instrument_returns)
                if positive_instrument_returns
                else 0.0
            ),
            "mean_negative_instrument_return_pct": (
                fsum(negative_instrument_returns)
                / len(negative_instrument_returns)
                if negative_instrument_returns
                else 0.0
            ),
            "mean_instrument_return_pct": (
                fsum(trade.pnl_pct for trade in trades) / total_trades
                if total_trades
                else 0.0
            ),
            "gross_realized_pnl": gross_realized_pnl,
            "net_realized_pnl": net_realized_pnl,
            "mean_net_pnl_per_completed_trade": (
                net_realized_pnl / total_trades if total_trades else 0.0
            ),
            "completed_trade_transaction_cost_total": (
                completed_trade_transaction_cost_total
            ),
            "account_pnl": account_pnl,
            "account_return_pct": account_return_pct,
            "max_equity_drawdown_pct": max_equity_drawdown_pct,
        }

    @staticmethod
    def _validated_equity_values(result: BacktestResult) -> List[float]:
        if not result.bar_records:
            if result.trades:
                raise ValueError(
                    "Backtest trades require authoritative equity records"
                )
            return []

        equity_values = []
        for index, record in enumerate(result.bar_records):
            try:
                equity = float(record.equity)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Backtest equity at index {index} must be finite"
                ) from exc

            if not isfinite(equity):
                raise ValueError(
                    f"Backtest equity at index {index} must be finite"
                )

            equity_values.append(equity)

        if equity_values[0] <= 0:
            raise ValueError("Backtest starting equity must be strictly positive")

        return equity_values

    @staticmethod
    def _max_equity_drawdown(equity_values: List[float]) -> float:
        peak = equity_values[0]
        max_drawdown = 0.0

        for equity in equity_values:
            peak = max(peak, equity)
            drawdown = (peak - equity) / peak * 100
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown

    @staticmethod
    def summarize(trades: List[Trade]) -> dict:
        """Return the legacy trade-only summary retained for WFA callers."""

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

        total_transaction_cost = sum(t.transaction_cost for t in trades)

        gross_pnl = sum(t.gross_pnl for t in trades)

        net_pnl = sum(t.pnl for t in trades)

        return {
            "total_trades": total_trades,
            "win_rate": round(win_rate * 100, 2),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "expectancy_pct": round(expectancy, 2),
            "gross_pnl": round(gross_pnl, 2),
            "net_pnl": round(net_pnl, 2),
            "total_transaction_cost": round(
                total_transaction_cost,
                2,
            ),
            "max_drawdown_pct": round(max_drawdown, 2),
        }

    @staticmethod
    def _max_drawdown(trades: List[Trade]) -> float:
        """
        Simple equity curve drawdown using % returns.
        """
        equity = 1.0
        peak = 1.0
        max_dd = 0.0

        for trade in trades:
            equity *= 1 + (trade.pnl_pct / 100)

            if equity > peak:
                peak = equity

            drawdown = (equity - peak) / peak

            if drawdown < max_dd:
                max_dd = drawdown

        return abs(max_dd) * 100

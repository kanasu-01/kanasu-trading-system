from typing import List, Dict


class RiskMetrics:
    """
    Risk-adjusted performance metrics.
    STEP 7.5: R-multiple based evaluation.
    """

    @staticmethod
    def compute_r_multiple(
        entry_price: float,
        exit_price: float,
        stop_price: float,
        direction: str = "LONG",
    ) -> float:
        """
        Compute R-multiple for a trade.
        """

        if direction != "LONG":
            raise NotImplementedError("Only LONG trades supported")

        initial_risk = entry_price - stop_price
        if initial_risk <= 0:
            return 0.0

        reward = exit_price - entry_price
        return reward / initial_risk

    @staticmethod
    def summarize(trades: List[Dict]) -> Dict:
        """
        Summarize R-multiple statistics.
        Expects each trade to have:
        - entry_price
        - exit_price
        - stop_price
        """

        r_values = []

        for trade in trades:
            r = RiskMetrics.compute_r_multiple(
                entry_price=trade["entry_price"],
                exit_price=trade["exit_price"],
                stop_price=trade["stop_price"],
            )
            trade["r_multiple"] = round(r, 2)
            r_values.append(r)

        if not r_values:
            return {}

        avg_r = sum(r_values) / len(r_values)

        wins = [r for r in r_values if r > 0]
        losses = [r for r in r_values if r <= 0]

        expectancy_r = (
            (len(wins) / len(r_values)) * (sum(wins) / len(wins))
            + (len(losses) / len(r_values)) * (sum(losses) / len(losses))
            if losses else avg_r
        )

        max_r_drawdown = RiskMetrics._max_r_drawdown(r_values)

        return {
            "total_trades": len(r_values),
            "avg_r": round(avg_r, 2),
            "expectancy_r": round(expectancy_r, 2),
            "best_r": round(max(r_values), 2),
            "worst_r": round(min(r_values), 2),
            "max_r_drawdown": round(max_r_drawdown, 2),
        }

    @staticmethod
    def _max_r_drawdown(r_values: List[float]) -> float:
        """
        Max drawdown calculated on cumulative R curve.
        """

        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0

        for r in r_values:
            cumulative += r
            if cumulative > peak:
                peak = cumulative
            dd = cumulative - peak
            if dd < max_dd:
                max_dd = dd

        return abs(max_dd)

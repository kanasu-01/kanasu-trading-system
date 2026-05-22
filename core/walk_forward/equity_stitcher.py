from typing import List, Tuple
from datetime import datetime
from typing import Any


class EquityStitcher:
    """
    Builds a continuous stitched OOS equity curve
    from walk-forward window results.
    """

    @staticmethod
    def stitch(
        windows: List[Any],
    ) -> List[Tuple[datetime, float]]:
        """
        Returns:
            List of (timestamp, stitched_equity)
        """

        if not windows:
            return []

        stitched_curve: List[Tuple[datetime, float]] = []

        capital_base = None

        for window in windows:

            equity_curve = window.backtest_result.equity_curve

            if not equity_curve:
                continue

            # -----------------------------------------
            # Initialize starting capital
            # -----------------------------------------
            if capital_base is None:
                capital_base = equity_curve[0][1]

            window_start_equity = equity_curve[0][1]

            # Prevent division issues
            if window_start_equity == 0:
                continue

            # -----------------------------------------
            # Normalize + compound
            # -----------------------------------------
            for timestamp, equity in equity_curve:

                normalized_equity = equity / window_start_equity

                stitched_equity = capital_base * normalized_equity

                stitched_curve.append((timestamp, stitched_equity))

            # -----------------------------------------
            # Update rolling capital base
            # -----------------------------------------
            capital_base = stitched_curve[-1][1]

        return stitched_curve

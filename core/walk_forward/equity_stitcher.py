from datetime import datetime
from math import isfinite
from typing import Any, List, Tuple


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
        last_timestamp = None

        for window in windows:
            equity_curve = window.backtest_result.equity_curve
            window_index = getattr(
                window,
                "window_index",
                "unknown",
            )

            if not equity_curve:
                raise ValueError(
                    f"WFA window {window_index} requires "
                    f"OOS equity records"
                )

            try:
                window_start_equity = float(
                    equity_curve[0][1]
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"WFA window {window_index} starting "
                    f"equity must be finite"
                ) from exc

            if not isfinite(window_start_equity):
                raise ValueError(
                    f"WFA window {window_index} starting "
                    f"equity must be finite"
                )

            if window_start_equity <= 0:
                raise ValueError(
                    f"WFA window {window_index} starting "
                    f"equity must be strictly positive"
                )

            if capital_base is not None and capital_base <= 0:
                raise ValueError(
                    "WFA stitching cannot continue after "
                    "non-positive equity"
                )

            window_capital_base = (
                window_start_equity
                if capital_base is None
                else capital_base
            )

            for point_index, (timestamp, raw_equity) in enumerate(
                equity_curve
            ):
                if not isinstance(timestamp, datetime):
                    raise TypeError(
                        "WFA equity timestamps must be datetime values"
                    )

                try:
                    equity = float(raw_equity)
                except (TypeError, ValueError) as exc:
                    raise ValueError(
                        f"WFA window {window_index} equity at "
                        f"index {point_index} must be finite"
                    ) from exc

                if not isfinite(equity):
                    raise ValueError(
                        f"WFA window {window_index} equity at "
                        f"index {point_index} must be finite"
                    )

                if last_timestamp is not None:
                    try:
                        non_increasing = timestamp <= last_timestamp
                    except TypeError as exc:
                        raise ValueError(
                            "WFA OOS equity timestamps must "
                            "be comparable"
                        ) from exc

                    if non_increasing:
                        raise ValueError(
                            "WFA OOS equity timestamps must be "
                            "strictly increasing and non-overlapping"
                        )

                stitched_equity = (
                    window_capital_base
                    * (equity / window_start_equity)
                )

                if not isfinite(stitched_equity):
                    raise ValueError(
                        "stitched WFA equity must be finite"
                    )

                stitched_curve.append(
                    (timestamp, stitched_equity)
                )
                last_timestamp = timestamp

            capital_base = stitched_curve[-1][1]

        return stitched_curve

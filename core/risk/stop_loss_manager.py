from typing import Optional


class StopLossManager:
    """
    Structure-based stop-loss logic.
    STEP 7.2: Defines where the trade idea is invalidated.
    """

    def __init__(
        self,
        buffer_pct: float = 0.2,
        min_tick: float = 0.05,
    ):
        """
        :param buffer_pct: Extra buffer below structure (%)
        :param min_tick: Minimum price tick (exchange dependent)
        """
        self.buffer_pct = buffer_pct
        self.min_tick = min_tick

    def compute_long_stop(
        self,
        rejection_midpoint: Optional[float],
    ) -> Optional[float]:
        """
        Stop-loss for long trades.
        """

        if rejection_midpoint is None:
            return None

        stop = rejection_midpoint * (1 - self.buffer_pct / 100)

        # Round to tick
        stop = round(stop / self.min_tick) * self.min_tick

        return stop

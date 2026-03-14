from dataclasses import dataclass
from typing import List, Iterator, Tuple, Literal

from core.entities.candle import Candle


# ==========================================================
# WALK-FORWARD WINDOW
# ==========================================================

@dataclass(frozen=True)
class WalkForwardWindow:
    """
    Represents a single walk-forward window.
    """
    train_bars: List[Candle]
    test_bars: List[Candle]
    window_index: int


# ==========================================================
# WINDOW GENERATOR
# ==========================================================

class WalkForwardWindowGenerator:
    """
    Generates walk-forward train/test windows from candles.

    Strategy-agnostic.
    Backtest-agnostic.
    """

    def __init__(
        self,
        in_sample_bars: int,
        out_sample_bars: int,
        step_bars: int,
        mode: Literal["rolling", "expanding"] = "rolling",
    ):
        if in_sample_bars <= 0:
            raise ValueError("in_sample_bars must be > 0")

        if out_sample_bars <= 0:
            raise ValueError("out_sample_bars must be > 0")

        if step_bars <= 0:
            raise ValueError("step_bars must be > 0")

        if mode not in ("rolling", "expanding"):
            raise ValueError("mode must be 'rolling' or 'expanding'")

        self.in_sample_bars = in_sample_bars
        self.out_sample_bars = out_sample_bars
        self.step_bars = step_bars
        self.mode = mode

    # ------------------------------------------------------
    # Public API
    # ------------------------------------------------------

    def generate(
        self,
        candles: List[Candle],
    ) -> Iterator[WalkForwardWindow]:
        """
        Yield walk-forward windows.
        """

        total_bars = len(candles)

        start = 0
        window_index = 0

        while True:
            if self.mode == "rolling":
                train_start = start
            else:  # expanding
                train_start = 0

            train_end = train_start + self.in_sample_bars
            test_end = train_end + self.out_sample_bars

            if test_end > total_bars:
                break

            train_bars = candles[train_start:train_end]
            test_bars = candles[train_end:test_end]

            yield WalkForwardWindow(
                train_bars=train_bars,
                test_bars=test_bars,
                window_index=window_index,
            )

            start += self.step_bars
            window_index += 1

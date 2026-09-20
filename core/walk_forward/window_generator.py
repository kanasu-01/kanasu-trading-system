from dataclasses import dataclass, field
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
    train_history_bars: List[Candle] = field(
        default_factory=list
    )
    test_history_bars: List[Candle] = field(
        default_factory=list
    )


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
        *,
        prehistory_bars: int = 0,
    ) -> Iterator[WalkForwardWindow]:
        """
        Yield walk-forward windows.

        prehistory_bars are strictly before each scored
        interval and are never part of its result metrics.
        """

        if (
            not isinstance(prehistory_bars, int)
            or isinstance(prehistory_bars, bool)
            or prehistory_bars < 0
        ):
            raise ValueError(
                "prehistory_bars must be a non-negative integer"
            )

        total_bars = len(candles)

        start = 0
        window_index = 0

        while True:
            if self.mode == "rolling":
                train_start = prehistory_bars + start
                train_end = (
                    train_start + self.in_sample_bars
                )
            else:  # expanding
                train_start = prehistory_bars
                train_end = (
                    train_start
                    + self.in_sample_bars
                    + start
                )

            test_end = train_end + self.out_sample_bars

            if test_end > total_bars:
                break

            train_history_start = (
                train_start - prehistory_bars
            )
            test_history_start = max(
                0,
                train_end - prehistory_bars,
            )

            train_history_bars = candles[
                train_history_start:train_start
            ]
            train_bars = candles[
                train_start:train_end
            ]
            test_history_bars = candles[
                test_history_start:train_end
            ]
            test_bars = candles[
                train_end:test_end
            ]

            yield WalkForwardWindow(
                train_bars=train_bars,
                test_bars=test_bars,
                window_index=window_index,
                train_history_bars=train_history_bars,
                test_history_bars=test_history_bars,
            )

            start += self.step_bars
            window_index += 1

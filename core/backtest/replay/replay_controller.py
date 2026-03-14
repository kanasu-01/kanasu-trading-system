import time
from typing import List, Optional, Callable

from core.backtest.bar_record import BarRecord


class ReplayController:
    """
    Controls bar-by-bar replay over recorded BarRecords.
    Strategy-agnostic and UI-agnostic.
    """

    def __init__(
        self,
        records: List[BarRecord],
        on_step: Optional[Callable[[BarRecord, int], None]] = None,
    ):
        if not records:
            raise ValueError("ReplayController requires BarRecords")

        self.records = records
        self.on_step = on_step  # callback per bar

        self.current_index: int = -1
        self.is_playing: bool = False
        self.play_delay_sec: float = 0.5  # default speed

    # -------------------------------------------------
    # Core controls
    # -------------------------------------------------

    def reset(self) -> None:
        self.pause()
        self.current_index = -1

    def step(self) -> Optional[BarRecord]:
        """
        Advance by one bar.
        """
        if self.current_index + 1 >= len(self.records):
            self.pause()
            return None

        self.current_index += 1
        record = self.records[self.current_index]

        if self.on_step:
            self.on_step(record, self.current_index)

        return record

    def play(self, delay_sec: Optional[float] = None) -> None:
        """
        Start auto-replay.
        """
        if delay_sec is not None:
            self.play_delay_sec = delay_sec

        self.is_playing = True

        while self.is_playing:
            record = self.step()
            if record is None:
                break
            time.sleep(self.play_delay_sec)

    def pause(self) -> None:
        """
        Pause auto-replay.
        """
        self.is_playing = False

    # -------------------------------------------------
    # Helpers
    # -------------------------------------------------

    def has_next(self) -> bool:
        return self.current_index + 1 < len(self.records)

    def current_record(self) -> Optional[BarRecord]:
        if self.current_index < 0:
            return None
        return self.records[self.current_index]
    
    

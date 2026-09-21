from dataclasses import dataclass
from datetime import datetime, time


@dataclass(frozen=True)
class LivePaperSessionWindow:
    start: datetime
    end: datetime


def resolve_live_paper_session_window(
    *,
    current_time: datetime,
    session_start: time,
    session_end: time,
) -> LivePaperSessionWindow:
    """Resolve and validate one same-day live paper session window."""

    if (
        current_time.tzinfo is None
        or current_time.utcoffset() is None
    ):
        raise ValueError(
            "Live paper current time must be timezone-aware"
        )

    if session_start >= session_end:
        raise ValueError(
            "Live paper session start must be before session end"
        )

    start = current_time.replace(
        hour=session_start.hour,
        minute=session_start.minute,
        second=session_start.second,
        microsecond=session_start.microsecond,
    )
    end = current_time.replace(
        hour=session_end.hour,
        minute=session_end.minute,
        second=session_end.second,
        microsecond=session_end.microsecond,
    )

    if current_time < start:
        raise RuntimeError(
            "Live paper session has not started"
        )

    if current_time >= end:
        raise RuntimeError(
            "Live paper session has already ended"
        )

    return LivePaperSessionWindow(
        start=start,
        end=end,
    )

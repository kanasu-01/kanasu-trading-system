from datetime import datetime, time

import pytest
import pytz

from core.runtime.live_paper_session import (
    resolve_live_paper_session_window,
)


IST = pytz.timezone("Asia/Kolkata")


def _ts(hour: int, minute: int):
    return IST.localize(
        datetime(
            2026,
            1,
            2,
            hour,
            minute,
        )
    )


def test_live_paper_session_window_uses_current_session_date_and_timezone():
    current = _ts(10, 0)

    window = resolve_live_paper_session_window(
        current_time=current,
        session_start=time(9, 15),
        session_end=time(15, 30),
    )

    assert window.start == _ts(9, 15)
    assert window.end == _ts(15, 30)
    assert window.start.tzinfo == current.tzinfo
    assert window.end.tzinfo == current.tzinfo


def test_live_paper_session_rejects_start_before_session_open():
    with pytest.raises(
        RuntimeError,
        match="has not started",
    ):
        resolve_live_paper_session_window(
            current_time=_ts(9, 14),
            session_start=time(9, 15),
            session_end=time(15, 30),
        )


def test_live_paper_session_rejects_start_at_or_after_session_close():
    for current in (
        _ts(15, 30),
        _ts(16, 0),
    ):
        with pytest.raises(
            RuntimeError,
            match="already ended",
        ):
            resolve_live_paper_session_window(
                current_time=current,
                session_start=time(9, 15),
                session_end=time(15, 30),
            )


def test_live_paper_session_rejects_invalid_configured_window():
    with pytest.raises(
        ValueError,
        match="start must be before session end",
    ):
        resolve_live_paper_session_window(
            current_time=_ts(10, 0),
            session_start=time(15, 30),
            session_end=time(9, 15),
        )

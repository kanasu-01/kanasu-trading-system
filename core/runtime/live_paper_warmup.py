from datetime import datetime, timedelta

from core.config.app_config import AppConfig
from core.market_data.historical_coverage import TimeRange
from core.runtime.dataset_context import DatasetContext


_LIVE_TIMEFRAME_MINUTES = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "10m": 10,
    "15m": 15,
    "30m": 30,
    "1h": 60,
}


def load_live_paper_warmup(
    *,
    app_config: AppConfig,
    historical_source,
    strategy,
    dataset_context: DatasetContext,
    current_time: datetime,
    session_start: datetime,
) -> list:
    """Load the accepted M7 strategy warm-up before live paper execution."""

    warmup_method = getattr(
        strategy,
        "warmup_bars",
        None,
    )
    warmup_bars = (
        warmup_method()
        if callable(warmup_method)
        else 0
    )

    if (
        isinstance(warmup_bars, bool)
        or not isinstance(warmup_bars, int)
        or warmup_bars < 0
    ):
        raise ValueError(
            "strategy warmup_bars must be a non-negative integer"
        )

    if warmup_bars == 0:
        return []

    timeframe = dataset_context.timeframe
    if timeframe not in _LIVE_TIMEFRAME_MINUTES:
        raise ValueError(
            f"unsupported live warm-up timeframe: {timeframe}"
        )

    session_start_wall = app_config.paper_session_start
    session_end_wall = app_config.paper_session_end

    start_seconds = (
        session_start_wall.hour * 3600
        + session_start_wall.minute * 60
        + session_start_wall.second
    )
    end_seconds = (
        session_end_wall.hour * 3600
        + session_end_wall.minute * 60
        + session_end_wall.second
    )
    session_minutes = (
        end_seconds - start_seconds
    ) // 60

    timeframe_minutes = (
        _LIVE_TIMEFRAME_MINUTES[timeframe]
    )

    interval = timedelta(
        minutes=timeframe_minutes,
    )
    elapsed = current_time - session_start

    if elapsed.total_seconds() < 0:
        raise RuntimeError(
            "live paper warm-up cannot precede session start"
        )

    bucket_index = int(
        elapsed.total_seconds()
        // interval.total_seconds()
    )
    history_end = (
        session_start
        + interval * bucket_index
    )

    bars_per_session = max(
        1,
        session_minutes // timeframe_minutes,
    )
    required_sessions = (
        warmup_bars + bars_per_session - 1
    ) // bars_per_session

    lookback_days = max(
        7,
        required_sessions * 2 + 2,
    )

    request = TimeRange(
        start=(
            history_end
            - timedelta(days=lookback_days)
        ),
        end=history_end,
    )

    history = historical_source.retrieve(
        dataset_context,
        request,
    )

    if len(history) < warmup_bars:
        raise RuntimeError(
            "insufficient historical warm-up for live paper strategy: "
            f"required={warmup_bars}, available={len(history)}"
        )

    return history[-warmup_bars:]

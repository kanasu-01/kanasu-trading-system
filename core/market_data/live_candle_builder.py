from datetime import datetime, time, timedelta

from core.entities.candle import Candle
from core.market_data.live_market_update import LiveMarketUpdate


_TIMEFRAME_MINUTES = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "10m": 10,
    "15m": 15,
    "30m": 30,
    "1h": 60,
}


class LiveCandleBuilder:
    """
    Session-scoped live update to completed-candle builder.

    The first observed mid-session candle is intentionally treated as
    partial and is never emitted. Once its boundary has passed, subsequent
    observed candles are eligible for completed delivery.

    No synthetic candle is created for an interval with no market updates.
    """

    def __init__(
        self,
        timeframe: str,
        session_start: time,
        allow_first_boundary_candle: bool = True,
    ) -> None:
        if timeframe not in _TIMEFRAME_MINUTES:
            raise ValueError(f"unsupported live timeframe: {timeframe}")

        if session_start.tzinfo is not None:
            raise ValueError("session_start must be a timezone-naive wall time")

        self.timeframe = timeframe
        self.session_start = session_start
        self._allow_first_boundary_candle = allow_first_boundary_candle
        self._interval = timedelta(minutes=_TIMEFRAME_MINUTES[timeframe])

        self._timezone = None
        self._session_date = None
        self._watermark: datetime | None = None
        self._last_update: LiveMarketUpdate | None = None

        self._active_start: datetime | None = None
        self._active_end: datetime | None = None
        self._active_open: float | None = None
        self._active_high: float | None = None
        self._active_low: float | None = None
        self._active_close: float | None = None
        self._active_volume = 0.0
        self._active_eligible = False

        self._warmed = False

    def on_update(self, update: LiveMarketUpdate) -> Candle | None:
        """
        Accept one ordered live update.

        Returns a completed candle only when this update crosses the active
        candle boundary. The update itself belongs to the new interval.
        """
        if self._last_update is not None:
            if update.sequence == self._last_update.sequence:
                if update == self._last_update:
                    return None
                raise ValueError(
                    "conflicting live update for previously accepted sequence"
                )

            if update.sequence < self._last_update.sequence:
                raise ValueError(
                    "live update sequence is older than the latest accepted update"
                )

        bucket_start, bucket_end, session_anchor = self._bucket_bounds(
            update.timestamp
        )

        if (
            self._timezone is not None
            and update.timestamp.tzinfo != self._timezone
        ):
            raise ValueError("live update timezone must remain consistent")

        if (
            self._session_date is not None
            and update.timestamp.date() != self._session_date
        ):
            raise ValueError(
                "live candle builder is scoped to one trading session"
            )

        if (
            self._watermark is not None
            and update.timestamp < self._watermark
        ):
            raise ValueError(
                "live update event time is older than the current watermark"
            )

        if (
            self._last_update is not None
            and update.cumulative_volume
            < self._last_update.cumulative_volume
        ):
            raise ValueError(
                "live cumulative volume cannot decrease within a session"
            )

        if self._last_update is None:
            if update.timestamp == session_anchor:
                volume_delta = update.cumulative_volume
            else:
                volume_delta = 0.0
        else:
            volume_delta = (
                update.cumulative_volume
                - self._last_update.cumulative_volume
            )

        completed = None

        if (
            self._active_end is not None
            and update.timestamp >= self._active_end
        ):
            completed = self._finish_active()
            self._clear_active()
            self._warmed = True

        if self._active_start is None:
            first_observation_on_boundary = (
                self._last_update is None
                and update.timestamp == bucket_start
            )
            eligible = self._warmed or (
                self._allow_first_boundary_candle
                and first_observation_on_boundary
            )

            self._start_active(
                start=bucket_start,
                end=bucket_end,
                price=update.price,
                volume_delta=volume_delta,
                eligible=eligible,
            )
        else:
            if bucket_start != self._active_start:
                raise RuntimeError(
                    "live candle builder active interval does not match "
                    "incoming update interval"
                )

            self._apply_update(
                price=update.price,
                volume_delta=volume_delta,
            )

        if self._timezone is None:
            self._timezone = update.timestamp.tzinfo

        if self._session_date is None:
            self._session_date = update.timestamp.date()

        self._last_update = update
        self._watermark = update.timestamp

        return completed

    def advance_time(self, timestamp: datetime) -> Candle | None:
        """
        Advance the live clock without fabricating market updates.

        If the active interval has ended, its candle is completed. No new
        candle is created until a real market update arrives.
        """
        if timestamp.utcoffset() is None:
            raise ValueError("live clock timestamp must be timezone-aware")

        if self._timezone is not None and timestamp.tzinfo != self._timezone:
            raise ValueError("live clock timezone must remain consistent")

        if (
            self._session_date is not None
            and timestamp.date() != self._session_date
        ):
            raise ValueError(
                "live candle builder is scoped to one trading session"
            )

        if self._watermark is not None and timestamp < self._watermark:
            raise ValueError(
                "live clock cannot move behind the current watermark"
            )

        if self._timezone is None:
            self._timezone = timestamp.tzinfo

        self._watermark = timestamp

        if self._active_end is None or timestamp < self._active_end:
            return None

        completed = self._finish_active()
        self._clear_active()
        self._warmed = True
        return completed

    def _bucket_bounds(
        self,
        timestamp: datetime,
    ) -> tuple[datetime, datetime, datetime]:
        session_anchor = timestamp.replace(
            hour=self.session_start.hour,
            minute=self.session_start.minute,
            second=self.session_start.second,
            microsecond=self.session_start.microsecond,
        )

        if timestamp < session_anchor:
            raise ValueError("live update arrived before the trading session")

        elapsed = timestamp - session_anchor
        interval_seconds = self._interval.total_seconds()
        bucket_index = int(elapsed.total_seconds() // interval_seconds)

        start = session_anchor + (self._interval * bucket_index)
        end = start + self._interval
        return start, end, session_anchor

    def _start_active(
        self,
        start: datetime,
        end: datetime,
        price: float,
        volume_delta: float,
        eligible: bool,
    ) -> None:
        self._active_start = start
        self._active_end = end
        self._active_open = price
        self._active_high = price
        self._active_low = price
        self._active_close = price
        self._active_volume = volume_delta
        self._active_eligible = eligible

    def _apply_update(
        self,
        price: float,
        volume_delta: float,
    ) -> None:
        if (
            self._active_high is None
            or self._active_low is None
        ):
            raise RuntimeError("live candle builder has no active candle")

        self._active_high = max(self._active_high, price)
        self._active_low = min(self._active_low, price)
        self._active_close = price
        self._active_volume += volume_delta

    def _finish_active(self) -> Candle | None:
        if self._active_start is None:
            return None

        if not self._active_eligible:
            return None

        if (
            self._active_open is None
            or self._active_high is None
            or self._active_low is None
            or self._active_close is None
        ):
            raise RuntimeError("live candle builder active candle is incomplete")

        return Candle(
            timestamp=self._active_start,
            open=self._active_open,
            high=self._active_high,
            low=self._active_low,
            close=self._active_close,
            volume=self._active_volume,
        )

    def _clear_active(self) -> None:
        self._active_start = None
        self._active_end = None
        self._active_open = None
        self._active_high = None
        self._active_low = None
        self._active_close = None
        self._active_volume = 0.0
        self._active_eligible = False

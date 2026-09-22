from datetime import datetime, time

from core.entities.candle import Candle
from core.market_data.completed_candle_delivery import (
    CompletedCandleDelivery,
)
from core.market_data.live_candle_builder import LiveCandleBuilder
from core.market_data.live_market_update import LiveMarketUpdate


class LiveCandlePipeline:
    """
    Session-scoped live update to validated completed-candle pipeline.

    Connection epochs intentionally use fresh LiveCandleBuilder instances.
    Event-time, session, timezone, cumulative-volume, and completed-candle
    validity remain continuous across reconnects.
    """

    def __init__(
        self,
        timeframe: str,
        session_start: time,
    ) -> None:
        self.timeframe = timeframe
        self.session_start = session_start

        self._delivery = CompletedCandleDelivery()
        self._builder: LiveCandleBuilder | None = None

        self._connected = False
        self._ever_connected = False

        self._timezone = None
        self._session_date = None
        self._watermark: datetime | None = None
        self._latest_update: LiveMarketUpdate | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    def begin_connection(self) -> None:
        """
        Begin a new provider connection epoch.

        The initial epoch preserves normal cold-start semantics. Every later
        epoch suppresses its first observed interval even when the first tick
        lands exactly on a candle boundary.
        """
        if self._connected:
            raise RuntimeError(
                "live candle pipeline connection is already active"
            )

        self._builder = LiveCandleBuilder(
            timeframe=self.timeframe,
            session_start=self.session_start,
            allow_first_boundary_candle=not self._ever_connected,
        )

        self._connected = True
        self._ever_connected = True

    def mark_disconnected(self) -> None:
        """
        Invalidate the active connection epoch.

        Any active candle is discarded because its provider interval is no
        longer known to be complete.
        """
        self._connected = False
        self._builder = None

    def on_update(
        self,
        update: LiveMarketUpdate,
    ) -> Candle | None:
        candle, _accepted = (
            self.on_update_with_acceptance(update)
        )
        return candle

    def on_update_with_acceptance(
        self,
        update: LiveMarketUpdate,
    ) -> tuple[Candle | None, bool]:
        """
        Accept one source observation while preserving the legacy result.

        The boolean distinguishes an accepted update from an exact
        retransmission. Interval-transition identity is available through
        on_update_with_transition().
        """
        completed, accepted, _opens_new_interval = (
            self.on_update_with_transition(update)
        )
        return completed, accepted

    def on_update_with_transition(
        self,
        update: LiveMarketUpdate,
    ) -> tuple[Candle | None, bool, bool]:
        """
        Accept one source observation and expose interval transition state.

        Returns:
            completed candle, accepted flag, opens-new-interval flag.

        The transition flag derives from accepted provider-event interval
        state, independently of whether the preceding candle is eligible
        for completed delivery.
        """
        if not self._connected or self._builder is None:
            raise RuntimeError(
                "live market update received without an active connection"
            )

        # An exact retransmission of the latest accepted source update is
        # idempotent even when it appears immediately after reconnect.
        if (
            self._latest_update is not None
            and update == self._latest_update
        ):
            return None, False, False

        self._validate_timestamp(update.timestamp)

        if (
            self._latest_update is not None
            and update.cumulative_volume
            < self._latest_update.cumulative_volume
        ):
            raise ValueError(
                "live cumulative volume cannot decrease across connections"
            )

        previous_interval_start = (
            self._builder.active_start
        )

        completed = self._builder.on_update(update)

        current_interval_start = (
            self._builder.active_start
        )
        opens_new_interval = (
            current_interval_start is not None
            and current_interval_start
            != previous_interval_start
        )

        self._record_timestamp(update.timestamp)
        self._latest_update = update

        return (
            self._accept_completed(completed),
            True,
            opens_new_interval,
        )

    def advance_time(
        self,
        timestamp: datetime,
    ) -> Candle | None:
        """
        Observe the caller wall clock without changing source-event ordering.

        Exchange-event timestamps are the only authority for intraday candle
        completion and the source watermark. The caller clock owns session
        lifecycle only; transport latency must not make a legitimate source
        update stale or prematurely finalize a candle.
        """
        self._validate_clock_timestamp(timestamp)
        return None

    def _validate_clock_timestamp(
        self,
        timestamp: datetime,
    ) -> None:
        if timestamp.utcoffset() is None:
            raise ValueError(
                "live pipeline clock timestamp must be timezone-aware"
            )

        if (
            self._timezone is not None
            and timestamp.tzinfo != self._timezone
        ):
            raise ValueError(
                "live pipeline timezone must remain consistent"
            )

        if (
            self._session_date is not None
            and timestamp.date() != self._session_date
        ):
            raise ValueError(
                "live pipeline is scoped to one trading session"
            )

    def _validate_timestamp(
        self,
        timestamp: datetime,
    ) -> None:
        if timestamp.utcoffset() is None:
            raise ValueError(
                "live pipeline timestamp must be timezone-aware"
            )

        if (
            self._timezone is not None
            and timestamp.tzinfo != self._timezone
        ):
            raise ValueError(
                "live pipeline timezone must remain consistent"
            )

        if (
            self._session_date is not None
            and timestamp.date() != self._session_date
        ):
            raise ValueError(
                "live pipeline is scoped to one trading session"
            )

        if (
            self._watermark is not None
            and timestamp < self._watermark
        ):
            raise ValueError(
                "live pipeline timestamp is older than the current watermark"
            )

    def _record_timestamp(
        self,
        timestamp: datetime,
    ) -> None:
        if self._timezone is None:
            self._timezone = timestamp.tzinfo

        if self._session_date is None:
            self._session_date = timestamp.date()

        self._watermark = timestamp

    def _accept_completed(
        self,
        candle: Candle | None,
    ) -> Candle | None:
        if candle is None:
            return None

        if not self._delivery.accept(candle):
            return None

        return candle

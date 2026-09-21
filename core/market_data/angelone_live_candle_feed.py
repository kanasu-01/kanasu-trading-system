import threading
from datetime import datetime, time

from core.broker.angelone_config import AngelOneConfig
from core.entities.candle import Candle
from core.market_data.angelone_live_market_data import (
    AngelOneLiveMarketDataAdapter,
    WebSocketFactory,
)
from core.market_data.live_candle_feed import (
    CompletedCandleHandler,
    LiveCandleFeed,
    LiveMarketUpdateHandler,
)
from core.market_data.live_candle_pipeline import LiveCandlePipeline
from core.market_data.live_market_update import LiveMarketUpdate


class AngelOneLiveCandleFeed(LiveCandleFeed):
    """
    AngelOne provider-to-completed-candle feed.

    Runtime thread ownership and automatic retry policy are intentionally
    deferred to M7.
    """

    def __init__(
        self,
        config: AngelOneConfig,
        auth_token: str,
        feed_token: str,
        symbol: str,
        timeframe: str,
        session_start: time,
        websocket_factory: WebSocketFactory | None = None,
    ) -> None:
        self._pipeline = LiveCandlePipeline(
            timeframe=timeframe,
            session_start=session_start,
        )
        self._pipeline_lock = threading.RLock()

        self._on_candle: CompletedCandleHandler | None = None
        self._on_market_update: LiveMarketUpdateHandler | None = None

        if websocket_factory is None:
            self._adapter = AngelOneLiveMarketDataAdapter(
                config=config,
                auth_token=auth_token,
                feed_token=feed_token,
                symbol=symbol,
                on_update=self._handle_update,
                on_disconnect=self._handle_disconnect,
            )
        else:
            self._adapter = AngelOneLiveMarketDataAdapter(
                config=config,
                auth_token=auth_token,
                feed_token=feed_token,
                symbol=symbol,
                on_update=self._handle_update,
                websocket_factory=websocket_factory,
                on_disconnect=self._handle_disconnect,
            )

    @property
    def connected(self) -> bool:
        with self._pipeline_lock:
            return self._pipeline.connected

    def subscribe(
        self,
        on_candle: CompletedCandleHandler,
        on_market_update: LiveMarketUpdateHandler | None = None,
    ) -> None:
        if self._on_candle is not None:
            raise RuntimeError(
                "AngelOne live candle feed is already subscribed"
            )

        self._on_candle = on_candle
        self._on_market_update = on_market_update
        self._connect_epoch()

    def reconnect(self) -> None:
        """
        Start a fresh provider connection epoch.

        Any candle active in the prior epoch is invalidated before the new
        connection begins.
        """
        if self._on_candle is None:
            raise RuntimeError(
                "AngelOne live candle feed must be subscribed before reconnect"
            )

        with self._pipeline_lock:
            self._pipeline.mark_disconnected()

        self._adapter.close()

        self._connect_epoch()

    def close(self) -> None:
        with self._pipeline_lock:
            self._pipeline.mark_disconnected()

        self._adapter.close()

    def advance_time(
        self,
        timestamp: datetime,
    ) -> None:
        with self._pipeline_lock:
            candle = self._pipeline.advance_time(timestamp)

            if candle is not None:
                self._emit(candle)

    def _connect_epoch(self) -> None:
        with self._pipeline_lock:
            self._pipeline.begin_connection()

        try:
            self._adapter.connect()
        except Exception:
            with self._pipeline_lock:
                self._pipeline.mark_disconnected()

            raise

    def _handle_update(
        self,
        update: LiveMarketUpdate,
    ) -> None:
        with self._pipeline_lock:
            candle, accepted = (
                self._pipeline.on_update_with_acceptance(
                    update
                )
            )

            if not accepted:
                return

            opens_new_bar = candle is not None

            # The boundary source update first proves the prior candle
            # complete. Strategy decision therefore happens before the
            # same observation becomes the causal next-bar execution price.
            if candle is not None:
                self._emit(candle)

            if self._on_market_update is not None:
                self._on_market_update(
                    update,
                    opens_new_bar,
                )

    def _handle_disconnect(self) -> None:
        with self._pipeline_lock:
            self._pipeline.mark_disconnected()

    def _emit(
        self,
        candle: Candle,
    ) -> None:
        if self._on_candle is None:
            raise RuntimeError(
                "AngelOne live candle feed has no completed-candle consumer"
            )

        self._on_candle(candle)

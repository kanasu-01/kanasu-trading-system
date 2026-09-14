from pathlib import Path

from core.broker.broker_factory import create_angelone_broker
from core.config.app_config import AppConfig
from core.market_data.historical_feed import HistoricalFeed
from core.market_data.historical_feed_provider import HistoricalFeedProvider
from core.market_data.historical_source import HistoricalSource
from core.market_data.sqlite_candle_store import SQLiteCandleStore


def create_historical_source(app_config: AppConfig) -> HistoricalSource:
    database_path = Path(app_config.historical_database_path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    store = SQLiteCandleStore(database_path)

    def create_provider() -> HistoricalFeedProvider:
        broker = create_angelone_broker(
            paper_mode=True,
            enable_historical_api=True,
        )
        feed = HistoricalFeed(
            broker,
            request_delay_sec=app_config.historical_request_delay_sec,
        )
        return HistoricalFeedProvider(feed)

    return HistoricalSource(
        store=store,
        policy=app_config.historical_source_policy,
        provider_factory=create_provider,
    )

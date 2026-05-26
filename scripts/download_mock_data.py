from core.broker.broker_factory import (
    create_angelone_broker,
)

from core.market_data.historical_feed import (
    HistoricalFeed,
)

from core.config.backtest_config import (
    BACKTEST_CONFIG,
)

from core.backtest.exporters.candle_only_exporter import (
    export_candles_only,
)

from core.backtest.exporters.bar_record_adapter import (
    bar_records_to_dicts,
)

from core.backtest.bar_record import (
    BarRecord,
)
from dotenv import load_dotenv

load_dotenv()


def main():

    broker = create_angelone_broker(
        paper_mode=True,
        enable_historical_api=True,
    )

    feed = HistoricalFeed(
        broker=broker,
        request_delay_sec=1.0,
    )

    candles = list(
        feed.stream(
            symbol=BACKTEST_CONFIG.symbol,
            timeframe=BACKTEST_CONFIG.timeframe,
            start=BACKTEST_CONFIG.start,
            end=BACKTEST_CONFIG.end,
        )
    )

    records = []

    for candle in candles:

        records.append(
            BarRecord(
                timestamp=candle.timestamp,
                open=candle.open,
                high=candle.high,
                low=candle.low,
                close=candle.close,
                volume=candle.volume,
                strategy="",
                state=None,
                signal=None,
                execution_event=None,
                execution_price=None,
                execution_quantity=None,
                decision_snapshot={},
                equity=0.0,
                cash=0.0,
                position_size=0.0,
                drawdown=0.0,
            )
        )

    export_candles_only(
        records=bar_records_to_dicts(records),
        filepath=(
            f"data/mock_live/"
            f"{BACKTEST_CONFIG.symbol}_"
            f"{BACKTEST_CONFIG.timeframe}.csv"
        ),
    )

    print("\n=== MOCK DATA DOWNLOADED ===")


if __name__ == "__main__":

    main()

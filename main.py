# main.py (root)
import sys
from datetime import datetime

import pytz
from core.runtime.walk_forward_runtime import (
    run_walk_forward,
)
from core.config.app_config import AppConfig
from core.config.paper_data_source import PaperDataSource
from core.config.runtime_mode import RuntimeMode
import logging
from core.runtime.backtest_runtime import (
    run_backtest,
)
from core.config.backtest_config import (
    BacktestConfig,
    BACKTEST_CONFIG,
)
from core.strategies.strategy_factory import (
    create_strategy,
)
from core.runtime.runtime_context import RuntimeContext

from core.runtime.dataset_context import DatasetContext
from dotenv import load_dotenv
from core.runtime.paper_runtime import (
    run_live_paper_trading,
    run_paper_trading,
)

from core.market_data.mock_live_feed import (
    MockLiveFeed,
)
from core.market_data.angelone_live_candle_feed import (
    AngelOneLiveCandleFeed,
)
from core.broker.angelone import AngelOneBroker
from core.broker.angelone_config import AngelOneConfig

from core.market_data.csv_candle_loader import (
    load_candles_from_csv,
)
from core.market_data.historical_source_factory import (
    create_historical_source,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format=("%(asctime)s | " "%(levelname)s | " "%(name)s | " "%(message)s"),
)


def main(app_config: AppConfig, backtest_config: BacktestConfig) -> None:
    # -------- MODE --------

    # -------- BACKTEST FLOW --------
    if app_config.runtime_mode == RuntimeMode.BACKTEST:

        historical_source = create_historical_source(app_config)
        strategy = create_strategy(backtest_config)
        run_backtest(
            historical_source=historical_source,
            strategy=strategy,
            config=backtest_config,
            runtime_context=RuntimeContext(
                risk_per_trade_pct=app_config.risk_per_trade_pct,
            ),
            dataset_context=DatasetContext(
                symbol=backtest_config.symbol,
                timeframe=backtest_config.timeframe,
                timezone=backtest_config.timezone,
            ),
        )

    elif app_config.runtime_mode == RuntimeMode.WALK_FORWARD:

        historical_source = create_historical_source(app_config)
        run_walk_forward(
            historical_source=historical_source,
            config=backtest_config,
            runtime_context=RuntimeContext(
                risk_per_trade_pct=app_config.risk_per_trade_pct,
            ),
        )

    elif app_config.runtime_mode == RuntimeMode.PAPER:

        strategy = create_strategy(backtest_config)

        runtime_context = RuntimeContext(
            risk_per_trade_pct=app_config.risk_per_trade_pct,
        )
        dataset_context = DatasetContext(
            symbol=backtest_config.symbol,
            timeframe=backtest_config.timeframe,
            timezone=backtest_config.timezone,
        )

        if app_config.paper_data_source == PaperDataSource.MOCK:
            candles = load_candles_from_csv(
                filepath=(
                    "data/mock_live/"
                    f"{backtest_config.symbol}_"
                    f"{backtest_config.timeframe}.csv"
                )
            )

            mock_feed = MockLiveFeed(
                candles=candles,
                interval_seconds=0.0,
            )

            run_paper_trading(
                feed=mock_feed,
                strategy=strategy,
                runtime_context=runtime_context,
                dataset_context=dataset_context,
                initial_capital=backtest_config.initial_capital,
            )

        elif app_config.paper_data_source == PaperDataSource.ANGELONE:
            angelone_config = AngelOneConfig.load_from_env()

            broker = AngelOneBroker(
                config=angelone_config,
                paper_mode=True,
                enable_historical_api=False,
            )
            broker.login()

            auth_token, feed_token = (
                broker.get_live_market_data_session()
            )

            feed = AngelOneLiveCandleFeed(
                config=angelone_config,
                auth_token=auth_token,
                feed_token=feed_token,
                symbol=backtest_config.symbol,
                timeframe=backtest_config.timeframe,
                session_start=app_config.paper_session_start,
            )

            ist = pytz.timezone("Asia/Kolkata")
            current_time = datetime.now(ist)
            session_end = ist.localize(
                datetime.combine(
                    current_time.date(),
                    app_config.paper_session_end,
                )
            )

            run_live_paper_trading(
                feed=feed,
                strategy=strategy,
                runtime_context=runtime_context,
                dataset_context=dataset_context,
                session_end=session_end,
                now=lambda: datetime.now(ist),
                reconnect_attempts=app_config.broker_retry_attempts,
                reconnect_delay_seconds=(
                    app_config.broker_retry_delay_sec
                ),
                clock_interval_seconds=(
                    app_config.paper_clock_interval_sec
                ),
                initial_capital=backtest_config.initial_capital,
            )

        else:
            raise ValueError(
                f"Unsupported paper data source: "
                f"{app_config.paper_data_source}"
            )

    elif app_config.runtime_mode == RuntimeMode.LIVE:

        run_live_trading()

    else:

        raise ValueError(f"Unsupported runtime mode: " f"{app_config.runtime_mode}")


def run_live_trading():

    print("\n=== LIVE MODE NOT IMPLEMENTED ===")


if __name__ == "__main__":

    try:

        main(
            app_config=AppConfig(),
            backtest_config=BACKTEST_CONFIG,
        )

    except Exception as e:

        logging.exception("Kanasu runtime startup failed")

        print("\n=== KANASU STARTUP FAILURE ===")

        print(str(e))

        sys.exit(1)

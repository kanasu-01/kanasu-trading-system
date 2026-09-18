# main.py (root)
import sys
from core.runtime.walk_forward_runtime import (
    run_walk_forward,
)
from core.config.app_config import AppConfig
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
    run_paper_trading,
)

from core.market_data.mock_live_feed import (
    MockLiveFeed,
)

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
        )

    elif app_config.runtime_mode == RuntimeMode.PAPER:

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

        strategy = create_strategy(backtest_config)

        run_paper_trading(
            feed=mock_feed,
            strategy=strategy,
            runtime_context=RuntimeContext(),
            dataset_context=DatasetContext(
                symbol=backtest_config.symbol,
                timeframe=backtest_config.timeframe,
                timezone=backtest_config.timezone,
            ),
            initial_capital=(backtest_config.initial_capital),
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

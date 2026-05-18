# main.py (root)
import sys
from core.market_data.historical_feed import HistoricalFeed
from core.backtest.backtest_engine import BacktestEngine
from core.broker.base_broker import BaseBroker
from core.strategies.base_strategy import BaseStrategy
from core.config.app_config import AppConfig
from core.config.runtime_mode import RuntimeMode
import logging
from core.backtest.backtest_runner import (
    print_performance_summary,
    run_replay,
    export_backtest_records,
    visualize_backtest,
)
from core.config.backtest_config import (
    BacktestConfig,
    BACKTEST_CONFIG,
)
from core.strategies.strategy_factory import (
    create_strategy,
)
from core.broker.broker_factory import (
    create_angelone_broker,
)

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format=("%(asctime)s | " "%(levelname)s | " "%(name)s | " "%(message)s"),
)


def main(app_config: AppConfig, backtest_config: BacktestConfig) -> None:
    # -------- MODE --------

    # -------- BROKER --------
    broker = create_angelone_broker(
        paper_mode=(app_config.runtime_mode != RuntimeMode.LIVE),
        enable_historical_api=(
            app_config.runtime_mode in [RuntimeMode.BACKTEST, RuntimeMode.PAPER]
        ),
    )

    # -------- STRATEGY --------
    # strategy = PivotBossSwingStrategy()
    strategy = create_strategy(backtest_config)

    # -------- BACKTEST FLOW --------
    if app_config.runtime_mode == RuntimeMode.BACKTEST:
        run_backtest(
            broker=broker,
            strategy=strategy,
            config=backtest_config,
            app_config=app_config,
        )

    elif app_config.runtime_mode == RuntimeMode.PAPER:

        raise NotImplementedError(
            "Live paper trading runtime " "is not implemented yet"
        )

    elif app_config.runtime_mode == RuntimeMode.LIVE:

        run_live_trading()

    else:

        raise ValueError(f"Unsupported runtime mode: " f"{app_config.runtime_mode}")


def run_backtest(
    broker: BaseBroker,
    strategy: BaseStrategy,
    config: BacktestConfig,
    app_config: AppConfig,
) -> None:
    feed = HistoricalFeed(
        broker,
        request_delay_sec=app_config.historical_request_delay_sec,
    )

    candle_stream = feed.stream(
        symbol=config.symbol,
        timeframe=config.timeframe,
        start=config.start,
        end=config.end,
    )

    engine = BacktestEngine(strategy=strategy, initial_capital=config.initial_capital)
    trades = engine.run_stream(candle_stream)

    ## Performance metrics OR Backtest summary report
    print_performance_summary(trades)

    if config.enable_replay:
        run_replay(
            strategy=strategy,
            records=engine.bar_recorder.records,
        )

    # EXPORTS (CSV/JSON for replay)
    if config.enable_exports:
        export_backtest_records(records=engine.bar_recorder.records, config=config)

    # Visualization
    if config.enable_visualization:
        visualize_backtest(
            strategy=strategy,
            records=engine.bar_recorder.records,
            trades=trades,
        )


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

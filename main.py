# main.py (root)
import sys
from datetime import datetime, timedelta

import pytz
from core.runtime.walk_forward_runtime import (
    run_walk_forward,
)
from core.config.app_config import AppConfig
from core.config.loaders import load_app_config
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
from core.runtime.live_paper_session import (
    resolve_live_paper_session_window,
)
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
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_source_factory import (
    create_historical_source,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format=("%(asctime)s | " "%(levelname)s | " "%(name)s | " "%(message)s"),
)


_LIVE_TIMEFRAME_MINUTES = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "10m": 10,
    "15m": 15,
    "30m": 30,
    "1h": 60,
}


def _load_live_paper_warmup(
    *,
    app_config: AppConfig,
    historical_source,
    strategy,
    dataset_context: DatasetContext,
    current_time: datetime,
    session_start: datetime,
) -> list:
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
    session_minutes = (end_seconds - start_seconds) // 60

    timeframe_minutes = _LIVE_TIMEFRAME_MINUTES[timeframe]

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

    # Calendar lookback deliberately exceeds the minimum trading-session
    # count so weekends and ordinary exchange holidays do not silently
    # starve strategy warm-up. Exact sufficiency is validated below.
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
            ist = pytz.timezone("Asia/Kolkata")
            current_time = datetime.now(ist)
            session_window = resolve_live_paper_session_window(
                current_time=current_time,
                session_start=app_config.paper_session_start,
                session_end=app_config.paper_session_end,
            )

            historical_source = create_historical_source(
                app_config
            )

            history_bars = _load_live_paper_warmup(
                app_config=app_config,
                historical_source=historical_source,
                strategy=strategy,
                dataset_context=dataset_context,
                current_time=current_time,
                session_start=session_window.start,
            )

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

            # Historical warm-up, broker login, and token acquisition may
            # take long enough to cross the configured session boundary.
            # Revalidate immediately before admitting the live feed/runtime.
            current_time = datetime.now(ist)
            session_window = resolve_live_paper_session_window(
                current_time=current_time,
                session_start=app_config.paper_session_start,
                session_end=app_config.paper_session_end,
            )

            feed = AngelOneLiveCandleFeed(
                config=angelone_config,
                auth_token=auth_token,
                feed_token=feed_token,
                symbol=backtest_config.symbol,
                timeframe=backtest_config.timeframe,
                session_start=app_config.paper_session_start,
            )

            run_live_paper_trading(
                feed=feed,
                strategy=strategy,
                runtime_context=runtime_context,
                dataset_context=dataset_context,
                session_end=session_window.end,
                now=lambda: datetime.now(ist),
                reconnect_attempts=app_config.broker_retry_attempts,
                reconnect_delay_seconds=(
                    app_config.broker_retry_delay_sec
                ),
                clock_interval_seconds=(
                    app_config.paper_clock_interval_sec
                ),
                initial_capital=backtest_config.initial_capital,
                history_bars=history_bars,
                historical_source=historical_source,
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


def run_configured_application() -> None:
    main(
        app_config=load_app_config(),
        backtest_config=BACKTEST_CONFIG,
    )


if __name__ == "__main__":

    try:

        run_configured_application()

    except Exception as e:

        logging.exception("Kanasu runtime startup failed")

        print("\n=== KANASU STARTUP FAILURE ===")

        print(str(e))

        sys.exit(1)

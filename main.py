# main.py (root)
import sys
from core.runtime.walk_forward_runtime import (
    run_walk_forward,
)
from core.broker.base_broker import BaseBroker
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

    # -------- BACKTEST FLOW --------
    if app_config.runtime_mode == RuntimeMode.BACKTEST:

        strategy = create_strategy(backtest_config)
        run_backtest(
            broker=broker,
            strategy=strategy,
            config=backtest_config,
            app_config=app_config,
        )

    elif app_config.runtime_mode == RuntimeMode.WALK_FORWARD:

        run_walk_forward(
            broker=broker,
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

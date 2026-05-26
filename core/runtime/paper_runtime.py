from core.market_data.mock_live_feed import (
    MockLiveFeed,
)

from core.entities.candle_series import (
    CandleSeries,
)

from core.strategies.strategy_runner import (
    StrategyRunner,
)

from core.execution.trade_execution_engine import (
    TradeExecutionEngine,
)

from core.logging.logger import (
    get_logger,
)

from core.runtime.runtime_context import (
    RuntimeContext,
)

from core.runtime.dataset_context import (
    DatasetContext,
)

from core.entities.candle import (
    Candle,
)

from core.strategies.base_strategy import (
    BaseStrategy,
)
from core.market_data.base_feed import BaseFeed

logger = get_logger(__name__)


def run_paper_trading(
    feed: BaseFeed,
    strategy: BaseStrategy,
    runtime_context: RuntimeContext,
    dataset_context: DatasetContext,
    initial_capital: float = 100000,
) -> None:
    """
    MVP paper trading runtime using mock live candles.
    """

    logger.info(f"PAPER TRADING STARTED | " f"Symbol={dataset_context.symbol}")

    series = CandleSeries()

    strategy_runner = StrategyRunner(strategy)

    strategy_runner.start(series)

    execution_engine = TradeExecutionEngine(
        strategy=strategy,
        account_capital=initial_capital,
        session_id="paper_session",
        runtime_context=runtime_context,
    )

    def on_candle(candle: Candle) -> None:

        signal = strategy_runner.on_new_candle(candle)

        execution_engine.on_signal(
            signal=signal,
            candle=candle,
            series=series,
            symbol=dataset_context.symbol,
        )

    feed.subscribe(on_candle)

    logger.info(
        f"PAPER TRADING COMPLETED | " f"Trades={len(execution_engine.completed_trades)}"
    )

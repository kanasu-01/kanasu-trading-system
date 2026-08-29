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

from core.paper_trading.paper_trading_session import (
    PaperTradingSession,
)

logger = get_logger(__name__)


def run_paper_trading(
    feed: MockLiveFeed,
    strategy: BaseStrategy,
    runtime_context: RuntimeContext,
    dataset_context: DatasetContext,
    initial_capital: float = 100000,
) -> PaperTradingSession:
    """
    MVP paper trading runtime using mock live candles.
    """

    logger.info(f"PAPER TRADING STARTED | " f"Symbol={dataset_context.symbol}")

    session = PaperTradingSession(
        session_id="paper_session",
        strategy_name=strategy.name,
        symbol=dataset_context.symbol,
        initial_capital=initial_capital,
    )

    session.feed = feed

    session.strategy = strategy

    session.runtime_context = runtime_context

    session.dataset_context = dataset_context

    series = CandleSeries()

    strategy_runner = StrategyRunner(strategy)

    session.strategy_runner = strategy_runner

    strategy_runner.start(series)

    execution_engine = TradeExecutionEngine(
        strategy=strategy,
        account_capital=initial_capital,
        session_id="paper_session",
        runtime_context=runtime_context,
    )

    session.execution_engine = execution_engine

    def on_candle(candle: Candle) -> None:

        signal = strategy_runner.on_new_candle(candle)

        execution_engine.on_signal(
            signal=signal,
            candle=candle,
            series=series,
            symbol=dataset_context.symbol,
        )

    session.start()

    feed.subscribe(on_candle)

    logger.info(
        f"PAPER TRADING COMPLETED | " f"Trades={len(execution_engine.completed_trades)}"
    )
    return session

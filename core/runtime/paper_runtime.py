from core.logging.logger import get_logger
from core.market_data.live_candle_feed import LiveCandleFeed
from core.paper_trading.paper_trading_session import PaperTradingSession
from core.runtime.dataset_context import DatasetContext
from core.runtime.paper_candle_processor import PaperCandleProcessor
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy


logger = get_logger(__name__)


def run_paper_trading(
    feed: LiveCandleFeed,
    strategy: BaseStrategy,
    runtime_context: RuntimeContext,
    dataset_context: DatasetContext,
    initial_capital: float = 100000,
) -> PaperTradingSession:
    """
    Paper trading runtime consuming validated completed candles.
    """

    logger.info(
        f"PAPER TRADING STARTED | "
        f"Symbol={dataset_context.symbol}"
    )

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

    processor = PaperCandleProcessor(
        strategy=strategy,
        runtime_context=runtime_context,
        dataset_context=dataset_context,
        initial_capital=initial_capital,
        session_id=session.session_id,
    )

    session.strategy_runner = processor.strategy_runner
    session.execution_engine = processor.execution_engine

    session.start()

    feed.subscribe(processor.on_candle)

    logger.info(
        f"PAPER TRADING COMPLETED | "
        f"Trades={len(processor.execution_engine.completed_trades)}"
    )

    return session

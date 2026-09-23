import re
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from core.logging.logger import get_logger
from core.market_data.historical_coverage import TimeRange
from core.market_data.live_candle_feed import LiveCandleFeed
from core.paper_trading.paper_trading_session import PaperTradingSession
from core.runtime.dataset_context import DatasetContext
from core.runtime.live_paper_runtime import (
    LivePaperRuntime,
    ManagedLiveCandleFeed,
)
from core.runtime.paper_candle_processor import PaperCandleProcessor
from core.runtime.runtime_context import RuntimeContext
from core.strategies.base_strategy import BaseStrategy


logger = get_logger(__name__)


def _create_paper_session_id(
    *,
    source: str,
    symbol: str,
) -> str:
    """Return one human-readable, filesystem-safe paper session id."""

    source_token = source.strip().lower()

    if source_token not in {"mock", "live"}:
        raise ValueError(
            f"unsupported paper session source: {source!r}"
        )

    symbol_token = re.sub(
        r"[^A-Za-z0-9]+",
        "-",
        symbol.strip().upper(),
    ).strip("-")

    if not symbol_token:
        raise ValueError(
            "paper session symbol must contain an alphanumeric character"
        )

    started_token = (
        datetime.now()
        .astimezone()
        .strftime("%Y%m%d-%H%M%S")
    )
    unique_token = uuid.uuid4().hex[:8]

    return (
        f"paper-{source_token}-{started_token}-"
        f"{symbol_token}-{unique_token}"
    )


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
        session_id=_create_paper_session_id(
            source="mock",
            symbol=dataset_context.symbol,
        ),
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

    try:
        feed.subscribe(processor.on_candle)
    except Exception as exc:
        session.fail(exc)
        logger.exception(
            f"PAPER TRADING FAILED | Symbol={dataset_context.symbol}"
        )
        raise
    else:
        session.stop()

    logger.info(
        f"PAPER TRADING COMPLETED | "
        f"Trades={len(processor.execution_engine.completed_trades)}"
    )

    return session



@dataclass(frozen=True)
class PreparedLivePaperRun:
    """Prepared authoritative live-paper graph ready for execution."""

    session: PaperTradingSession
    runtime: LivePaperRuntime
    state_lock: object
    session_end: datetime
    now: Callable[[], datetime]
    clock_interval_seconds: float


def prepare_live_paper_trading(
    *,
    feed: ManagedLiveCandleFeed,
    strategy: BaseStrategy,
    runtime_context: RuntimeContext,
    dataset_context: DatasetContext,
    session_end: datetime,
    now: Callable[[], datetime],
    reconnect_attempts: int,
    reconnect_delay_seconds: float,
    clock_interval_seconds: float,
    initial_capital: float = 100000,
    history_bars=None,
    historical_source=None,
) -> PreparedLivePaperRun:
    """Prepare one authoritative M7 live-paper graph without starting it."""

    session = PaperTradingSession(
        session_id=_create_paper_session_id(
            source="live",
            symbol=dataset_context.symbol,
        ),
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
        history_bars=history_bars,
    )

    session.strategy_runner = processor.strategy_runner
    session.execution_engine = processor.execution_engine

    state_lock = threading.RLock()

    reconciliation_active = False
    pending_recovery_range = None
    reconciliation_generation = 0

    def begin_reconciliation() -> None:
        nonlocal reconciliation_active
        nonlocal pending_recovery_range
        nonlocal reconciliation_generation

        with state_lock:
            processor.begin_live_reconciliation()
            reconciliation_generation += 1
            reconciliation_active = True
            pending_recovery_range = None

    def handle_completed_candle(candle) -> None:
        with state_lock:
            if reconciliation_active:
                return

            processor.on_live_completed_candle(candle)

    def handle_reconciliation_market_update(
        update,
        opens_new_bar: bool,
    ) -> None:
        nonlocal pending_recovery_range

        with state_lock:
            if not reconciliation_active:
                processor.on_live_market_update(
                    update,
                    opens_new_bar,
                )
                return

            processor.on_live_market_update(
                update,
                False,
            )

            recovery_range = (
                processor.observe_live_reconciliation_update(
                    update,
                    opens_new_bar,
                )
            )

            if recovery_range is not None:
                pending_recovery_range = recovery_range

    def process_reconciliation_work() -> None:
        nonlocal reconciliation_active
        nonlocal pending_recovery_range

        with state_lock:
            if (
                not reconciliation_active
                or pending_recovery_range is None
            ):
                return

            recovery_range = pending_recovery_range
            recovery_generation = reconciliation_generation

        recovery_start, recovery_end = recovery_range

        try:
            if historical_source is None:
                raise RuntimeError(
                    "live paper historical source is required "
                    "for reconnect reconciliation"
                )

            recovered_candles = historical_source.retrieve(
                dataset_context,
                TimeRange(
                    start=recovery_start,
                    end=recovery_end,
                ),
            )

            with state_lock:
                if (
                    not reconciliation_active
                    or reconciliation_generation
                    != recovery_generation
                    or pending_recovery_range != recovery_range
                ):
                    return

                processor.apply_live_reconciliation_candles(
                    recovered_candles,
                    expected_start=recovery_start,
                    expected_end=recovery_end,
                )

                pending_recovery_range = None
                reconciliation_active = False

        except Exception:
            with state_lock:
                if (
                    not reconciliation_active
                    or reconciliation_generation
                    != recovery_generation
                    or pending_recovery_range != recovery_range
                ):
                    return

                pending_recovery_range = None

                open_position = (
                    processor.execution_engine.get_runtime_position(
                        dataset_context.symbol
                    )
                )

            if open_position is None:
                raise

            logger.exception(
                f"LIVE PAPER RECONCILIATION HISTORY FAILED | "
                f"Symbol={dataset_context.symbol} | "
                f"Continuing restricted live protection"
            )

    supervisor = LivePaperRuntime(
        feed=feed,
        on_candle=handle_completed_candle,
        on_market_update=handle_reconciliation_market_update,
        on_reconciliation_required=begin_reconciliation,
        on_clock=process_reconciliation_work,
        reconnect_attempts=reconnect_attempts,
        reconnect_delay_seconds=reconnect_delay_seconds,
    )

    return PreparedLivePaperRun(
        session=session,
        runtime=supervisor,
        state_lock=state_lock,
        session_end=session_end,
        now=now,
        clock_interval_seconds=clock_interval_seconds,
    )


def execute_prepared_live_paper_trading(
    prepared: PreparedLivePaperRun,
) -> PaperTradingSession:
    """Execute one previously prepared authoritative live-paper graph."""

    session = prepared.session

    logger.info(
        f"LIVE PAPER TRADING STARTED | "
        f"Symbol={session.symbol}"
    )

    with prepared.state_lock:
        session.start()

    try:
        prepared.runtime.run_until(
            session_end=prepared.session_end,
            now=prepared.now,
            clock_interval_seconds=(
                prepared.clock_interval_seconds
            ),
        )
    except Exception as exc:
        with prepared.state_lock:
            session.fail(exc)

        logger.exception(
            f"LIVE PAPER TRADING FAILED | "
            f"Symbol={session.symbol}"
        )
        raise
    else:
        with prepared.state_lock:
            session.stop()

    with prepared.state_lock:
        engine = session.execution_engine
        completed_trade_count = (
            len(engine.completed_trades)
            if engine is not None
            else 0
        )

    logger.info(
        f"LIVE PAPER TRADING COMPLETED | "
        f"Trades={completed_trade_count}"
    )

    return session


def run_live_paper_trading(
    *,
    feed: ManagedLiveCandleFeed,
    strategy: BaseStrategy,
    runtime_context: RuntimeContext,
    dataset_context: DatasetContext,
    session_end,
    now,
    reconnect_attempts: int,
    reconnect_delay_seconds: float,
    clock_interval_seconds: float,
    initial_capital: float = 100000,
    history_bars=None,
    historical_source=None,
) -> PaperTradingSession:
    """Run one supervised live-market-data paper session."""

    prepared = prepare_live_paper_trading(
        feed=feed,
        strategy=strategy,
        runtime_context=runtime_context,
        dataset_context=dataset_context,
        session_end=session_end,
        now=now,
        reconnect_attempts=reconnect_attempts,
        reconnect_delay_seconds=reconnect_delay_seconds,
        clock_interval_seconds=clock_interval_seconds,
        initial_capital=initial_capital,
        history_bars=history_bars,
        historical_source=historical_source,
    )

    return execute_prepared_live_paper_trading(
        prepared
    )

from typing import List

from core.backtest.backtest_engine import (
    BacktestEngine,
)
from core.backtest.backtest_result import (
    BacktestResult,
)

from core.backtest.backtest_runner import (
    print_performance_summary,
    run_replay,
    export_backtest_records,
    visualize_backtest,
)

from core.strategies.base_strategy import (
    BaseStrategy,
)

from core.config.backtest_config import (
    BacktestConfig,
)
from core.market_data.historical_coverage import TimeRange
from core.entities.candle import Candle
from core.market_data.historical_source import HistoricalSource
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext


def retrieve_backtest_candles(
    historical_source: HistoricalSource,
    config: BacktestConfig,
    dataset_context: DatasetContext,
) -> List[Candle]:
    """Retrieve and materialize the canonical Backtest candle sequence."""

    return list(
        historical_source.retrieve(
            dataset_context,
            TimeRange(config.start, config.end),
        )
    )


class DeterministicBacktestComputationError(RuntimeError):
    """Authoritative deterministic Backtest computation failed."""

    def __init__(self, original_error: Exception):
        self.original_error = original_error
        message = str(original_error).strip()
        if not message:
            message = type(original_error).__name__
        super().__init__(message)


class TransientBacktestOperationalError(RuntimeError):
    """Typed operational failure occurred around Backtest execution."""

    def __init__(self, original_error: Exception):
        self.original_error = original_error
        message = str(original_error).strip()
        if not message:
            message = type(original_error).__name__
        super().__init__(message)


def execute_backtest_candles(
    candles: List[Candle],
    strategy: BaseStrategy,
    config: BacktestConfig,
    runtime_context: RuntimeContext,
    dataset_context: DatasetContext,
) -> BacktestResult:
    """Execute the authoritative engine over already-retrieved candles."""

    try:
        engine = BacktestEngine(
            strategy=strategy,
            initial_capital=config.initial_capital,
            runtime_context=runtime_context,
            dataset_context=dataset_context,
        )

        return engine.run_stream(candles)
    except (ConnectionError, TimeoutError) as error:
        raise TransientBacktestOperationalError(
            error
        ) from error
    except OSError as error:
        raise TransientBacktestOperationalError(
            error
        ) from error
    except Exception as error:
        raise DeterministicBacktestComputationError(
            error
        ) from error


def execute_backtest(
    historical_source: HistoricalSource,
    strategy: BaseStrategy,
    config: BacktestConfig,
    runtime_context: RuntimeContext,
    dataset_context: DatasetContext,
) -> BacktestResult:
    """Retrieve once and execute the authoritative Backtest path."""

    candles = retrieve_backtest_candles(
        historical_source=historical_source,
        config=config,
        dataset_context=dataset_context,
    )

    return execute_backtest_candles(
        candles=candles,
        strategy=strategy,
        config=config,
        runtime_context=runtime_context,
        dataset_context=dataset_context,
    )


def run_backtest(
    historical_source: HistoricalSource,
    strategy: BaseStrategy,
    config: BacktestConfig,
    runtime_context: RuntimeContext,
    dataset_context: DatasetContext,
) -> None:
    backtest_result = execute_backtest(
        historical_source=historical_source,
        strategy=strategy,
        config=config,
        runtime_context=runtime_context,
        dataset_context=dataset_context,
    )

    # Performance metrics OR Backtest summary report
    print_performance_summary(backtest_result)

    if config.enable_replay:
        run_replay(
            strategy=strategy,
            records=backtest_result.bar_records,
        )

    if config.enable_exports:
        export_backtest_records(
            result=backtest_result,
            config=config,
        )

    if config.enable_visualization:
        visualize_backtest(
            strategy=strategy,
            result=backtest_result,
        )

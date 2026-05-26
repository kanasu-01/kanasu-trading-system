from core.market_data.historical_feed import (
    HistoricalFeed,
)

from core.backtest.backtest_engine import (
    BacktestEngine,
)

from core.backtest.backtest_runner import (
    print_performance_summary,
    run_replay,
    export_backtest_records,
    visualize_backtest,
)

from core.broker.base_broker import (
    BaseBroker,
)

from core.strategies.base_strategy import (
    BaseStrategy,
)

from core.config.app_config import (
    AppConfig,
)

from core.config.backtest_config import (
    BacktestConfig,
)
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext


def run_backtest(
    broker: BaseBroker,
    strategy: BaseStrategy,
    config: BacktestConfig,
    app_config: AppConfig,
    runtime_context: RuntimeContext,
    dataset_context: DatasetContext,
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

    engine = BacktestEngine(
        strategy=strategy,
        initial_capital=config.initial_capital,
        runtime_context=runtime_context,
        dataset_context=dataset_context,
    )
    backtest_result = engine.run_stream(candle_stream)

    ## Performance metrics OR Backtest summary report
    print_performance_summary(backtest_result)

    if config.enable_replay:
        run_replay(
            strategy=strategy,
            records=backtest_result.bar_records,
        )

    # EXPORTS (CSV/JSON for replay)
    if config.enable_exports:
        export_backtest_records(
            result=backtest_result,
            config=config,
        )

    # Visualization
    if config.enable_visualization:
        visualize_backtest(
            strategy=strategy,
            result=backtest_result,
        )

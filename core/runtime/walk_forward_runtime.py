from core.walk_forward.window_generator import (
    WalkForwardWindowGenerator,
)

from core.walk_forward.optimizer import (
    GridSearchOptimizer,
)

from core.walk_forward.metrics import (
    WalkForwardMetrics,
)

from core.walk_forward.runner import (
    WalkForwardRunner,
)

from core.walk_forward.reporting import (
    WalkForwardReporter,
)

from core.config.backtest_config import (
    BacktestConfig,
)
from core.market_data.historical_coverage import TimeRange
from core.market_data.historical_source import HistoricalSource
from core.runtime.dataset_context import DatasetContext
from core.runtime.runtime_context import RuntimeContext

from core.strategies.strategy_factory import (
    get_strategy_class,
)
from core.config.walk_forward_config import (
    WALK_FORWARD_CONFIG,
)
from core.walk_forward.exporters.export_wfa_results import (
    export_walk_forward_results,
)

from core.walk_forward.equity_stitcher import (
    EquityStitcher,
)

from core.walk_forward.equity_visualizer import (
    EquityVisualizer,
)

from core.logging.logger import (
    get_logger,
)

logger = get_logger(__name__)


def run_walk_forward(
    historical_source: HistoricalSource,
    config: BacktestConfig,
    runtime_context: RuntimeContext,
) -> None:

    logger.info(
        f"WALK-FORWARD STARTED | "
        f"Symbol={config.symbol} | "
        f"Timeframe={config.timeframe}"
    )

    # -----------------------------------------
    # Historical Data
    # -----------------------------------------

    dataset_context = DatasetContext(
        symbol=config.symbol,
        timeframe=config.timeframe,
        timezone=config.timezone,
    )
    candles = historical_source.retrieve(
        dataset_context,
        TimeRange(config.start, config.end),
    )

    strategy_cls = get_strategy_class(config)

    # -----------------------------------------
    # Walk-Forward Infrastructure
    # -----------------------------------------

    window_generator = WalkForwardWindowGenerator(
        in_sample_bars=(WALK_FORWARD_CONFIG.in_sample_bars),
        out_sample_bars=(WALK_FORWARD_CONFIG.out_sample_bars),
        step_bars=(WALK_FORWARD_CONFIG.step_bars),
        mode=WALK_FORWARD_CONFIG.mode,
    )

    optimizer = GridSearchOptimizer()

    metrics = WalkForwardMetrics()

    runner = WalkForwardRunner(
        window_generator=window_generator,
        optimizer=optimizer,
        metrics=metrics,
    )

    reporter = WalkForwardReporter()

    # -----------------------------------------
    # Parameter Space
    # -----------------------------------

    # -----------------------------------------
    # Execute WFA
    # -----------------------------------------

    wf_result = runner.run(
        strategy_cls=strategy_cls,
        param_space=(WALK_FORWARD_CONFIG.param_space),
        candles=candles,
        dataset_context=dataset_context,
        initial_capital=config.initial_capital,
        runtime_context=runtime_context,
    )

    # -----------------------------------------
    # Reporting
    # -----------------------------------------

    reporter.log_summary(wf_result)

    stitched_curve = EquityStitcher.stitch(wf_result.windows)

    EquityVisualizer.plot(
        curve=stitched_curve,
        title=(f"{config.symbol} " f"{config.timeframe} " f"WFA Equity Curve"),
    )

    logger.info(
        f"WALK-FORWARD COMPLETED | "
        f"Symbol={config.symbol} | "
        f"Timeframe={config.timeframe} | "
        f"Verdict={wf_result.verdict}"
    )
    export_walk_forward_results(
        result=wf_result,
        filepath_prefix=(
            f"outputs/walk_forward/" f"{config.symbol}_" f"{config.timeframe}_wfa"
        ),
    )

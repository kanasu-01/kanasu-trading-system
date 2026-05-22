from dataclasses import asdict

from core.entities.candle import Candle
from core.backtest.bar_replay import BarByBarReplay
from core.backtest.backtest_result import BacktestResult
from core.backtest.simple_visualization import (
    SimpleChartVisualizer,
)
from core.backtest.exporters.csv_exporter import (
    CSVExporter,
)
from core.backtest.exporters.json_exporter import (
    JSONExporter,
)
from core.backtest.exporters.bar_record_adapter import (
    bar_records_to_dicts,
)
from core.backtest.performance_metrics import (
    PerformanceMetrics,
)


def print_performance_summary(result: BacktestResult):

    metrics = PerformanceMetrics.summarize(result.trades)

    print("\n=== PERFORMANCE METRICS ===")

    for key, value in metrics.items():
        print(f"{key}: {value}")


def run_replay(
    strategy,
    records,
):

    replay = BarByBarReplay(strategy)

    replay.run_from_records(records)


def export_backtest_records(
    result: BacktestResult,
    config,
):

    CSVExporter.export(
        records=bar_records_to_dicts(result.bar_records),
        filepath=(
            f"outputs/backtests/" f"{config.symbol}_" f"{config.timeframe}_bars.csv"
        ),
    )

    JSONExporter.export(
        records=[asdict(r) for r in result.bar_records],
        filepath=(
            f"frontend/public/replay/"
            f"{config.symbol}_"
            f"{config.timeframe}_bars.json"
        ),
    )


def visualize_backtest(
    strategy,
    result: BacktestResult,
):

    candles = [
        Candle(
            timestamp=r.timestamp,
            open=r.open,
            high=r.high,
            low=r.low,
            close=r.close,
            volume=r.volume,
        )
        for r in result.bar_records
    ]

    if not result.trades:
        print("\n=== NO TRADES FOUND ===")

    SimpleChartVisualizer.plot_price_with_signals(
        candles=candles,
        trades=result.trades,
        strategy_name=strategy.name,
    )

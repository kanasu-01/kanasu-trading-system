from core.backtest.exporters.csv_exporter import (
    CSVExporter,
)

from core.backtest.exporters.json_exporter import (
    JSONExporter,
)

from core.walk_forward.exporters.window_result_adapter import (
    walk_window_results_to_dicts,
)

from core.walk_forward.result import (
    WalkForwardResult,
)
from core.walk_forward.exporters.aggregated_metrics_adapter import (
    aggregated_metrics_to_dict,
)

from core.walk_forward.equity_stitcher import (
    EquityStitcher,
)

from core.walk_forward.exporters.equity_curve_adapter import (
    equity_curve_to_dicts,
)


def export_walk_forward_results(
    result: WalkForwardResult,
    filepath_prefix: str,
) -> None:
    """
    Export walk-forward results into CSV and JSON.
    """

    rows = walk_window_results_to_dicts(result.windows)

    CSVExporter.export(
        records=rows,
        filepath=f"{filepath_prefix}.csv",
    )

    JSONExporter.export(
        records=rows,
        filepath=f"{filepath_prefix}.json",
    )

    summary_row = aggregated_metrics_to_dict(result)

    CSVExporter.export(
        records=[summary_row],
        filepath=(f"{filepath_prefix}_summary.csv"),
    )

    JSONExporter.export(
        records=[summary_row],
        filepath=(f"{filepath_prefix}_summary.json"),
    )

    stitched_curve = EquityStitcher.stitch(result.windows)

    curve_rows = equity_curve_to_dicts(stitched_curve)

    CSVExporter.export(
        records=curve_rows,
        filepath=(f"{filepath_prefix}_equity.csv"),
    )

    JSONExporter.export(
        records=curve_rows,
        filepath=(f"{filepath_prefix}_equity.json"),
    )

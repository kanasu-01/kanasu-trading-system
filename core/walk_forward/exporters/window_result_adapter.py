from typing import List, Dict, Any

from core.walk_forward.result import (
    WalkWindowResult,
)


def walk_window_results_to_dicts(
    windows: List[WalkWindowResult],
) -> List[Dict[str, Any]]:
    """
    Flatten walk-forward window results into
    export-friendly dictionaries.
    """

    rows: List[Dict[str, Any]] = []

    for window in windows:

        row = {
            "window_index": window.window_index,
            "trade_count": window.trade_count,
            **window.best_params,
            **window.test_metrics,
        }

        rows.append(row)

    return rows

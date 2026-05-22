from typing import (
    List,
    Tuple,
    Dict,
    Any,
)

from datetime import datetime


def equity_curve_to_dicts(
    curve: List[Tuple[datetime, float]],
) -> List[Dict[str, Any]]:
    """
    Convert stitched equity curve into
    export-friendly dictionaries.
    """

    rows: List[Dict[str, Any]] = []

    for timestamp, equity in curve:

        rows.append(
            {
                "timestamp": timestamp,
                "equity": equity,
            }
        )

    return rows

from dataclasses import asdict
from typing import List
import json

from core.backtest.bar_record import BarRecord


def bar_records_to_dicts(records: List[BarRecord]) -> List[dict]:
    """
    Convert BarRecord objects into flat dicts suitable for CSV export.
    decision_snapshot is JSON-serialized.
    """
    output: List[dict] = []

    for record in records:
        row = asdict(record)

        # Serialize decision_snapshot for CSV compatibility
        if "decision_snapshot" in row:
            row["decision_snapshot"] = json.dumps(
                row["decision_snapshot"],
                default=str
            )

        # Normalize timestamp
        if "timestamp" in row and hasattr(row["timestamp"], "isoformat"):
            row["timestamp"] = row["timestamp"].isoformat()

        output.append(row)

    return output

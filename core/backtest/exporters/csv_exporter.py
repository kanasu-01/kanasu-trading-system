import csv
from pathlib import Path
from typing import List, Dict


class CSVExporter:
    """
    Generic CSV exporter for bar-by-bar or trade-level data.
    """

    @staticmethod
    def export(
        records: List[Dict],
        filepath: str,
    ) -> None:
        if not records:
            raise ValueError("No records to export")

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=records[0].keys()
            )
            writer.writeheader()
            writer.writerows(records)

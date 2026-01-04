import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict


class TradeJournal:
    """
    Persistent trade journal.
    """

    def __init__(
        self,
        journal_dir: str = "journals",
        csv_filename: str = "trades.csv",
        json_filename: str = "trades.json",
    ):
        self.journal_path = Path(journal_dir)
        self.journal_path.mkdir(parents=True, exist_ok=True)

        self.csv_path = self.journal_path / csv_filename
        self.json_path = self.journal_path / json_filename

        self._ensure_csv_header()

    def log_trade(self, trade: Dict) -> None:
        record = trade.copy()
        record["timestamp"] = datetime.utcnow().isoformat()

        self._append_csv(record)
        self._append_json(record)

    def _ensure_csv_header(self) -> None:
        if self.csv_path.exists():
            return

        with open(self.csv_path, "w", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "timestamp",
                    "entry_price",
                    "exit_price",
                    "stop_price",
                    "quantity",
                    "direction",
                    "exit_reason",
                ],
            )
            writer.writeheader()

    def _append_csv(self, trade: Dict) -> None:
        with open(self.csv_path, "a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=trade.keys())
            writer.writerow(trade)

    def _append_json(self, trade: Dict) -> None:
        if self.json_path.exists():
            with open(self.json_path, "r") as f:
                data = json.load(f)
        else:
            data = []

        data.append(trade)

        with open(self.json_path, "w") as f:
            json.dump(data, f, indent=2)

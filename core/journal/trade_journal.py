import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Dict
from dataclasses import asdict
from core.entities.trade import Trade


class TradeJournal:
    """
    Persistent trade journal.
    """

    def __init__(
        self,
        session_id: str,
        journal_dir: str = "journals",
        csv_filename: str = "trades.csv",
        json_filename: str = "trades.jsonl",
    ):
        self.journal_path = Path(journal_dir) / session_id

        self.journal_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.csv_path = self.journal_path / csv_filename
        self.json_path = self.journal_path / json_filename
        self.fieldnames = [
            "timestamp",
            "session_id",
            "symbol",
            "entry_time",
            "entry_price",
            "exit_time",
            "exit_price",
            "stop_price",
            "quantity",
            "direction",
            "exit_reason",
            "gross_pnl",
            "transaction_cost",
            "pnl",
            "pnl_pct",
        ]
        self.session_id = session_id

        self._ensure_csv_header()

    def log_trade(self, trade: Trade) -> None:
        record = asdict(trade)
        record["session_id"] = self.session_id
        record["timestamp"] = datetime.utcnow().isoformat()

        self._append_csv(record)
        self._append_json(record)

    def _ensure_csv_header(self) -> None:
        if self.csv_path.exists():
            return

        with open(self.csv_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            writer.writeheader()

    def _append_csv(self, trade: Dict) -> None:
        with open(self.csv_path, "a", newline="") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=self.fieldnames,
            )
            writer.writerow(trade)

    def _append_json(
        self,
        trade: Dict,
    ) -> None:

        with open(self.json_path, "a") as f:

            json_record = json.dumps(
                trade,
                default=str,
            )

            f.write(json_record + "\n")

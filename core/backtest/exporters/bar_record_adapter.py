# core/backtest/exporters/bar_record_adapter.py

from dataclasses import asdict
from typing import List
from core.backtest.bar_record import BarRecord


def bar_records_to_dicts(records: List[BarRecord]) -> List[dict]:
    return [asdict(r) for r in records]

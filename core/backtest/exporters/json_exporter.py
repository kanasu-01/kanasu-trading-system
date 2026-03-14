import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


class JSONExporter:
    """
    Exports backtest records to JSON.

    Handles non-JSON types such as datetime automatically.
    """

    @staticmethod
    def _serializer(obj: Any):
        """                  
        Convert unsupported objects into JSON-safe values.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()

        # fallback for any unexpected type
        return str(obj)

    @staticmethod
    def export(records: List[Dict], filepath: str) -> None:
        if not records:
            raise ValueError("No records to export")

        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                records,
                f,
                indent=2,
                ensure_ascii=False,
                default=JSONExporter._serializer,
            )
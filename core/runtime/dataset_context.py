from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetContext:
    """
    Dataset identity for runtime execution.

    Future:
    - exchange
    - datasource
    - corporate action metadata
    - timezone
    """

    symbol: str
    timeframe: str | None = None

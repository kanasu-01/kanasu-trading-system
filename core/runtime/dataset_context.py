from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetContext:
    """
    Dataset identity for runtime execution.

    Future:
    - exchange
    - timeframe
    - datasource
    - corporate action metadata
    - timezone
    """

    symbol: str

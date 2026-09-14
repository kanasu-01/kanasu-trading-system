from enum import Enum


class HistoricalSourcePolicy(Enum):
    LOCAL_ONLY = "LOCAL_ONLY"
    LOCAL_FIRST = "LOCAL_FIRST"
    PROVIDER_BACKED = "PROVIDER_BACKED"

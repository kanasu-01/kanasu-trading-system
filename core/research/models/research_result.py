from dataclasses import dataclass
from typing import Any


@dataclass
class ResearchResult:
    """
    Unified research execution result.

    MVP v1 scope:
    - simple execution status
    - optional message
    - optional returned data
    """

    success: bool

    message: str = ""

    data: Any | None = None

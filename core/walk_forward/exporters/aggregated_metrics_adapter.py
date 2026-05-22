from typing import Dict, Any

from core.walk_forward.result import (
    WalkForwardResult,
)


def aggregated_metrics_to_dict(
    result: WalkForwardResult,
) -> Dict[str, Any]:
    """
    Convert aggregated walk-forward metrics
    into export-friendly dictionary.
    """

    return {
        **result.aggregated_metrics,
        "verdict": result.verdict,
    }

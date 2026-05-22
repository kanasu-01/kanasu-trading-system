from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass(frozen=True)
class OptimizationEvaluation:
    """
    Single parameter evaluation result.
    """

    params: Dict[str, Any]
    score: float
    metrics: Dict[str, Any]


@dataclass(frozen=True)
class OptimizationResult:
    """
    Canonical optimization result.

    Preserves optimization lineage for:
    - transparency
    - robustness analysis
    - parameter stability analysis
    - future research tooling
    """

    best_params: Dict[str, Any]
    best_score: float

    # All evaluated parameter results
    evaluations: List[OptimizationEvaluation]

"""M8 baseline anomaly-detection evaluation."""

from .config import EvaluationConfig
from .pipeline import EvaluationResult, GroundTruthError, run_evaluation

__all__ = [
    "EvaluationConfig",
    "EvaluationResult",
    "GroundTruthError",
    "run_evaluation",
]

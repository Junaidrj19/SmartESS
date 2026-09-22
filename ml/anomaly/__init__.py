"""Baseline unsupervised anomaly detection (M7)."""

from .aggregate import aggregate_module_summary, module_status
from .baseline import (
    BASELINE_SIGNALS,
    BASELINE_THRESHOLD,
    BASELINE_TYPE,
    compute_statistical_baseline,
)
from .config import AnomalyConfig, DETECTOR_VERSION
from .pipeline import AnomalyRunResult, BlockedFeaturesError, run_anomaly_pipeline

__all__ = [
    "AnomalyConfig",
    "AnomalyRunResult",
    "BASELINE_SIGNALS",
    "BASELINE_THRESHOLD",
    "BASELINE_TYPE",
    "BlockedFeaturesError",
    "DETECTOR_VERSION",
    "aggregate_module_summary",
    "compute_statistical_baseline",
    "module_status",
    "run_anomaly_pipeline",
]

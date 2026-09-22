"""M8 evaluation configuration and constants.

M8 is an evaluation-only layer over the frozen M7 artifacts. It never retrains,
never changes thresholds, and never writes outside ``ml/datasets/evaluation/``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

AUTHORITATIVE_MODEL_ID = "iforest-v1-syn-sic-pc-dev-001-s20260922"
FEATURE_VERSION = "v1"
DETECTOR_VERSION = "v1"

# Statistical baseline module flag threshold (frozen M7 baseline threshold).
STATISTICAL_BASELINE_THRESHOLD = 3.0

# Health label: any module that is not healthy is a positive (degradation/terminal).
HEALTHY_LABEL = "healthy"

# Relative GT path inside a dataset directory.
GROUND_TRUTH_RELATIVE = Path("ground_truth/ground-truth.parquet")

# Supported scenario and data origin for this frozen dataset. Used for GT validation.
EXPECTED_SCENARIO = "degradation_benchmark"
EXPECTED_DATA_ORIGIN = "synthetic"

# Severity bins for descriptive stratification of continuous degradation_severity.
SEVERITY_BINS = (0.0, 0.25, 0.5, 1.0, float("inf"))
SEVERITY_LABELS = ("none", "low", "medium", "high")


@dataclass(frozen=True)
class EvaluationConfig:
    """Configuration for a single M8 evaluation run."""

    model_id: str = AUTHORITATIVE_MODEL_ID
    feature_version: str = FEATURE_VERSION
    detector_version: str = DETECTOR_VERSION
    baseline_threshold: float = STATISTICAL_BASELINE_THRESHOLD
    scores_dir: str = "ml/datasets/scores"
    models_dir: str = "ml/models"
    output_root: str = "ml/datasets/evaluation"

    @property
    def score_dir(self) -> Path:
        return Path(self.scores_dir) / self.model_id

    @property
    def model_dir(self) -> Path:
        return Path(self.models_dir) / self.model_id

    @property
    def output_dir(self) -> Path:
        return Path(self.output_root) / self.model_id

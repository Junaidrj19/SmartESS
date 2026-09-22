"""M7 baseline anomaly detection configuration."""

from __future__ import annotations

from dataclasses import dataclass

from ml.features.definitions import FEATURE_VERSION

DETECTOR_VERSION = "v1"
ALGORITHM_ISOLATION_FOREST = "isolation_forest"


@dataclass
class AnomalyConfig:
    """Configuration for the v1 unsupervised detector."""

    detector_version: str = DETECTOR_VERSION
    feature_version: str = FEATURE_VERSION
    algorithm: str = ALGORITHM_ISOLATION_FOREST
    n_estimators: int = 100
    contamination: float = 0.10
    max_samples: str | int = "auto"
    random_state: int = 20260922
    test_lot_fraction: float = 0.4
    min_train_lots: int = 1
    output_directory: str = "ml/models"
    scores_directory: str = "ml/datasets/scores"
    # Training uses unlabeled observation features from train lots only.
    # Ground-truth health labels are never used to select the training set.
    train_on_unlabeled: bool = True

    def __post_init__(self) -> None:
        if self.detector_version != DETECTOR_VERSION:
            raise ValueError(f"M7 defines detector_version={DETECTOR_VERSION} only")
        if self.feature_version != FEATURE_VERSION:
            raise ValueError(f"M7 consumes feature_version={FEATURE_VERSION} only")
        if self.algorithm != ALGORITHM_ISOLATION_FOREST:
            raise ValueError(f"M7 baseline algorithm is {ALGORITHM_ISOLATION_FOREST}")
        if not 0 < self.contamination < 0.5:
            raise ValueError("contamination must be in (0, 0.5)")
        if self.n_estimators < 1:
            raise ValueError("n_estimators must be positive")
        if not 0 < self.test_lot_fraction < 1:
            raise ValueError("test_lot_fraction must be in (0, 1)")

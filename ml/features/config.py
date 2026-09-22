"""Feature engineering configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .definitions import FEATURE_VERSION, WINDOW_SIZES_V1


DEFAULT_MODULE_PROFILE_PATH = "examples/module-profiles/sic-reference-module.json"
DEFAULT_T_REF_C = 25.0
DEFAULT_T_HOT_C = 150.0


@dataclass
class FeatureConfig:
    """Configuration for the v1 feature engineering pipeline."""

    feature_version: str = FEATURE_VERSION
    baseline_window_fraction: float = 0.1
    baseline_min_cycles: int = 10
    window_sizes: List[int] = field(default_factory=lambda: list(WINDOW_SIZES_V1))
    t_ref_C: float = DEFAULT_T_REF_C
    t_hot_C: float = DEFAULT_T_HOT_C
    rds_on_ref_mohm: Optional[float] = None
    rds_on_hot_mohm: Optional[float] = None
    module_profile_path: Optional[str] = None
    target_cycles: Optional[int] = None
    compute_observation_features: bool = True
    compute_module_features: bool = True
    output_directory: str = "ml/datasets/features"
    extra_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.feature_version != FEATURE_VERSION:
            raise ValueError(
                f"M6 defines {FEATURE_VERSION} only; changing definitions requires a new feature version, not {self.feature_version}"
            )
        if not 0 < self.baseline_window_fraction <= 1:
            raise ValueError("baseline_window_fraction must be between 0 and 1")
        if self.baseline_min_cycles < 1:
            raise ValueError("baseline_min_cycles must be positive")
        if any(w <= 0 for w in self.window_sizes):
            raise ValueError("All window sizes must be positive")
        if self.t_hot_C <= self.t_ref_C:
            raise ValueError("t_hot_C must be greater than t_ref_C")
        if self.target_cycles is not None and self.target_cycles <= 0:
            raise ValueError("target_cycles must be a positive integer")
        if self.rds_on_ref_mohm is not None and self.rds_on_ref_mohm <= 0:
            raise ValueError("rds_on_ref_mohm must be positive")
        if self.rds_on_hot_mohm is not None and self.rds_on_hot_mohm <= 0:
            raise ValueError("rds_on_hot_mohm must be positive")

    @property
    def reference_temperature(self) -> float:
        return self.t_ref_C

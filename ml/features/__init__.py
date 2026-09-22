"""Versioned feature engineering package for SmartESS."""

from .config import FeatureConfig
from .definitions import FEATURE_VERSION, FeatureDefinition, FeatureSet, create_v1_feature_set
from .output import FeatureOutputWriter
from .pipeline import BlockedDatasetError, build_features_from_dataset
from .temperature import TemperatureNormalizer
from .transform import FeatureTransformer
from .validation import FeatureValidator
from .windows import WindowCalculator

feature_version = FEATURE_VERSION

__all__ = [
    "FeatureConfig",
    "FeatureDefinition",
    "FeatureSet",
    "FeatureTransformer",
    "TemperatureNormalizer",
    "WindowCalculator",
    "FeatureOutputWriter",
    "FeatureValidator",
    "build_features_from_dataset",
    "BlockedDatasetError",
    "feature_version",
    "FEATURE_VERSION",
    "create_v1_feature_set",
]

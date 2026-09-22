"""Feature validation against the authoritative v1 registry."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .definitions import (
    FEATURE_VERSION,
    FORBIDDEN_FEATURE_COLUMNS,
    MODULE_IDENTIFIER_COLUMNS,
    OBSERVATION_IDENTIFIER_COLUMNS,
    FeatureSet,
)

logger = logging.getLogger(__name__)


class FeatureValidator:
    """Validates feature engineering outputs against the registry."""

    def __init__(self, feature_set: FeatureSet):
        self.feature_set = feature_set

    def validate_features(
        self,
        observation_features: pd.DataFrame,
        module_features: pd.DataFrame,
        source_dataset_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        available_signals: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str]]:
        del available_signals  # schema is definition-driven, never dataset-missingness-driven
        errors: List[str] = []
        errors.extend(self._validate_observation_features(observation_features))
        errors.extend(self._validate_module_features(module_features))
        errors.extend(self._validate_cross_consistency(observation_features, module_features))
        errors.extend(self._validate_no_forbidden_columns(observation_features, module_features))
        errors.extend(self._validate_feature_counts(observation_features, module_features))
        if metadata is not None:
            errors.extend(self._validate_metadata(metadata, observation_features, module_features))

        is_valid = len(errors) == 0
        if is_valid:
            logger.info("Feature validation passed for dataset %s", source_dataset_id)
        else:
            logger.warning(
                "Feature validation failed for dataset %s with %s errors",
                source_dataset_id,
                len(errors),
            )
        return is_valid, errors

    def _validate_observation_features(self, df: pd.DataFrame) -> List[str]:
        errors: List[str] = []
        if df.empty:
            errors.append("Observation features: DataFrame is empty")
            return errors

        expected = self.feature_set.observation_parquet_columns()
        actual = list(df.columns)
        if actual != expected:
            missing = [c for c in expected if c not in actual]
            unexpected = [c for c in actual if c not in expected]
            if missing:
                errors.append(f"Observation features: Missing expected feature columns: {missing}")
            if unexpected:
                errors.append(
                    f"Observation features: Unexpected feature columns not in registry: {unexpected}"
                )
            if not missing and not unexpected and actual != expected:
                errors.append("Observation features: Column order does not match authoritative registry")

        if pd.Index(actual).duplicated().any():
            dups = list(pd.Index(actual)[pd.Index(actual).duplicated()])
            errors.append(f"Observation features: Duplicate feature columns: {dups}")

        for col in OBSERVATION_IDENTIFIER_COLUMNS:
            if col not in df.columns:
                errors.append(f"Observation features: Missing required identifier: {col}")

        if "module_id" in df.columns and "cycle_number" in df.columns:
            if df.duplicated(["module_id", "cycle_number"]).any():
                n_dup = int(df.duplicated(["module_id", "cycle_number"]).sum())
                errors.append(f"Observation features: Duplicate module/cycle rows: {n_dup}")
            for module_id, group in df.groupby("module_id", sort=False):
                if not group["cycle_number"].is_monotonic_increasing:
                    errors.append(
                        f"Observation features: Cycle numbers not monotonically increasing for module {module_id}"
                    )
                    break

        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            values = pd.to_numeric(df[col], errors="coerce").to_numpy(dtype=float)
            inf_count = int(np.isinf(values).sum())
            if inf_count > 0:
                errors.append(f"Observation features: Column {col} contains {inf_count} infinite values")
        return errors

    def _validate_module_features(self, df: pd.DataFrame) -> List[str]:
        errors: List[str] = []
        if df.empty:
            errors.append("Module features: DataFrame is empty")
            return errors

        expected = self.feature_set.module_parquet_columns()
        actual = list(df.columns)
        missing = [c for c in expected if c not in actual]
        unexpected = [c for c in actual if c not in expected]
        if missing:
            errors.append(f"Module features: Missing expected feature columns: {missing}")
        if unexpected:
            errors.append(f"Module features: Unexpected feature columns not in registry: {unexpected}")
        if pd.Index(actual).duplicated().any():
            dups = list(pd.Index(actual)[pd.Index(actual).duplicated()])
            errors.append(f"Module features: Duplicate feature columns: {dups}")
        if "module_id" not in df.columns:
            errors.append("Module features: Missing required column: module_id")
        elif df["module_id"].duplicated().any():
            errors.append(
                f"Module features: Duplicate module IDs found: {int(df['module_id'].duplicated().sum())}"
            )
        for col in MODULE_IDENTIFIER_COLUMNS:
            if col not in df.columns:
                errors.append(f"Module features: Missing required identifier: {col}")
        return errors

    def _validate_cross_consistency(
        self,
        observation_features: pd.DataFrame,
        module_features: pd.DataFrame,
    ) -> List[str]:
        errors: List[str] = []
        if observation_features.empty or module_features.empty:
            return errors
        obs_modules = set(observation_features["module_id"].unique())
        mod_modules = set(module_features["module_id"].unique())
        missing_in_module = obs_modules - mod_modules
        if missing_in_module:
            errors.append(
                f"Cross-validation: Modules in observation features missing from module features: {missing_in_module}"
            )
        extra_in_module = mod_modules - obs_modules
        if extra_in_module:
            errors.append(
                f"Cross-validation: Modules in module features missing from observation features: {extra_in_module}"
            )
        return errors

    def _validate_no_forbidden_columns(
        self,
        observation_features: pd.DataFrame,
        module_features: pd.DataFrame,
    ) -> List[str]:
        errors: List[str] = []
        obs_forbidden = set(observation_features.columns) & FORBIDDEN_FEATURE_COLUMNS
        if obs_forbidden:
            errors.append(f"Forbidden columns found in observation features: {sorted(obs_forbidden)}")
        mod_forbidden = set(module_features.columns) & FORBIDDEN_FEATURE_COLUMNS
        if mod_forbidden:
            errors.append(f"Forbidden columns found in module features: {sorted(mod_forbidden)}")
        return errors

    def _validate_feature_counts(
        self,
        observation_features: pd.DataFrame,
        module_features: pd.DataFrame,
        available_signals: Optional[List[str]] = None,
    ) -> List[str]:
        del available_signals
        errors: List[str] = []
        expected_obs = self.feature_set.count_observation_parquet_columns()
        actual_obs = len(observation_features.columns)
        if actual_obs != expected_obs:
            errors.append(
                f"Feature count: Observation column count mismatch: expected {expected_obs}, got {actual_obs}"
            )
        expected_feat = self.feature_set.count_observation_features()
        actual_feat = actual_obs - len(OBSERVATION_IDENTIFIER_COLUMNS)
        if actual_feat != expected_feat:
            errors.append(
                f"Feature count: Observation feature count mismatch: expected {expected_feat}, got {actual_feat}"
            )
        expected_mod = self.feature_set.count_module_parquet_columns()
        actual_mod = len(module_features.columns)
        if actual_mod != expected_mod:
            errors.append(
                f"Feature count: Module column count mismatch: expected {expected_mod}, got {actual_mod}"
            )
        return errors

    def _validate_metadata(
        self,
        metadata: Dict[str, Any],
        observation_features: pd.DataFrame,
        module_features: pd.DataFrame,
    ) -> List[str]:
        errors: List[str] = []
        version = metadata.get("feature_version")
        if version != FEATURE_VERSION or version != self.feature_set.version:
            errors.append(
                f"Metadata mismatch: invalid feature_version {version!r}; expected {FEATURE_VERSION}"
            )
        counts = metadata.get("feature_counts") or {}
        expected_obs = self.feature_set.count_observation_parquet_columns()
        expected_feat = self.feature_set.count_observation_features()
        expected_mod = self.feature_set.count_module_parquet_columns()
        if counts.get("observation_columns") not in (None, expected_obs, len(observation_features.columns)):
            if counts.get("observation_columns") != len(observation_features.columns):
                errors.append("Metadata mismatch: observation_columns does not match Parquet schema")
        if counts.get("observation_feature_columns") not in (None, expected_feat):
            if counts.get("observation_feature_columns") != expected_feat:
                errors.append("Metadata mismatch: observation_feature_columns does not match registry")
        if counts.get("module_columns") not in (None, expected_mod, len(module_features.columns)):
            if counts.get("module_columns") != len(module_features.columns):
                errors.append("Metadata mismatch: module_columns does not match Parquet schema")

        designation = metadata.get("feature_designation") or {}
        if designation.get("module_features_is_retrospective") is False:
            errors.append("Retrospective metadata mismatch: module features must have is_retrospective=true")
        if designation.get("observation_features_is_causal") is False:
            errors.append("Metadata mismatch: observation features must be causal")
        return errors

    def validate_leakage_prevention(
        self,
        original_telemetry: pd.DataFrame,
        observation_features: pd.DataFrame,
        cycle_cutoff: int,
        modified_observation_features: Optional[pd.DataFrame] = None,
    ) -> Tuple[bool, List[str]]:
        """Compare observation features at cycles <= cutoff. Requires a modified rerun."""

        errors: List[str] = []
        if modified_observation_features is None:
            errors.append("Leakage check requires features from modified future telemetry")
            return False, errors
        feature_cols = self.feature_set.observation_feature_names()
        keys = ["module_id", "cycle_number"]
        a = observation_features[observation_features["cycle_number"] <= cycle_cutoff][keys + feature_cols].sort_values(keys)
        b = modified_observation_features[modified_observation_features["cycle_number"] <= cycle_cutoff][keys + feature_cols].sort_values(keys)
        if len(a) != len(b):
            errors.append("Leakage check: row counts at cutoff differ")
            return False, errors
        for col in feature_cols:
            if not np.allclose(a[col].to_numpy(dtype=float), b[col].to_numpy(dtype=float), equal_nan=True):
                errors.append(f"Non-causal feature behavior: {col} changed at cycles <= {cycle_cutoff}")
        return len(errors) == 0, errors

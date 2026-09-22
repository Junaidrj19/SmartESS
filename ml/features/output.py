"""Feature output writing: parquet + registry-derived metadata."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from .definitions import (
    BASELINE_ROLLING_SIGNALS,
    ELECTRICAL_RAW_SIGNALS,
    FEATURE_VERSION,
    MODULE_IDENTIFIER_COLUMNS,
    MODULE_METADATA_COLUMNS,
    OBSERVATION_IDENTIFIER_COLUMNS,
    THERMAL_RAW_SIGNALS,
    TREND_SIGNALS,
    VF_BASELINE_ROLLING_POLICY,
    FeatureSet,
    create_v1_feature_set,
)


class FeatureOutputWriter:
    """Writes feature datasets to disk with metadata derived from the registry."""

    def __init__(self, output_directory: str):
        self.output_directory = output_directory
        os.makedirs(output_directory, exist_ok=True)

    def write_features(
        self,
        observation_features: pd.DataFrame,
        module_features: pd.DataFrame,
        feature_version: str,
        source_dataset_id: str,
        schema_version: str,
        generation_metadata: Dict[str, Any],
        validation_metadata: Dict[str, Any],
        window_config: Dict[str, Any],
        baseline_config: Dict[str, Any],
        temperature_config: Dict[str, Any],
        feature_set: Optional[FeatureSet] = None,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, str]:
        if feature_version != FEATURE_VERSION:
            raise ValueError(f"Unsupported feature version {feature_version}")
        feature_set = feature_set or create_v1_feature_set(window_config.get("window_sizes"))

        version_dir = os.path.join(self.output_directory, feature_version)
        os.makedirs(version_dir, exist_ok=True)

        obs_path = os.path.join(version_dir, "observation-features.parquet")
        mod_path = os.path.join(version_dir, "module-features.parquet")
        metadata_path = os.path.join(version_dir, "feature-metadata.json")

        self._write_dataframe_to_parquet(observation_features, obs_path)
        self._write_dataframe_to_parquet(module_features, mod_path)

        metadata = self.build_metadata(
            observation_features=observation_features,
            module_features=module_features,
            feature_version=feature_version,
            source_dataset_id=source_dataset_id,
            schema_version=schema_version,
            generation_metadata=generation_metadata,
            validation_metadata=validation_metadata,
            window_config=window_config,
            baseline_config=baseline_config,
            temperature_config=temperature_config,
            feature_set=feature_set,
            extra_metadata=extra_metadata,
        )
        with open(metadata_path, "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2, default=str)
            handle.write("\n")

        return {
            "observation_features": obs_path,
            "module_features": mod_path,
            "feature_metadata": metadata_path,
        }

    def build_metadata(
        self,
        observation_features: pd.DataFrame,
        module_features: pd.DataFrame,
        feature_version: str,
        source_dataset_id: str,
        schema_version: str,
        generation_metadata: Dict[str, Any],
        validation_metadata: Dict[str, Any],
        window_config: Dict[str, Any],
        baseline_config: Dict[str, Any],
        temperature_config: Dict[str, Any],
        feature_set: FeatureSet,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        category_counts = feature_set.category_feature_counts()
        metadata: Dict[str, Any] = {
            "feature_version": feature_version,
            "feature_definition_registry_version": feature_set.version,
            "source_dataset_id": source_dataset_id,
            "source_schema_version": schema_version,
            "generation_metadata": generation_metadata,
            "validation_metadata": validation_metadata,
            "feature_definitions": {
                "version": feature_set.version,
                "feature_definition_count": feature_set.count_definitions(),
                "window_sizes": list(feature_set.window_sizes),
                "vf_baseline_rolling_policy": VF_BASELINE_ROLLING_POLICY,
                "features": feature_set.registry_records(),
            },
            "signal_sets": {
                "electrical_raw": list(ELECTRICAL_RAW_SIGNALS),
                "thermal_raw": list(THERMAL_RAW_SIGNALS),
                "baseline_rolling": list(BASELINE_ROLLING_SIGNALS),
                "trend": list(TREND_SIGNALS),
                "vf_in_baseline_rolling": False,
            },
            "identifier_columns": {
                "observation": list(OBSERVATION_IDENTIFIER_COLUMNS),
                "module": list(MODULE_IDENTIFIER_COLUMNS),
                "module_metadata": list(MODULE_METADATA_COLUMNS),
            },
            "feature_counts": {
                "observation_rows": int(len(observation_features)),
                "module_rows": int(len(module_features)),
                "observation_identifier_columns": len(OBSERVATION_IDENTIFIER_COLUMNS),
                "observation_feature_columns": feature_set.count_observation_features(),
                "observation_columns": feature_set.count_observation_parquet_columns(),
                "observation_feature_columns_by_family": category_counts,
                "module_aggregate_columns": len(feature_set.module_aggregate_columns()),
                "module_metadata_columns": len(MODULE_METADATA_COLUMNS),
                "module_identifier_columns": len(MODULE_IDENTIFIER_COLUMNS),
                "module_columns": feature_set.count_module_parquet_columns(),
                "actual_observation_columns": int(len(observation_features.columns)),
                "actual_module_columns": int(len(module_features.columns)),
            },
            "feature_designation": {
                "observation_features_is_causal": True,
                "observation_features_is_retrospective": False,
                "module_features_is_causal": False,
                "module_features_is_retrospective": True,
                "module_features_boundary": (
                    "Module-level aggregates are computed over the complete trajectory. "
                    "They are retrospective and must not be used as observation-time features "
                    "for detecting an anomaly at an earlier cycle."
                ),
            },
            "window_configuration": window_config,
            "baseline_configuration": baseline_config,
            "temperature_normalization_configuration": temperature_config,
            "creation_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "provenance": {
                "feature_engineering_version": feature_version,
                "component": "SmartESS Feature Engineering",
                "processing_step": "feature_transformation",
            },
        }
        if extra_metadata:
            metadata["extra"] = extra_metadata
        return metadata

    def _write_dataframe_to_parquet(self, df: pd.DataFrame, filepath: str) -> None:
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(table, filepath)

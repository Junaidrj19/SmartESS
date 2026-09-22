"""Dataset-facing feature build pipeline. Loads telemetry and declared context only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Tuple

import pandas as pd

from .config import DEFAULT_MODULE_PROFILE_PATH, FeatureConfig
from .definitions import FEATURE_VERSION
from .output import FeatureOutputWriter
from .temperature import TemperatureNormalizer
from .transform import FeatureTransformer
from .validation import FeatureValidator

SOURCE_ARTIFACTS = (
    "telemetry/telemetry.parquet",
    "ground_truth/ground-truth.parquet",
    "metadata/dataset.json",
    "metadata/generation-config.json",
    "metadata/assumptions.json",
    "provenance/provenance.json",
)


class BlockedDatasetError(RuntimeError):
    """Raised when M5 overall status is BLOCKED."""


@dataclass
class FeatureBuildResult:
    observation_features: pd.DataFrame
    module_features: pd.DataFrame
    metadata: Dict[str, Any]
    output_paths: Dict[str, str]
    elapsed_s: float
    source_hashes: Dict[str, str]


def _read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot_source_artifacts(dataset_dir: Path) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for relative in SOURCE_ARTIFACTS:
        path = dataset_dir / relative
        if path.exists():
            hashes[relative] = _file_sha256(path)
    return hashes


def load_validation_metadata(dataset_dir: Path) -> Dict[str, Any]:
    report_path = dataset_dir / "validation" / "validation-report.json"
    if not report_path.exists():
        return {
            "validation_status": "unknown",
            "validator_version": None,
            "validation_timestamp": None,
            "source_dataset_id": None,
            "validation_report_reference": None,
        }
    report = _read_json(report_path)
    status = report.get("overall_status", "unknown")
    if status == "BLOCKED":
        raise BlockedDatasetError(f"Refusing to process BLOCKED dataset {dataset_dir}")
    return {
        "validation_status": status,
        "validator_version": report.get("validator_version"),
        "validation_timestamp": report.get("validation_timestamp"),
        "source_dataset_id": report.get("dataset_id"),
        "validation_report_reference": "validation/validation-report.json",
    }


def load_declared_context(dataset_dir: Path) -> Tuple[str, str, int, TemperatureNormalizer, Dict[str, Any]]:
    metadata_path = dataset_dir / "metadata" / "dataset.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing dataset metadata: {metadata_path}")
    dataset_meta = _read_json(metadata_path)
    source_dataset_id = dataset_meta.get("dataset_id")
    if not source_dataset_id:
        raise ValueError("dataset.json must include dataset_id")
    schema_version = dataset_meta.get("schema_version_telemetry", "1.0.0")
    target_cycles = dataset_meta.get("target_cycles")
    if target_cycles is None:
        raise ValueError(
            "target_cycles is missing from dataset.json; cannot compute causal normalized_cycle_position"
        )

    gen_config_path = dataset_dir / "metadata" / "generation-config.json"
    module_profile_path = DEFAULT_MODULE_PROFILE_PATH
    t_ref_C = 25.0
    t_hot_C = 150.0
    if gen_config_path.exists():
        gen_config = _read_json(gen_config_path)
        configured_path = gen_config.get("module_profile_path")
        if configured_path:
            candidate = Path(configured_path)
            module_profile_path = str(candidate if candidate.is_absolute() else Path.cwd() / candidate)
        temp_model = gen_config.get("temperature_model") or {}
        if temp_model.get("t_ref_C") is not None:
            t_ref_C = float(temp_model["t_ref_C"])

    if not Path(module_profile_path).exists():
        module_profile_path = DEFAULT_MODULE_PROFILE_PATH

    normalizer = TemperatureNormalizer.from_module_profile_path(
        module_profile_path,
        t_ref_C=t_ref_C,
        t_hot_C=t_hot_C,
    )
    context = {
        "module_profile_path": module_profile_path,
        "t_ref_C": t_ref_C,
        "t_hot_C": t_hot_C,
        "rds_on_ref_mohm": normalizer.rds_on_ref_mohm,
        "rds_on_hot_mohm": normalizer.rds_on_hot_mohm,
        "target_cycles": int(target_cycles),
        "schema_version": schema_version,
        "dataset_id": source_dataset_id,
    }
    return source_dataset_id, schema_version, int(target_cycles), normalizer, context


def build_features_from_dataset(
    dataset_dir: str | Path,
    output_dir: str = "ml/datasets/features",
    feature_version: str = FEATURE_VERSION,
    write: bool = True,
) -> FeatureBuildResult:
    import time

    if feature_version != FEATURE_VERSION:
        raise ValueError(f"M6 defines {FEATURE_VERSION} only")

    dataset_path = Path(dataset_dir)
    telemetry_path = dataset_path / "telemetry" / "telemetry.parquet"
    if not telemetry_path.exists():
        raise FileNotFoundError(f"Telemetry file not found at {telemetry_path}")

    before_hashes = snapshot_source_artifacts(dataset_path)
    validation_metadata = load_validation_metadata(dataset_path)
    source_dataset_id, schema_version, target_cycles, normalizer, context = load_declared_context(dataset_path)

    telemetry_df = pd.read_parquet(telemetry_path)

    config = FeatureConfig(
        feature_version=feature_version,
        output_directory=output_dir,
        target_cycles=target_cycles,
        t_ref_C=normalizer.t_ref_C,
        t_hot_C=normalizer.t_hot_C,
        rds_on_ref_mohm=normalizer.rds_on_ref_mohm,
        rds_on_hot_mohm=normalizer.rds_on_hot_mohm,
        module_profile_path=context["module_profile_path"],
    )
    transformer = FeatureTransformer(config)
    started = time.perf_counter()
    observation_features, module_features = transformer.transform(telemetry_df)
    elapsed_s = time.perf_counter() - started

    writer = FeatureOutputWriter(output_dir)
    window_config = {"window_sizes": list(config.window_sizes), "center": False, "causal": True}
    baseline_config = {
        "baseline_window_fraction": config.baseline_window_fraction,
        "baseline_min_cycles": config.baseline_min_cycles,
        "rule": "min(max(baseline_min_cycles, int(n_obs * baseline_window_fraction)), n_obs)",
        "uses_ground_truth": False,
        "causal": True,
    }
    temperature_config = {
        **normalizer.get_normalization_info(),
        "module_profile_path": context["module_profile_path"],
    }
    metadata = writer.build_metadata(
        observation_features=observation_features,
        module_features=module_features,
        feature_version=feature_version,
        source_dataset_id=source_dataset_id,
        schema_version=schema_version,
        generation_metadata={
            "source": "synthetic_dataset_generator",
            "source_dataset_id": source_dataset_id,
        },
        validation_metadata=validation_metadata,
        window_config=window_config,
        baseline_config=baseline_config,
        temperature_config=temperature_config,
        feature_set=transformer.feature_set,
        extra_metadata={"runtime_seconds": elapsed_s},
    )

    validator = FeatureValidator(transformer.feature_set)
    is_valid, errors = validator.validate_features(
        observation_features,
        module_features,
        source_dataset_id,
        metadata=metadata,
    )
    if not is_valid:
        raise ValueError("Feature validation failed:\n" + "\n".join(f"  - {err}" for err in errors))

    output_paths: Dict[str, str] = {}
    if write:
        output_paths = writer.write_features(
            observation_features=observation_features,
            module_features=module_features,
            feature_version=feature_version,
            source_dataset_id=source_dataset_id,
            schema_version=schema_version,
            generation_metadata=metadata["generation_metadata"],
            validation_metadata=validation_metadata,
            window_config=window_config,
            baseline_config=baseline_config,
            temperature_config=temperature_config,
            feature_set=transformer.feature_set,
            extra_metadata={"runtime_seconds": elapsed_s},
        )

    after_hashes = snapshot_source_artifacts(dataset_path)
    if before_hashes != after_hashes:
        raise RuntimeError("Feature generation mutated source dataset artifacts")

    return FeatureBuildResult(
        observation_features=observation_features,
        module_features=module_features,
        metadata=metadata,
        output_paths=output_paths,
        elapsed_s=elapsed_s,
        source_hashes=after_hashes,
    )

"""Deterministic checks for generated synthetic datasets.

Failures are raised. Invalid data is not silently repaired.
"""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from domain.module_profiles.models import ModuleProfile
from domain.telemetry.enums import DataOrigin
from domain.telemetry.models import FORBIDDEN_TELEMETRY_FIELDS, TelemetryRecord
from domain.telemetry.validation import parse_telemetry_record
from domain.test_profiles.models import TestProfile
from ml.generators.synthetic.config import GenerationConfig, Mechanism, Scenario
from ml.generators.synthetic.sensors import DERIVED, UNITS


FORBIDDEN_IN_TELEMETRY_COLUMNS = FORBIDDEN_TELEMETRY_FIELDS | {
    "degradation_mechanism",
    "health_state",
    "onset_cycle",
    "degradation_stage",
    "rate_scale",
    "mechanism_model",
}


class DatasetValidationError(ValueError):
    pass


def _fail(message: str) -> None:
    raise DatasetValidationError(message)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def reconstruct_record(row: pd.Series, channels: list[str]) -> dict[str, Any]:
    measurements = []
    for name in channels:
        status = str(row[f"{name}_status"])
        origin = str(row[f"{name}_origin"])
        unit = str(row[f"{name}_unit"])
        value = row[name]
        missing = status == "missing" or value is None or pd.isna(value)
        if name in DERIVED and status == "missing":
            # M3 forbids origin=derived with status=missing; omit the channel.
            continue
        item: dict[str, Any] = {
            "parameter": name,
            "status": status,
            "origin": origin,
        }
        if status == "missing":
            if not missing:
                _fail(f"missing {name} has a numeric value on {row['telemetry_id']}")
        elif status in {"valid", "estimated", "derived"}:
            if missing:
                _fail(f"{status} {name} missing numeric value on {row['telemetry_id']}")
            number = float(value)
            if not math.isfinite(number):
                _fail(f"non-finite {name} on {row['telemetry_id']}")
            item["value"] = number
            item["unit"] = unit
            if origin == "derived":
                item["derivation"] = {
                    "method": "synthetic_lumped_rds_temperature_map"
                    if name == "RDS_on"
                    else "synthetic_generator_derived",
                    "notes": "Simulator derivation; not a laboratory procedure.",
                }
        elif status == "invalid":
            if not missing:
                number = float(value)
                if not math.isfinite(number):
                    _fail(f"NaN/Inf not allowed even on invalid {name} ({row['telemetry_id']})")
                item["value"] = number
                item["unit"] = unit
        measurements.append(item)
        if name in DERIVED and origin != "derived" and status != "missing":
            _fail(f"{name} must be origin=derived")

    return {
        "schema_version": row["schema_version"],
        "telemetry_id": row["telemetry_id"],
        "module_id": row["module_id"],
        "test_id": row["test_id"],
        "lot_id": row["lot_id"],
        "dataset_id": row["dataset_id"],
        "timestamp": row["timestamp"],
        "cycle_number": int(row["cycle_number"]),
        "cycle_phase": row["cycle_phase"],
        "measurements": measurements,
        "provenance": {
            "data_origin": row["data_origin"],
            "source_type": row["source_type"],
            "source_dataset": row["source_dataset"],
            "notes": row["provenance_notes"],
        },
    }


def _validate_pydantic_sample(telemetry: pd.DataFrame, channels: list[str], *, limit: int | None) -> int:
    if limit is None:
        sample = telemetry
    else:
        n = min(limit, len(telemetry))
        sample = telemetry.sample(n=n, random_state=0) if n < len(telemetry) else telemetry
    count = 0
    for _, row in sample.iterrows():
        payload = reconstruct_record(row, channels)
        parse_telemetry_record(payload)
        count += 1
    return count


def validate_generated_dataset(
    dataset_dir: Path,
    *,
    config: GenerationConfig,
    module_profile: ModuleProfile,
    test_profile: TestProfile,
    target_cycles: int,
    n_obs_nominal: int,
    latent_end_severity,
    population_mechanisms,
    population_onset,
    population_module_ids,
    pydantic_record_limit: int | None = 400,
) -> None:
    telemetry_path = dataset_dir / "telemetry" / "telemetry.parquet"
    gt_path = dataset_dir / "ground_truth" / "ground-truth.parquet"
    if not telemetry_path.is_file() or not gt_path.is_file():
        _fail("expected parquet outputs are missing")

    telemetry = pd.read_parquet(telemetry_path)
    ground = pd.read_parquet(gt_path)
    dataset = _load_json(dataset_dir / "metadata" / "dataset.json")
    written_config = _load_json(dataset_dir / "metadata" / "generation-config.json")
    assumptions = _load_json(dataset_dir / "metadata" / "assumptions.json")
    provenance = _load_json(dataset_dir / "provenance" / "provenance.json")

    if dataset.get("data_origin") != DataOrigin.SYNTHETIC.value:
        _fail("dataset metadata data_origin must be synthetic")
    if dataset.get("random_seed") != config.seed:
        _fail("dataset metadata seed mismatch")
    if dataset.get("generator_version") != config.generator_version:
        _fail("generator_version mismatch")
    if written_config.get("seed") != config.seed:
        _fail("generation-config seed mismatch")
    if "disclaimer" not in assumptions:
        _fail("assumptions.json missing disclaimer")
    if provenance.get("source_references") != []:
        _fail("do not invent source references")

    illegal = FORBIDDEN_IN_TELEMETRY_COLUMNS.intersection(telemetry.columns)
    if illegal:
        _fail(f"telemetry contains forbidden ground-truth/ML columns: {sorted(illegal)}")

    if telemetry["data_origin"].ne("synthetic").any():
        _fail("every telemetry row must have data_origin=synthetic")
    if telemetry["test_id"].ne(test_profile.test_id).any():
        _fail("telemetry test_id must match TestProfile")
    if telemetry["dataset_id"].ne(config.dataset_id).any():
        _fail("telemetry dataset_id mismatch")

    gt_modules = set(ground["module_id"].astype(str))
    tel_modules = set(telemetry["module_id"].astype(str))
    if gt_modules != tel_modules:
        _fail("ground truth and telemetry module_id sets differ")
    if gt_modules != set(map(str, population_module_ids)):
        _fail("ground truth module ids differ from generated population")
    if len(ground) != config.n_modules:
        _fail(f"expected {config.n_modules} ground-truth rows, got {len(ground)}")
    if ground["lot_id"].isna().any() or telemetry["lot_id"].isna().any():
        _fail("lot_id must be present")
    gt_lots = set(ground["lot_id"].astype(str))
    tel_lots = set(telemetry["lot_id"].astype(str))
    if gt_lots != tel_lots:
        _fail("lot ids inconsistent between telemetry and ground truth")
    if ground["test_id"].ne(test_profile.test_id).any():
        _fail("ground truth test_id mismatch")
    if (ground["module_profile_id"] != module_profile.identity.module_id).any():
        _fail("ground truth module_profile_id mismatch")

    parsed_ts = pd.to_datetime(telemetry["timestamp"], utc=True, format="ISO8601")
    if parsed_ts.isna().any():
        _fail("unparseable timestamps")
    if str(parsed_ts.dt.tz) not in {"UTC", "tzutc()"} and parsed_ts.dt.tz is None:
        _fail("timestamp is not UTC")

    channels = config.include_channels
    for name in channels:
        status_col = telemetry[f"{name}_status"].astype(str)
        values = telemetry[name]
        inf_mask = values.map(lambda v: isinstance(v, (int, float, np.floating)) and np.isinf(v))
        if inf_mask.any():
            _fail(f"Inf in {name}")
        nan_non_missing = values.map(
            lambda v: isinstance(v, (float, np.floating)) and math.isnan(float(v))
        ) & status_col.ne("missing")
        if nan_non_missing.any():
            _fail(f"NaN in {name} with non-missing status")
        missing_has_value = status_col.eq("missing") & values.notna()
        if missing_has_value.any():
            _fail("missing measurements must not include a numeric value")
        required_missing_value = status_col.isin(["valid", "derived", "estimated"]) & values.isna()
        if required_missing_value.any():
            _fail(f"valid/derived measurement missing value for {name}")
        if telemetry[f"{name}_unit"].ne(UNITS[name]).any():
            _fail(f"unexpected unit for {name}")

    if config.scenario is not Scenario.DATA_QUALITY_STRESS:
        if len(telemetry) != config.n_modules * n_obs_nominal:
            _fail(
                f"expected {config.n_modules * n_obs_nominal} telemetry rows, got {len(telemetry)}"
            )
        for module_id, group in telemetry.groupby("module_id", sort=False):
            cycles = group["cycle_number"].to_numpy()
            if (cycles[1:] <= cycles[:-1]).any():
                _fail(f"cycle_number is not strictly increasing for {module_id}")
            stamps = pd.to_datetime(group["timestamp"], utc=True, format="ISO8601")
            if stamps.diff().iloc[1:].dt.total_seconds().le(0).any():
                _fail(f"timestamps are not strictly increasing for {module_id}")
        if telemetry[[f"{c}_status" for c in channels]].ne("valid").any().any():
            _fail("clean scenarios must not inject missing/invalid statuses")
        if telemetry["telemetry_id"].duplicated().any():
            _fail("duplicate telemetry_id in a clean scenario")
    else:
        if not (telemetry[[f"{c}_status" for c in channels]] == "missing").any().any():
            if config.quality.p_missing > 0 and len(telemetry) > 50:
                _fail("data_quality_stress expected some missing statuses")

    mix_counts = ground["degradation_mechanism"].value_counts().to_dict()
    expected = {mech.value: int((population_mechanisms == mech.value).sum()) for mech in Mechanism}
    expected = {key: value for key, value in expected.items() if value}
    if mix_counts != expected:
        _fail(f"mechanism composition mismatch: {mix_counts} vs {expected}")
    if config.scenario is Scenario.CLEAN_HEALTHY:
        if set(ground["degradation_mechanism"].unique()) - {"healthy"}:
            _fail("clean_healthy must contain only healthy modules")

    for _, row in ground.iterrows():
        onset = row["onset_cycle"]
        terminal = row["cycle_terminal"]
        if pd.isna(onset) or onset is None:
            if row["degradation_mechanism"] != "healthy":
                _fail("degrading module missing onset")
            continue
        onset_i = int(onset)
        for field in ("cycle_early", "cycle_measurable", "cycle_advanced", "cycle_terminal"):
            value = row[field]
            if value is not None and not (isinstance(value, float) and math.isnan(value)) and not pd.isna(value):
                if int(value) < onset_i:
                    _fail(f"{field} before onset for {row['module_id']}")
        if terminal is not None and not pd.isna(terminal) and int(terminal) < onset_i:
            _fail("terminal before onset")

    _validate_pydantic_sample(telemetry, channels, limit=pydantic_record_limit)
    # Always validate the first and last row of one module fully.
    first_id = str(telemetry["module_id"].iloc[0])
    subset = telemetry[telemetry["module_id"] == first_id].head(2)
    _validate_pydantic_sample(subset, channels, limit=None)

    if config.scenario is Scenario.CLEAN_HEALTHY and n_obs_nominal >= 3:
        rds = telemetry["RDS_on"].astype(float)
        if rds.nunique() <= config.n_modules:
            _fail("healthy trajectories appear perfectly flat")


def assert_record_is_telemetry(payload: dict[str, Any]) -> TelemetryRecord:
    return parse_telemetry_record(payload)

"""Structural M5 checks: artifacts, metadata, schema, identity, leakage, size."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from domain.telemetry.enums import DataOrigin, MeasurementStatus
from domain.telemetry.validation import parse_telemetry_record
from ml.generators.synthetic.config import GenerationConfig, Mechanism
from ml.generators.synthetic.population import largest_remainder_counts
from ml.generators.synthetic.sensors import DERIVED
from ml.validators.synthetic.constants import (
    ALL_HEALTH,
    ALL_MECHANISMS,
    ALL_ORIGINS,
    ALL_SCENARIOS,
    ALL_STAGES,
    ALL_STATUSES,
    CORE_TELEMETRY_COLUMNS,
    GROUND_TRUTH_REQUIRED_COLUMNS,
    PARAMETER_UNIT_VALUES,
    REQUIRED_ARTIFACTS,
    STAGE_ORDER,
    VALID_VALUE_STATUSES,
)
from ml.validators.synthetic.loader import LoadedDataset
from ml.validators.synthetic.models import (
    CheckCategory,
    CheckResult,
    CheckSeverity,
    make_check,
)
from ml.validators.synthetic.stats import channel_values, valid_mask


def _ids(frame: pd.DataFrame, mask: pd.Series, column: str = "telemetry_id", limit: int = 8) -> list[str]:
    if column not in frame.columns:
        return [str(i) for i in frame.index[mask.fillna(False)][:limit]]
    return [str(v) for v in frame.loc[mask.fillna(False), column].astype(str).head(limit).tolist()]


def _modules(frame: pd.DataFrame, mask: pd.Series, limit: int = 8) -> list[str]:
    if "module_id" not in frame.columns:
        return []
    return [str(v) for v in frame.loc[mask.fillna(False), "module_id"].astype(str).unique()[:limit]]


def check_artifacts(loaded: LoadedDataset) -> list[CheckResult]:
    missing = loaded.missing_artifacts
    unread = loaded.unreadable
    return [
        make_check(
            "artifacts.required_files",
            CheckCategory.ARTIFACTS,
            CheckSeverity.BLOCKING,
            failed=bool(missing),
            pass_message="All required dataset artifacts are present.",
            fail_message=f"Missing required artifacts: {missing}",
            metrics={"missing": missing, "required": list(REQUIRED_ARTIFACTS)},
        ),
        make_check(
            "artifacts.readable",
            CheckCategory.ARTIFACTS,
            CheckSeverity.BLOCKING,
            failed=bool(unread),
            pass_message="Required artifacts are readable.",
            fail_message=f"Unreadable artifacts: {unread}",
            metrics={"unreadable": unread},
        ),
    ]


def check_metadata(loaded: LoadedDataset) -> list[CheckResult]:
    meta = loaded.dataset_meta
    config = loaded.generation_config
    assumptions = loaded.assumptions
    provenance = loaded.provenance
    checks: list[CheckResult] = []

    checks.append(
        make_check(
            "metadata.dataset_json",
            CheckCategory.METADATA,
            CheckSeverity.BLOCKING,
            failed=meta is None,
            pass_message="dataset.json loaded.",
            fail_message="dataset.json is missing or unreadable.",
            metrics={"keys": sorted(meta.keys()) if isinstance(meta, dict) else []},
        )
    )
    if meta is None:
        return checks + [
            make_check(
                "metadata.data_origin",
                CheckCategory.METADATA,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="Cannot validate data_origin without dataset.json.",
            )
        ]

    required_meta = [
        "dataset_id",
        "scenario",
        "generator_version",
        "random_seed",
        "data_origin",
        "schema_version_telemetry",
        "module_profile_id",
        "test_profile_id",
    ]
    missing_keys = [key for key in required_meta if key not in meta or meta[key] in (None, "")]
    checks.append(
        make_check(
            "metadata.required_fields",
            CheckCategory.METADATA,
            CheckSeverity.BLOCKING,
            failed=bool(missing_keys),
            pass_message="dataset.json contains required identity fields.",
            fail_message=f"dataset.json missing required fields: {missing_keys}",
            metrics={"missing_keys": missing_keys},
        )
    )

    origin = str(meta.get("data_origin", ""))
    mislabelled_real = origin == DataOrigin.REAL.value
    origin_ok = origin == DataOrigin.SYNTHETIC.value
    checks.append(
        make_check(
            "metadata.data_origin",
            CheckCategory.METADATA,
            CheckSeverity.BLOCKING,
            failed=not origin_ok,
            pass_message="Required synthetic dataset declares data_origin=synthetic.",
            fail_message=(
                "Synthetic dataset is incorrectly labelled as real."
                if mislabelled_real
                else f"data_origin must be synthetic, got {origin!r}."
            ),
            metrics={"data_origin": origin},
        )
    )

    scenario = str(meta.get("scenario", ""))
    checks.append(
        make_check(
            "metadata.scenario",
            CheckCategory.METADATA,
            CheckSeverity.BLOCKING,
            failed=scenario not in ALL_SCENARIOS,
            pass_message=f"Scenario {scenario} is supported.",
            fail_message=f"Unknown scenario {scenario!r}.",
            metrics={"scenario": scenario},
        )
    )

    config_ok = config is not None
    parsed_ok = False
    parse_error = None
    if config is not None:
        try:
            GenerationConfig.model_validate(config)
            parsed_ok = True
        except Exception as exc:  # noqa: BLE001
            parse_error = f"{type(exc).__name__}: {exc}"
    checks.append(
        make_check(
            "metadata.generation_config",
            CheckCategory.METADATA,
            CheckSeverity.BLOCKING,
            failed=not config_ok or not parsed_ok,
            pass_message="generation-config.json is present and parseable.",
            fail_message=parse_error or "generation-config.json is missing or unreadable.",
        )
    )

    has_disclaimer = isinstance(assumptions, dict) and bool(assumptions.get("disclaimer"))
    checks.append(
        make_check(
            "metadata.assumptions",
            CheckCategory.METADATA,
            CheckSeverity.BLOCKING,
            failed=not has_disclaimer,
            pass_message="assumptions.json includes a synthetic-data disclaimer.",
            fail_message="assumptions.json is missing, unreadable, or lacks disclaimer.",
        )
    )

    provenance_ok = isinstance(provenance, dict) and provenance.get("dataset_id") and provenance.get("generator_version")
    checks.append(
        make_check(
            "metadata.provenance",
            CheckCategory.METADATA,
            CheckSeverity.BLOCKING,
            failed=not provenance_ok,
            pass_message="provenance.json is present with dataset identity.",
            fail_message="Required provenance is missing or incomplete.",
        )
    )

    refs: Any = None
    if isinstance(assumptions, dict):
        refs = assumptions.get("source_references")
    if isinstance(provenance, dict) and refs is None:
        refs = provenance.get("source_references")
    empty_ok = refs == [] or refs is None
    invented = isinstance(refs, list) and any(refs)
    checks.append(
        make_check(
            "metadata.source_references",
            CheckCategory.METADATA,
            CheckSeverity.INFO,
            failed=False,
            pass_message=(
                "source_references is empty, which is acceptable until verified external sources are ingested."
                if empty_ok
                else "source_references is populated; values were not independently verified by M5."
            ),
            fail_message="source_references invalid.",
            metrics={"source_references": refs if isinstance(refs, list) else [], "invented_flag": invented},
        )
    )
    return checks


def _reconstruct_row(row: pd.Series, channels: list[str]) -> dict[str, Any]:
    measurements = []
    for name in channels:
        status = str(row[f"{name}_status"])
        origin = str(row[f"{name}_origin"])
        unit = str(row[f"{name}_unit"])
        value = row[name]
        missing = status == MeasurementStatus.MISSING.value or value is None or pd.isna(value)
        if name in DERIVED and status == MeasurementStatus.MISSING.value:
            continue
        item: dict[str, Any] = {"parameter": name, "status": status, "origin": origin}
        if status == MeasurementStatus.MISSING.value:
            pass
        elif status in VALID_VALUE_STATUSES:
            if not missing:
                item["value"] = float(value)
                item["unit"] = unit
            if origin == "derived":
                item["derivation"] = {"method": "synthetic_generator_derived", "notes": "M5 reconstruct"}
        elif status == MeasurementStatus.INVALID.value and not missing:
            item["value"] = float(value)
            item["unit"] = unit
        measurements.append(item)
    if not measurements:
        measurements = [
            {
                "parameter": channels[0],
                "status": MeasurementStatus.MISSING.value,
                "origin": "measured",
            }
        ]
    return {
        "schema_version": row["schema_version"],
        "telemetry_id": row["telemetry_id"],
        "module_id": row["module_id"],
        "test_id": row["test_id"],
        "lot_id": row["lot_id"],
        "dataset_id": row["dataset_id"],
        "timestamp": row["timestamp"],
        "cycle_number": int(row["cycle_number"]) if pd.notna(row["cycle_number"]) else None,
        "cycle_phase": row["cycle_phase"],
        "measurements": measurements,
        "provenance": {
            "data_origin": row["data_origin"],
            "source_type": row["source_type"],
            "source_dataset": row["source_dataset"],
            "notes": row["provenance_notes"],
        },
    }


def check_telemetry_structure(loaded: LoadedDataset) -> list[CheckResult]:
    tel = loaded.telemetry
    config = loaded.generation_config or {}
    channels = list(config.get("include_channels") or [])
    checks: list[CheckResult] = []
    if tel is None:
        return [
            make_check(
                "telemetry.readable",
                CheckCategory.TELEMETRY,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="telemetry.parquet is missing or unreadable.",
            )
        ]

    checks.append(
        make_check(
            "telemetry.readable",
            CheckCategory.TELEMETRY,
            CheckSeverity.BLOCKING,
            failed=tel.empty,
            pass_message=f"telemetry.parquet is readable ({len(tel)} rows).",
            fail_message="telemetry.parquet has no rows.",
            metrics={"n_rows": int(len(tel)), "n_columns": int(tel.shape[1])},
        )
    )

    expected_cols = list(CORE_TELEMETRY_COLUMNS)
    for name in channels:
        expected_cols.extend([name, f"{name}_status", f"{name}_origin", f"{name}_unit"])
    missing_cols = [c for c in expected_cols if c not in tel.columns]
    checks.append(
        make_check(
            "telemetry.required_columns",
            CheckCategory.TELEMETRY,
            CheckSeverity.BLOCKING,
            failed=bool(missing_cols),
            pass_message="Expected telemetry columns are present.",
            fail_message=f"Missing telemetry columns: {missing_cols}",
            metrics={"missing_columns": missing_cols},
        )
    )

    id_fields = ["telemetry_id", "module_id", "test_id"]
    empty_ids = {}
    for field in id_fields:
        if field not in tel.columns:
            empty_ids[field] = "missing_column"
            continue
        blank = tel[field].isna() | tel[field].astype(str).str.strip().eq("")
        empty_ids[field] = int(blank.sum())
    failed_ids = any(v != 0 for v in empty_ids.values())
    checks.append(
        make_check(
            "telemetry.identifiers",
            CheckCategory.TELEMETRY,
            CheckSeverity.BLOCKING,
            failed=failed_ids,
            pass_message="telemetry_id, module_id, and test_id are non-empty.",
            fail_message=f"Empty identifiers: {empty_ids}",
            metrics=empty_ids,
        )
    )

    cycle_ok = True
    cycle_msg = "cycle_number is present and integer-compatible."
    if "cycle_number" not in tel.columns:
        cycle_ok = False
        cycle_msg = "cycle_number is missing; power-cycling datasets require it."
    else:
        numeric = pd.to_numeric(tel["cycle_number"], errors="coerce")
        if numeric.isna().any():
            cycle_ok = False
            cycle_msg = "cycle_number contains non-integer or null values."
    checks.append(
        make_check(
            "telemetry.cycle_number",
            CheckCategory.TELEMETRY,
            CheckSeverity.BLOCKING,
            failed=not cycle_ok,
            pass_message="cycle_number exists where expected.",
            fail_message=cycle_msg,
        )
    )

    origin_ok = "data_origin" in tel.columns and not tel["data_origin"].astype(str).ne("synthetic").any()
    checks.append(
        make_check(
            "telemetry.data_origin",
            CheckCategory.TELEMETRY,
            CheckSeverity.BLOCKING,
            failed=not origin_ok,
            pass_message="Every telemetry row has data_origin=synthetic.",
            fail_message="Telemetry data_origin is missing or not synthetic.",
        )
    )

    nan_inf_channels = []
    missingness_violations = []
    unit_violations = []
    for name in channels:
        if name not in tel.columns:
            continue
        values = pd.to_numeric(tel[name], errors="coerce")
        status = tel[f"{name}_status"].astype(str) if f"{name}_status" in tel.columns else pd.Series("valid", index=tel.index)
        inf_mask = values.map(lambda v: bool(isinstance(v, (int, float, np.floating)) and np.isinf(v)), na_action="ignore")
        inf_mask = inf_mask.fillna(False).astype(bool)
        raw = tel[name]
        nan_non_missing = status.ne("missing") & raw.map(
            lambda v: isinstance(v, (float, np.floating)) and math.isnan(float(v)) if isinstance(v, (int, float, np.floating)) else False
        )
        if inf_mask.any() or nan_non_missing.any():
            nan_inf_channels.append(
                {"channel": name, "inf": int(inf_mask.sum()), "nan_non_missing": int(nan_non_missing.sum())}
            )
        if f"{name}_status" in tel.columns:
            missing_has_value = status.eq("missing") & tel[name].notna()
            required_missing = status.isin(list(VALID_VALUE_STATUSES)) & tel[name].isna()
            unknown_status = ~status.isin(ALL_STATUSES)
            if missing_has_value.any() or required_missing.any() or unknown_status.any():
                missingness_violations.append(
                    {
                        "channel": name,
                        "missing_has_value": int(missing_has_value.sum()),
                        "valid_without_value": int(required_missing.sum()),
                        "unknown_status": int(unknown_status.sum()),
                    }
                )
        if f"{name}_unit" in tel.columns:
            allowed = PARAMETER_UNIT_VALUES.get(name)
            if allowed is not None:
                bad_units = ~tel[f"{name}_unit"].astype(str).isin(allowed)
                if bad_units.any():
                    unit_violations.append({"channel": name, "n": int(bad_units.sum())})
        if f"{name}_origin" in tel.columns:
            origins = tel[f"{name}_origin"].astype(str)
            bad_origin = ~origins.isin(ALL_ORIGINS)
            if name in DERIVED:
                bad_derived = origins.ne("derived") & status.ne("missing")
            else:
                bad_derived = pd.Series(False, index=tel.index)
            if bad_origin.any() or bad_derived.any():
                unit_violations.append(
                    {
                        "channel": name,
                        "bad_origin": int(bad_origin.sum()),
                        "derived_contract": int(bad_derived.sum()),
                    }
                )

    checks.append(
        make_check(
            "telemetry.nan_inf",
            CheckCategory.TELEMETRY,
            CheckSeverity.BLOCKING,
            failed=bool(nan_inf_channels),
            pass_message="No NaN or Inf in non-missing telemetry measurements.",
            fail_message=f"NaN/Inf detected: {nan_inf_channels}",
            metrics={"channels": nan_inf_channels},
        )
    )
    checks.append(
        make_check(
            "telemetry.missingness_semantics",
            CheckCategory.TELEMETRY,
            CheckSeverity.BLOCKING,
            failed=bool(missingness_violations),
            pass_message="Missingness follows M3 semantics (status=missing, no numeric value).",
            fail_message=f"Missingness contract violations: {missingness_violations}",
            metrics={"violations": missingness_violations},
        )
    )
    checks.append(
        make_check(
            "telemetry.units_and_origin",
            CheckCategory.TELEMETRY,
            CheckSeverity.BLOCKING,
            failed=bool(unit_violations),
            pass_message="Units and origin follow the M3 parameter contract.",
            fail_message=f"Unit/origin violations: {unit_violations}",
            metrics={"violations": unit_violations},
        )
    )

    pydantic_errors = []
    if channels and not tel.empty and not missing_cols:
        n = min(32, len(tel))
        sample = tel.sample(n=n, random_state=0) if len(tel) > n else tel
        for _, row in sample.iterrows():
            try:
                payload = _reconstruct_row(row, channels)
                parse_telemetry_record(payload)
            except Exception as exc:  # noqa: BLE001
                pydantic_errors.append({"telemetry_id": str(row.get("telemetry_id")), "error": str(exc)})
                if len(pydantic_errors) >= 5:
                    break
    checks.append(
        make_check(
            "telemetry.pydantic_sample",
            CheckCategory.TELEMETRY,
            CheckSeverity.BLOCKING,
            failed=bool(pydantic_errors),
            pass_message="Sampled rows reconstruct to M3 TelemetryRecord.",
            fail_message=f"M3 reconstruction failed: {pydantic_errors[:3]}",
            metrics={"n_sampled": min(32, len(tel)), "errors": pydantic_errors[:5]},
        )
    )
    return checks


def check_ground_truth(loaded: LoadedDataset) -> list[CheckResult]:
    gt = loaded.ground_truth
    tel = loaded.telemetry
    if gt is None:
        return [
            make_check(
                "ground_truth.readable",
                CheckCategory.GROUND_TRUTH,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="ground-truth.parquet is missing or unreadable.",
            )
        ]
    checks = [
        make_check(
            "ground_truth.readable",
            CheckCategory.GROUND_TRUTH,
            CheckSeverity.BLOCKING,
            failed=gt.empty,
            pass_message=f"ground-truth.parquet is readable ({len(gt)} rows).",
            fail_message="ground-truth.parquet has no rows.",
            metrics={"n_rows": int(len(gt))},
        )
    ]
    missing = [c for c in GROUND_TRUTH_REQUIRED_COLUMNS if c not in gt.columns]
    checks.append(
        make_check(
            "ground_truth.required_fields",
            CheckCategory.GROUND_TRUTH,
            CheckSeverity.BLOCKING,
            failed=bool(missing),
            pass_message="Required ground-truth fields exist.",
            fail_message=f"Missing ground-truth fields: {missing}",
            metrics={"missing": missing},
        )
    )
    unique_ok = True
    n_dup = 0
    if "module_id" in gt.columns:
        n_dup = int(gt["module_id"].astype(str).duplicated().sum())
        unique_ok = n_dup == 0
    checks.append(
        make_check(
            "ground_truth.module_uniqueness",
            CheckCategory.GROUND_TRUTH,
            CheckSeverity.BLOCKING,
            failed=not unique_ok,
            pass_message="Ground-truth module_id values are unique.",
            fail_message=f"Duplicate ground-truth module_id count: {n_dup}",
            metrics={"duplicate_module_rows": n_dup},
        )
    )

    invalid_mech = []
    if "degradation_mechanism" in gt.columns:
        invalid_mech = [m for m in gt["degradation_mechanism"].astype(str).unique() if m not in ALL_MECHANISMS]
    checks.append(
        make_check(
            "ground_truth.mechanisms",
            CheckCategory.GROUND_TRUTH,
            CheckSeverity.BLOCKING,
            failed=bool(invalid_mech),
            pass_message="Mechanisms are from the supported set.",
            fail_message=f"Unsupported mechanisms: {invalid_mech}",
            metrics={"invalid": invalid_mech, "supported": sorted(ALL_MECHANISMS)},
        )
    )

    stage_errors = 0
    onset_errors = 0
    affected = []
    if not missing:
        for _, row in gt.iterrows():
            mech = str(row["degradation_mechanism"])
            stage = str(row["degradation_stage"])
            health = str(row["health_state"])
            if stage not in ALL_STAGES or health not in ALL_HEALTH:
                stage_errors += 1
                affected.append(str(row["module_id"]))
                continue
            onset = row["onset_cycle"]
            terminal = row["cycle_terminal"] if pd.notna(row["cycle_terminal"]) else row["terminal_cycle"]
            if mech == Mechanism.HEALTHY.value:
                if pd.notna(onset) and onset is not None:
                    onset_errors += 1
                    affected.append(str(row["module_id"]))
                continue
            if pd.isna(onset) or onset is None:
                onset_errors += 1
                affected.append(str(row["module_id"]))
                continue
            onset_i = int(onset)
            if onset_i < 0:
                onset_errors += 1
                affected.append(str(row["module_id"]))
            mapped: dict[str, int] = {}
            for field in ("cycle_early", "cycle_measurable", "cycle_advanced", "cycle_terminal", "terminal_cycle"):
                value = row[field]
                if value is not None and not pd.isna(value):
                    mapped[field] = int(value)
                    if int(value) < onset_i:
                        stage_errors += 1
                        affected.append(str(row["module_id"]))
            if terminal is not None and not pd.isna(terminal) and int(terminal) < onset_i:
                stage_errors += 1
            seq = [mapped[k] for k in ("cycle_early", "cycle_measurable", "cycle_advanced", "cycle_terminal") if k in mapped]
            if seq != sorted(seq):
                stage_errors += 1
                affected.append(str(row["module_id"]))
            if "cycle_advanced" in mapped and "cycle_terminal" in mapped:
                if mapped["cycle_terminal"] < mapped["cycle_advanced"]:
                    stage_errors += 1
                    affected.append(str(row["module_id"]))
    checks.append(
        make_check(
            "ground_truth.onset_and_stages",
            CheckCategory.GROUND_TRUTH,
            CheckSeverity.BLOCKING,
            failed=onset_errors > 0 or stage_errors > 0,
            pass_message="Onset, terminal, and stage ordering are valid.",
            fail_message=f"Invalid onset/stage ordering (onset_errors={onset_errors}, stage_errors={stage_errors}).",
            metrics={"onset_errors": onset_errors, "stage_errors": stage_errors},
            affected_modules=affected,
        )
    )

    finite_bad = 0
    if "degradation_severity" in gt.columns:
        sev = pd.to_numeric(gt["degradation_severity"], errors="coerce")
        finite_bad += int((~np.isfinite(sev.to_numpy(dtype=float))).sum())
    if "rate_scale" in gt.columns:
        rates = pd.to_numeric(gt["rate_scale"], errors="coerce")
        degrading = gt["degradation_mechanism"].astype(str).ne(Mechanism.HEALTHY.value) if "degradation_mechanism" in gt.columns else pd.Series(False, index=gt.index)
        finite_bad += int((degrading & ~np.isfinite(rates.fillna(np.nan).to_numpy(dtype=float))).sum())
        finite_bad += int((degrading & (rates <= 0)).sum())
    checks.append(
        make_check(
            "ground_truth.finite_severity_rate",
            CheckCategory.GROUND_TRUTH,
            CheckSeverity.BLOCKING,
            failed=finite_bad > 0,
            pass_message="Severity and rate_scale are finite (rate_scale > 0 for degrading modules).",
            fail_message=f"Invalid severity/rate values: {finite_bad}",
            metrics={"invalid_count": finite_bad},
        )
    )

    seed_ok = "simulation_seed" in gt.columns and not gt["simulation_seed"].isna().any()
    gen_ok = "generator_version" in gt.columns and not gt["generator_version"].astype(str).str.strip().eq("").any()
    checks.append(
        make_check(
            "ground_truth.seed_and_version",
            CheckCategory.GROUND_TRUTH,
            CheckSeverity.BLOCKING,
            failed=not (seed_ok and gen_ok),
            pass_message="Ground truth records seed and generator version.",
            fail_message="Ground truth is missing simulation_seed or generator_version.",
        )
    )

    if tel is None or "module_id" not in gt.columns:
        checks.append(
            make_check(
                "ground_truth.module_alignment",
                CheckCategory.GROUND_TRUTH,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="Cannot align ground-truth modules with telemetry.",
            )
        )
        return checks

    gt_modules = set(gt["module_id"].astype(str))
    tel_modules = set(tel["module_id"].astype(str))
    missing_gt = sorted(tel_modules - gt_modules)
    extra_gt = sorted(gt_modules - tel_modules)
    mismatch = bool(missing_gt or extra_gt)
    checks.append(
        make_check(
            "ground_truth.module_alignment",
            CheckCategory.GROUND_TRUTH,
            CheckSeverity.BLOCKING,
            failed=mismatch,
            pass_message="Every telemetry module has ground truth and every ground-truth module exists in telemetry.",
            fail_message=(
                f"Module mismatch. Missing ground truth: {missing_gt[:10]}. "
                f"Extra ground truth: {extra_gt[:10]}."
            ),
            metrics={
                "n_telemetry_modules": len(tel_modules),
                "n_ground_truth_modules": len(gt_modules),
                "missing_ground_truth": missing_gt[:50],
                "extra_ground_truth": extra_gt[:50],
            },
            affected_modules=(missing_gt + extra_gt)[:25],
        )
    )
    return checks


def expected_mechanism_counts(config: dict[str, Any]) -> dict[str, int]:
    parsed = GenerationConfig.model_validate(config)
    mix = parsed.effective_mix()
    if parsed.stratify_mix_by_lot:
        per_lot = largest_remainder_counts(parsed.modules_per_lot, mix)
        return {mech.value: per_lot[mech] * parsed.n_lots for mech in Mechanism}
    totals = largest_remainder_counts(parsed.n_modules, mix)
    return {mech.value: totals[mech] for mech in Mechanism}


def check_consistency(loaded: LoadedDataset) -> list[CheckResult]:
    meta = loaded.dataset_meta or {}
    config = loaded.generation_config or {}
    provenance = loaded.provenance or {}
    tel = loaded.telemetry
    gt = loaded.ground_truth
    checks: list[CheckResult] = []

    ids = {
        "dataset.json": meta.get("dataset_id"),
        "generation-config.json": config.get("dataset_id"),
        "provenance.json": provenance.get("dataset_id"),
    }
    if tel is not None and "dataset_id" in tel.columns and not tel.empty:
        ids["telemetry"] = tel["dataset_id"].iloc[0]
        tel_mismatch = tel["dataset_id"].astype(str).nunique() != 1 or str(tel["dataset_id"].iloc[0]) != str(meta.get("dataset_id"))
    else:
        tel_mismatch = tel is None
    if gt is not None and "dataset_id" in gt.columns and not gt.empty:
        ids["ground_truth"] = gt["dataset_id"].iloc[0]
        gt_mismatch = gt["dataset_id"].astype(str).nunique() != 1 or str(gt["dataset_id"].iloc[0]) != str(meta.get("dataset_id"))
    else:
        gt_mismatch = gt is None
    id_values = {str(v) for v in ids.values() if v is not None}
    checks.append(
        make_check(
            "consistency.dataset_id",
            CheckCategory.CONSISTENCY,
            CheckSeverity.BLOCKING,
            failed=len(id_values) != 1 or tel_mismatch or gt_mismatch,
            pass_message="dataset_id agrees across artifacts.",
            fail_message=f"dataset_id mismatch: {ids}",
            metrics={"ids": {k: str(v) for k, v in ids.items()}},
        )
    )

    seeds = {
        "dataset.json": meta.get("random_seed"),
        "generation-config.json": config.get("seed"),
        "provenance.json": provenance.get("random_seed"),
    }
    if gt is not None and "simulation_seed" in gt.columns and not gt.empty:
        seeds["ground_truth"] = gt["simulation_seed"].iloc[0]
        seed_gt_bad = gt["simulation_seed"].nunique() != 1
    else:
        seed_gt_bad = gt is None
    seed_vals = {s for s in seeds.values() if s is not None}
    try:
        seed_vals_norm = {int(s) for s in seed_vals}
    except (TypeError, ValueError):
        seed_vals_norm = set()
        seed_gt_bad = True
    checks.append(
        make_check(
            "consistency.seed",
            CheckCategory.CONSISTENCY,
            CheckSeverity.BLOCKING,
            failed=len(seed_vals_norm) != 1 or seed_gt_bad,
            pass_message="Seed agrees where represented.",
            fail_message=f"Seed mismatch: {seeds}",
            metrics={"seeds": {k: s for k, s in seeds.items()}},
        )
    )

    versions = {
        "dataset.json": meta.get("generator_version"),
        "generation-config.json": config.get("generator_version"),
        "provenance.json": provenance.get("generator_version"),
    }
    if gt is not None and "generator_version" in gt.columns and not gt.empty:
        versions["ground_truth"] = str(gt["generator_version"].iloc[0])
        ver_bad = gt["generator_version"].astype(str).nunique() != 1
    else:
        ver_bad = gt is None
    ver_vals = {str(v) for v in versions.values() if v is not None}
    checks.append(
        make_check(
            "consistency.generator_version",
            CheckCategory.CONSISTENCY,
            CheckSeverity.BLOCKING,
            failed=len(ver_vals) != 1 or ver_bad,
            pass_message="generator_version agrees across artifacts.",
            fail_message=f"generator_version mismatch: {versions}",
            metrics={"versions": {k: str(v) for k, v in versions.items()}},
        )
    )

    scenarios = {
        "dataset.json": meta.get("scenario"),
        "generation-config.json": config.get("scenario"),
        "provenance.json": provenance.get("scenario"),
    }
    if gt is not None and "scenario" in gt.columns and not gt.empty:
        scenarios["ground_truth"] = str(gt["scenario"].iloc[0])
        sc_bad = gt["scenario"].astype(str).nunique() != 1
    else:
        sc_bad = gt is None
    sc_vals = {str(v) for v in scenarios.values() if v is not None}
    checks.append(
        make_check(
            "consistency.scenario",
            CheckCategory.CONSISTENCY,
            CheckSeverity.BLOCKING,
            failed=len(sc_vals) != 1 or sc_bad,
            pass_message="Scenario agrees across artifacts.",
            fail_message=f"Scenario mismatch: {scenarios}",
            metrics={"scenarios": {k: str(v) for k, v in scenarios.items()}},
        )
    )

    n_mod_meta = meta.get("n_modules")
    n_mod_cfg = config.get("n_modules")
    n_mod_tel = int(tel["module_id"].nunique()) if tel is not None and "module_id" in tel.columns else None
    n_mod_gt = int(len(gt)) if gt is not None else None
    count_vals = [v for v in (n_mod_meta, n_mod_cfg, n_mod_tel, n_mod_gt) if v is not None]
    checks.append(
        make_check(
            "consistency.module_count",
            CheckCategory.CONSISTENCY,
            CheckSeverity.BLOCKING,
            failed=len(set(int(v) for v in count_vals)) != 1 if count_vals else True,
            pass_message="Module count agrees across metadata, telemetry, and ground truth.",
            fail_message=f"Module count mismatch: meta={n_mod_meta} config={n_mod_cfg} telemetry={n_mod_tel} gt={n_mod_gt}",
            metrics={"dataset": n_mod_meta, "config": n_mod_cfg, "telemetry": n_mod_tel, "ground_truth": n_mod_gt},
        )
    )

    mix_failed = True
    mix_metrics: dict[str, Any] = {}
    if gt is not None and "degradation_mechanism" in gt.columns and config:
        try:
            expected = expected_mechanism_counts(config)
            actual = gt["degradation_mechanism"].astype(str).value_counts().to_dict()
            actual_i = {str(k): int(v) for k, v in actual.items()}
            mix_metrics = {"expected": expected, "actual": actual_i}
            mix_failed = actual_i != {k: v for k, v in expected.items() if v} and actual_i != expected
            # allow expected zeros omitted
            mix_failed = {k: actual_i.get(k, 0) for k in expected} != expected
        except Exception as exc:  # noqa: BLE001
            mix_metrics = {"error": str(exc)}
            mix_failed = True
    checks.append(
        make_check(
            "consistency.mechanism_composition",
            CheckCategory.CONSISTENCY,
            CheckSeverity.BLOCKING,
            failed=mix_failed,
            pass_message="Mechanism composition matches configured deterministic allocation.",
            fail_message=f"Mechanism composition mismatch: {mix_metrics}",
            metrics=mix_metrics,
        )
    )

    pop_failed = False
    if tel is not None and gt is not None and "module_id" in tel.columns:
        # Declared population is GT module set / config n_modules. Extra IDs outside syn-mod pattern still belong if in GT.
        tel_only = set(tel["module_id"].astype(str)) - set(gt["module_id"].astype(str))
        gt_only = set(gt["module_id"].astype(str)) - set(tel["module_id"].astype(str))
        pop_failed = bool(tel_only or gt_only)
    checks.append(
        make_check(
            "consistency.population_membership",
            CheckCategory.CONSISTENCY,
            CheckSeverity.BLOCKING,
            failed=pop_failed,
            pass_message="All telemetry and ground-truth modules belong to the declared population.",
            fail_message="Telemetry or ground-truth modules fall outside the declared population.",
        )
    )
    return checks

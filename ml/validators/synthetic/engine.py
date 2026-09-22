"""Orchestrate independent dataset validation and write reports."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from ml.validators.synthetic.constants import LIMITATIONS
from ml.validators.synthetic.diagnostics import (
    check_correlations,
    check_degradation,
    check_distribution,
    check_mechanism_diagnostics,
    check_temperature_confounding,
)
from ml.validators.synthetic.loader import LoadedDataset, discover_and_load
from ml.validators.synthetic.models import (
    VALIDATOR_VERSION,
    CheckResult,
    CheckStatus,
    ValidationReport,
    ValidationSummary,
    aggregate_status,
    utc_now_iso,
)
from ml.validators.synthetic.quality import (
    check_identity,
    check_leakage,
    check_missingness,
    check_numerical,
    check_size,
    check_temporal,
)
from ml.validators.synthetic.reporting import write_reports
from ml.validators.synthetic.structural import (
    check_artifacts,
    check_consistency,
    check_ground_truth,
    check_metadata,
    check_telemetry_structure,
)
from ml.validators.synthetic.stats import valid_mask


def _run_all(loaded: LoadedDataset) -> list[CheckResult]:
    checks: list[CheckResult] = []
    checks.extend(check_artifacts(loaded))
    checks.extend(check_metadata(loaded))
    checks.extend(check_telemetry_structure(loaded))
    checks.extend(check_ground_truth(loaded))
    checks.extend(check_consistency(loaded))
    checks.extend(check_temporal(loaded))
    checks.extend(check_numerical(loaded))
    checks.extend(check_missingness(loaded))
    checks.extend(check_identity(loaded))
    checks.extend(check_leakage(loaded))
    checks.extend(check_size(loaded))
    checks.extend(check_distribution(loaded))
    checks.extend(check_correlations(loaded))
    checks.extend(check_temperature_confounding(loaded))
    checks.extend(check_degradation(loaded))
    checks.extend(check_mechanism_diagnostics(loaded))
    return checks


def _summary_metrics(loaded: LoadedDataset, checks: list[CheckResult], elapsed_s: float) -> ValidationSummary:
    tel = loaded.telemetry
    gt = loaded.ground_truth
    meta = loaded.dataset_meta or {}
    config = loaded.generation_config or {}
    channels = list(config.get("include_channels") or [])
    missingness = {}
    if tel is not None:
        for name in channels:
            col = f"{name}_status"
            if col in tel.columns:
                status = tel[col].astype(str)
                missingness[name] = float(status.eq("missing").mean())
    dup = {}
    if tel is not None:
        dup = {
            "telemetry_id": int(tel["telemetry_id"].duplicated().sum()) if "telemetry_id" in tel.columns else None,
            "module_cycle": (
                int(tel.duplicated(["module_id", "cycle_number"]).sum())
                if "module_id" in tel.columns and "cycle_number" in tel.columns
                else None
            ),
            "exact_rows": int(tel.duplicated().sum()),
        }
    mech = {}
    if gt is not None and "degradation_mechanism" in gt.columns:
        mech = {str(k): int(v) for k, v in gt["degradation_mechanism"].astype(str).value_counts().to_dict().items()}
    key = {}
    for check in checks:
        if check.check_id in {
            "correlation.declared_relationships",
            "temperature.healthy_rds_vs_tj",
            "temperature.mechanism_not_just_tj",
            "leakage.ground_truth_in_telemetry",
            "distribution.finite_variation",
        }:
            key[check.check_id] = check.metrics
    if tel is not None and "RDS_on" in tel.columns:
        mask = valid_mask(tel, "RDS_on")
        key["n_valid_rds"] = int(mask.sum())
    return ValidationSummary(
        n_checks=len(checks),
        n_pass=sum(1 for c in checks if c.status is CheckStatus.PASS),
        n_warning=sum(1 for c in checks if c.status is CheckStatus.WARNING),
        n_blocked=sum(1 for c in checks if c.status is CheckStatus.BLOCKED),
        n_modules=int(tel["module_id"].nunique()) if tel is not None and "module_id" in tel.columns else None,
        n_lots=int(tel["lot_id"].nunique()) if tel is not None and "lot_id" in tel.columns else None,
        n_telemetry_rows=int(len(tel)) if tel is not None else None,
        n_ground_truth_rows=int(len(gt)) if gt is not None else None,
        mechanism_counts=mech,
        missingness=missingness,
        duplicate_counts=dup,
        key_metrics=key,
        elapsed_s=elapsed_s,
        scenario=str(meta.get("scenario") or config.get("scenario") or "") or None,
        data_origin=str(meta.get("data_origin") or "") or None,
    )


def validate_dataset(
    dataset_path: str | Path,
    *,
    write_output: bool = True,
) -> ValidationReport:
    """Independently validate a SmartESS synthetic dataset directory.

    Does not modify source artifacts. Optionally writes reports under validation/.
    """

    from time import perf_counter

    started = perf_counter()
    loaded = discover_and_load(Path(dataset_path))
    checks = _run_all(loaded)
    elapsed = perf_counter() - started
    report = ValidationReport(
        dataset_id=loaded.dataset_id_guess,
        validator_version=VALIDATOR_VERSION,
        validation_timestamp=utc_now_iso(),
        overall_status=aggregate_status(checks),
        checks=checks,
        summary=_summary_metrics(loaded, checks, elapsed),
        limitations=list(LIMITATIONS),
    )
    if write_output and loaded.dataset_dir.is_dir():
        write_reports(loaded.dataset_dir, report)
    return report

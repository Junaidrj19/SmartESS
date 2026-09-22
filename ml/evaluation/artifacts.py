"""Deterministic serialization of M8 evaluation artifacts.

All write functions produce the exact schemas declared in the M8 contract.
None of them modify M7 score/model directories.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .config import EvaluationConfig

OBSERVATION_COLUMNS_FOR_FIRST_FLAG = [
    "module_id",
    "cycle_number",
    "anomaly_score",
]

MODULE_EVAL_COLUMNS: List[str] = [
    "module_id",
    "test_id",
    "lot_id",
    "dataset_id",
    "health_state",
    "degradation_mechanism",
    "degradation_stage",
    "onset_cycle",
    "cycle_measurable",
    "degradation_severity",
    "damage_index_end",
    "rate_scale",
    "n_observations",
    "n_anomalous_observations",
    "max_anomaly_score",
    "mean_anomaly_score",
    "first_anomalous_cycle",
    "module_anomaly_status",
    "statistical_baseline_max",
    "statistical_baseline_flag_rate",
    "y_true",
    "y_pred_module",
    "first_flag_cycle",
    "lead_vs_onset",
    "lead_vs_measurable",
    "statistical_baseline_flag_module",
    "y_pred_baseline",
]

TIMING_ANALYSIS_COLUMNS: List[str] = [
    "module_id",
    "degradation_mechanism",
    "health_state",
    "onset_cycle",
    "cycle_measurable",
    "first_flag_cycle",
    "lead_vs_onset",
    "lead_vs_measurable",
    "n_flagged_observations",
    "max_anomaly_score",
    "statistical_baseline_max",
]

BASELINE_COMPARISON_COLUMNS: List[str] = [
    "module_id",
    "max_anomaly_score",
    "statistical_baseline_max",
    "if_flag_module",
    "base_flag_module",
    "health_state",
    "degradation_mechanism",
]


def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_module_evaluation(
    module_eval: pd.DataFrame,
    path: Path,
) -> None:
    """Write module-evaluation.parquet with deterministic column ordering."""
    out = module_eval.reindex(columns=MODULE_EVAL_COLUMNS)
    _clean_int_dtypes(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)


def write_timing_analysis(
    timing: pd.DataFrame,
    path: Path,
) -> None:
    """Write timing-analysis.parquet with deterministic column ordering."""
    out = timing.reindex(columns=TIMING_ANALYSIS_COLUMNS)
    _clean_int_dtypes(out)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)


def write_baseline_comparison(
    comparison: pd.DataFrame,
    path: Path,
) -> None:
    """Write baseline-comparison.parquet with deterministic column ordering."""
    out = comparison.reindex(columns=BASELINE_COMPARISON_COLUMNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)


def _clean_int_dtypes(df: pd.DataFrame) -> None:
    """Convert float columns that are actually integer-like to object to preserve None."""
    for col in df.columns:
        if df[col].dtype.kind == "f" and (df[col].dropna() % 1 == 0).all():
            df[col] = df[col].apply(
                lambda x: int(x) if pd.notna(x) else None
            ).astype(object)


def _make_serializable(obj: Any) -> Any:
    """Recursively convert non-serializable types (e.g. numpy scalars) for JSON."""
    if isinstance(obj, dict):
        return {str(k): _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        val = float(obj)
        return val if np.isfinite(val) else None
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj


def write_evaluation_summary(
    summary: Dict[str, Any],
    path: Path,
    *,
    config: EvaluationConfig,
    gt_path: Path,
) -> None:
    """Write evaluation-summary.json with provenance and all computed metrics."""
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = _make_serializable(summary)
    payload = {
        "model_id": config.model_id,
        "evaluation_timestamp": utc_now_str(),
        "dataset_id": "syn-sic-pc-dev-001",
        "feature_version": config.feature_version,
        "detector_version": config.detector_version,
        "evaluation_population": {
            "source": "M7 observation-scores.parquet + module-summary.parquet + ground-truth.parquet",
            "n_modules_total": summary.get("n_modules_total"),
            "n_healthy": summary.get("n_healthy"),
            "n_degrading": summary.get("n_degrading"),
            "n_terminal": summary.get("n_terminal"),
        },
        "ground_truth_path": str(gt_path),
        "ground_truth_used_for_training": False,
        "provenance": {
            "evaluation_package": "ml.evaluation",
            "model_id": config.model_id,
            "scores_path": str(config.score_dir),
            "model_path": str(config.model_dir),
        },
        "module_threshold": summary.get("module_threshold"),
        "module_level_metrics": serializable.get("module_level_metrics"),
        "observation_level_flag_rates": serializable.get("observation_flag_rates"),
        "timing": serializable.get("timing"),
        "timing_by_mechanism": serializable.get("timing_by_mechanism"),
        "false_positive_summary": serializable.get("false_positive_summary"),
        "baseline_comparison": serializable.get("baseline_comparison"),
        "m7_test_lot_compatibility": serializable.get("m7_test_lot_compatibility"),
        "stratified": serializable.get("stratified"),
        "detection_rate_by_severity": serializable.get("detection_rate_by_severity"),
        "disclaimer": (
            "M8 evaluates the frozen M7 detector against synthetic ground truth. "
            "Metrics are for the evaluated frozen dataset only and are not a universal "
            "accuracy claim. An anomaly is not a confirmed physical failure. "
            "M8 does not perform root-cause analysis."
        ),
    }
    path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
"""M8 evaluation pipeline.

Loads the frozen M7 observation scores, module summary, model record, and synthetic
ground truth; validates them; computes module-level, observation-level (descriptive),
timing, false-positive, and statistical-baseline-comparison results; writes evaluation
artifacts under ``ml/datasets/evaluation/<model_id>/``.

M7 artifacts (``ml/datasets/scores/`` and ``ml/models/``) are never modified.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from .artifacts import (
    write_baseline_comparison,
    write_evaluation_summary,
    write_module_evaluation,
    write_timing_analysis,
)
from .config import (
    EvaluationConfig,
    EXPECTED_DATA_ORIGIN,
    EXPECTED_SCENARIO,
    GROUND_TRUTH_RELATIVE,
    HEALTHY_LABEL,
)
from .metrics import (
    baseline_comparison_metrics,
    compute_lead_times,
    compute_test_lot_metrics,
    detection_rate_by_severity,
    false_positive_summary,
    observation_flag_rate_summary,
    stratified_metrics,
    timing_by_mechanism,
)


@dataclass
class EvaluationResult:
    """Container for M8 evaluation outputs."""

    config: EvaluationConfig
    module_eval: pd.DataFrame
    timing_analysis: pd.DataFrame
    baseline_comparison: pd.DataFrame
    summary: Dict[str, Any]
    output_dir: Path


REQUIRED_GT_FIELDS = [
    "module_id",
    "lot_id",
    "health_state",
    "degradation_mechanism",
    "degradation_stage",
    "onset_cycle",
    "cycle_measurable",
    "degradation_severity",
    "damage_index_end",
    "rate_scale",
    "dataset_id",
    "scenario",
]


class GroundTruthError(RuntimeError):
    """Raised for any ground-truth integrity problem that must not be silently repaired."""


def load_ground_truth(dataset_dir: Path) -> pd.DataFrame:
    """Load and validate ground-truth.parquet.

    Fails clearly on any integrity problem rather than silently repairing it.
    """
    gt_path = dataset_dir / GROUND_TRUTH_RELATIVE
    if not gt_path.exists():
        raise GroundTruthError(f"Ground truth missing: {gt_path}")
    gt = pd.read_parquet(gt_path)
    missing = [c for c in REQUIRED_GT_FIELDS if c not in gt.columns]
    if missing:
        raise GroundTruthError(f"Ground truth missing required fields: {missing}")
    if "data_origin" in gt.columns:
        origins = set(gt["data_origin"].astype(str).unique())
        if origins != {EXPECTED_DATA_ORIGIN}:
            raise GroundTruthError(f"Unsupported data_origin: {origins}")
    if "scenario" in gt.columns:
        scenarios = set(gt["scenario"].astype(str).unique())
        unsupported = scenarios - {EXPECTED_SCENARIO}
        if unsupported:
            raise GroundTruthError(f"Unsupported scenario(s): {sorted(unsupported)}")
    if "dataset_id" in gt.columns:
        dataset_ids = set(gt["dataset_id"].astype(str).unique())
        if len(dataset_ids) != 1:
            raise GroundTruthError(f"Unexpected multiple dataset_id values: {sorted(dataset_ids)}")
    if gt["module_id"].duplicated().any():
        dup = gt.loc[gt["module_id"].duplicated(), "module_id"].tolist()
        raise GroundTruthError(f"Duplicate module_id in ground truth: {sorted(set(dup))[:10]}")
    return gt


def load_m7_artifacts(config: EvaluationConfig) -> dict[str, Any]:
    """Load and validate the frozen M7 artifacts."""
    missing = []
    score_dir = config.score_dir
    model_dir = config.model_dir
    obs_path = score_dir / "observation-scores.parquet"
    mod_path = score_dir / "module-summary.parquet"
    record_path = model_dir / "model-record.json"
    for p in (obs_path, mod_path, record_path):
        if not p.exists():
            missing.append(str(p))
    if missing:
        raise FileNotFoundError(f"Missing M7 artifacts: {missing}")

    observation = pd.read_parquet(obs_path)
    module_summary = pd.read_parquet(mod_path)
    record = json.loads(record_path.read_text(encoding="utf-8"))

    # Validate the module threshold comes from the frozen M7 record.
    eval_meta = record.get("evaluation") or {}
    module_threshold = eval_meta.get("module_threshold")
    if module_threshold is None:
        raise ValueError(f"model-record evaluation.module_threshold missing for {config.model_id}")
    module_threshold = float(module_threshold)

    if record.get("model_id") != config.model_id:
        raise ValueError(
            f"model-record model_id {record.get('model_id')} != requested {config.model_id}"
        )
    if record.get("feature_version") != config.feature_version:
        raise ValueError(
            f"feature_version {record.get('feature_version')} != expected {config.feature_version}"
        )

    # Confirm observation score schema (frozen M7 contract).
    for col in ("module_id", "cycle_number", "anomaly_score", "is_anomaly",
               "statistical_baseline_score", "statistical_baseline_flag"):
        if col not in observation.columns:
            raise ValueError(f"observation-scores missing required column: {col}")
    for col in ("module_id", "max_anomaly_score", "statistical_baseline_max"):
        if col not in module_summary.columns:
            raise ValueError(f"module-summary missing required column: {col}")

    return {
        "observation": observation,
        "module_summary": module_summary,
        "record": record,
        "module_threshold": module_threshold,
    }


def _compute_first_flag_cycle(observation: pd.DataFrame, module_threshold: float) -> pd.DataFrame:
    """First cycle where anomaly_score >= module_threshold, per module.

    Uses the frozen M7 **module threshold**, not the observation-level threshold.
    """
    flagged = observation.loc[observation["anomaly_score"] >= module_threshold]
    if flagged.empty:
        empty = {}
        return pd.DataFrame({"module_id": [], "first_flag_cycle": []})
    first = (
        flagged.sort_values(["module_id", "cycle_number"])
        .groupby("module_id", sort=False)["cycle_number"]
        .first()
        .rename("first_flag_cycle")
    )
    return first.reset_index()


def _n_flagged_observations(observation: pd.DataFrame, module_threshold: float) -> pd.Series:
    """Count observations with anomaly_score >= module_threshold per module."""
    flagged = observation.loc[observation["anomaly_score"] >= module_threshold]
    if flagged.empty:
        return pd.Series(dtype=int)
    return flagged.groupby("module_id", sort=False).size().rename("n_flagged_observations")


def _build_module_eval(
    module_summary: pd.DataFrame,
    ground_truth: pd.DataFrame,
    observation: pd.DataFrame,
    module_threshold: float,
    baseline_threshold: float,
) -> pd.DataFrame:
    """1:1 join of M7 module-summary with ground truth plus derived fields."""
    gt = ground_truth.copy()
    gt["module_id"] = gt["module_id"].astype(str)
    # Guard against duplicate GT module ids (extra safety; already validated upstream).
    gt = gt.drop_duplicates("module_id")
    joined = module_summary.merge(gt, on="module_id", how="inner")
    # Collapse duplicate identifier columns from module-summary and GT.
    for col in ("lot_id", "test_id", "dataset_id"):
        # Prefer the ground-truth copy if present, else the summary copy.
        pref = f"{col}_y" if f"{col}_y" in joined.columns else (col if col in joined.columns else None)
        alt = f"{col}_x" if f"{col}_x" in joined.columns else None
        if pref is not None and alt is not None:
            joined[col] = joined[alt].where(joined[pref].isna(), joined[pref])
            joined = joined.drop(columns=[pref, alt])
    missing_modules = set(module_summary["module_id"]) - set(gt["module_id"])
    if missing_modules:
        raise GroundTruthError(f"module-summary modules missing from ground truth: {sorted(missing_modules)[:10]}")
    extra = set(gt["module_id"]) - set(module_summary["module_id"])
    if extra:
        raise GroundTruthError(f"ground-truth modules missing from module-summary: {sorted(extra)[:10]}")

    joined["y_true"] = joined["health_state"].astype(str) != HEALTHY_LABEL
    joined["y_pred_module"] = joined["max_anomaly_score"] >= module_threshold

    first_flag = _compute_first_flag_cycle(observation, module_threshold)
    joined = joined.merge(first_flag, on="module_id", how="left")

    onset = pd.to_numeric(joined["onset_cycle"], errors="coerce")
    measurable = pd.to_numeric(joined["cycle_measurable"], errors="coerce")
    flag = pd.to_numeric(joined["first_flag_cycle"], errors="coerce")
    joined["lead_vs_onset"] = onset - flag
    joined["lead_vs_measurable"] = measurable - flag

    # Statistical baseline module flag (threshold = 3.0).
    joined["statistical_baseline_flag_module"] = (
        pd.to_numeric(joined["statistical_baseline_max"], errors="coerce")
        >= baseline_threshold
    )
    joined["y_pred_baseline"] = joined["statistical_baseline_flag_module"]
    return joined


def run_evaluation(
    dataset_dir: str | Path,
    config: EvaluationConfig | None = None,
    *,
    write: bool = True,
) -> EvaluationResult:
    """Run the M8 evaluation end-to-end.

    Parameters
    ----------
    dataset_dir : str | Path
        Directory that contains ``ground_truth/ground-truth.parquet``.
    config : EvaluationConfig | None
        Evaluation configuration; defaults to the authoritative model default.
    write : bool
        If True, write artifacts under ``ml/datasets/evaluation/<model_id>/``.
    """
    config = config or EvaluationConfig()
    dataset_dir = Path(dataset_dir)

    ground_truth = load_ground_truth(dataset_dir)
    artifacts = load_m7_artifacts(config)
    observation = artifacts["observation"]
    module_summary = artifacts["module_summary"]
    module_threshold = artifacts["module_threshold"]

    module_eval = _build_module_eval(
        module_summary, ground_truth, observation, module_threshold, config.baseline_threshold
    )

    # Population accounting.
    health_counts = module_eval["health_state"].astype(str).value_counts().to_dict()
    degraded_mask = module_eval["y_true"]
    timing = compute_lead_times(module_eval)
    timing_by_mech = timing_by_mechanism(module_eval)
    obs_flag_rates = observation_flag_rate_summary(observation, module_eval)
    fp_summary = false_positive_summary(
        module_eval, observation.loc[:, ["module_id", "anomaly_score", "is_anomaly"]]
    )

    # Stratified module metrics.
    strat = {
        "by_health_state": stratified_metrics(module_eval, stratum_column="health_state"),
        "by_mechanism": stratified_metrics(module_eval, stratum_column="degradation_mechanism"),
        "by_lot": stratified_metrics(module_eval, stratum_column="lot_id"),
        "by_stage": stratified_metrics(module_eval, stratum_column="degradation_stage"),
        "by_severity": detection_rate_by_severity(module_eval),
    }

    from .metrics import classification_metrics

    module_metrics = classification_metrics(
        module_eval["y_true"].to_numpy(), module_eval["y_pred_module"].to_numpy()
    )
    baseline_comp = baseline_comparison_metrics(module_eval)

    # M7 held-out test lot compatibility (frozen M7 split).
    test_lots = (
        artifacts.get("record", {}).get("split", {}).get("test_lots", [])
    )
    m7_test_lot = None
    if test_lots:
        m7_test_lot = compute_test_lot_metrics(module_eval, test_lots)

    # Timing analysis parquet: positive modules that were actually detected.
    detected = module_eval.loc[
        module_eval["y_true"] & module_eval["first_flag_cycle"].notna()
    ].copy()
    n_flag_obs = _n_flagged_observations(observation, module_threshold).rename("n_flagged_observations")
    # detected already has max_anomaly_score and statistical_baseline_max from module_eval.
    timing_df = detected.merge(n_flag_obs, on="module_id", how="left")
    timing_df = timing_df[[
        "module_id", "degradation_mechanism", "health_state", "onset_cycle",
        "cycle_measurable", "first_flag_cycle", "lead_vs_onset", "lead_vs_measurable",
        "n_flagged_observations", "max_anomaly_score", "statistical_baseline_max",
    ]]

    baseline_comp_df = module_eval[[
        "module_id", "max_anomaly_score", "statistical_baseline_max",
        "y_pred_module", "statistical_baseline_flag_module", "health_state",
        "degradation_mechanism",
    ]].copy()
    baseline_comp_df = baseline_comp_df.rename(columns={
        "y_pred_module": "if_flag_module",
        "statistical_baseline_flag_module": "base_flag_module",
    })

    summary: Dict[str, Any] = {
        "n_modules_total": int(len(module_eval)),
        "n_healthy": int(health_counts.get(HEALTHY_LABEL, 0)),
        "n_degrading": int(module_eval["health_state"].astype(str).eq("degrading").sum()),
        "n_terminal": int(module_eval["health_state"].astype(str).eq("terminal").sum()),
        "n_positive": int(module_eval["y_true"].sum()),
        "module_threshold": module_threshold,
        "module_level_metrics": module_metrics,
        "stratified": strat,
        "observation_flag_rates": obs_flag_rates,
        "timing": timing,
        "timing_by_mechanism": timing_by_mech,
        "false_positive_summary": fp_summary,
        "baseline_comparison": baseline_comp,
        "m7_test_lot_compatibility": m7_test_lot,
        "ground_truth_path": str(dataset_dir / GROUND_TRUTH_RELATIVE),
        "detection_rate_by_severity": strat["by_severity"],
    }

    result = EvaluationResult(
        config=config,
        module_eval=module_eval,
        timing_analysis=timing_df,
        baseline_comparison=baseline_comp_df,
        summary=summary,
        output_dir=config.output_dir,
    )

    if write:
        write_module_evaluation(module_eval, config.output_dir / "module-evaluation.parquet")
        write_timing_analysis(timing_df, config.output_dir / "timing-analysis.parquet")
        write_baseline_comparison(baseline_comp_df, config.output_dir / "baseline-comparison.parquet")
        write_evaluation_summary(
            summary,
            config.output_dir / "evaluation-summary.json",
            config=config,
            gt_path=dataset_dir / GROUND_TRUTH_RELATIVE,
        )
    return result
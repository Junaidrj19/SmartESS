"""Metrics for M8 evaluation.

All functions are deterministic given their inputs. Classification and timing
semantics are defined in the M8 contract document.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .config import HEALTHY_LABEL, STATISTICAL_BASELINE_THRESHOLD, SEVERITY_BINS, SEVERITY_LABELS


def _safe_div(num: float, den: float) -> float:
    if den == 0:
        return float("nan")
    return num / den


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    """Compute module-level classification metrics.

    Parameters
    ----------
    y_true : np.ndarray
        Boolean array, true labels (True = degraded/terminal).
    y_pred : np.ndarray
        Boolean array, predicted anomaly flags.
    """
    y_true = np.asarray(y_true, dtype=bool)
    y_pred = np.asarray(y_pred, dtype=bool)
    n = len(y_true)
    n_pos = int(y_true.sum())
    n_neg = n - n_pos
    tp = int((y_true & y_pred).sum())
    tn = int((~y_true & ~y_pred).sum())
    fp = int((~y_true & y_pred).sum())
    fn = int((y_true & ~y_pred).sum())
    return {
        "n_modules": n,
        "n_positive": n_pos,
        "n_negative": n_neg,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": _safe_div(tp, tp + fp),
        "recall": _safe_div(tp, tp + fn),
        "f1": _safe_div(2 * tp, 2 * tp + fp + fn) if (tp + fp + fn) > 0 else float("nan"),
        "false_positive_rate": _safe_div(fp, fp + tn),
        "false_negative_rate": _safe_div(fn, fn + tp),
    }


def stratified_metrics(
    module_eval: pd.DataFrame,
    *,
    stratum_column: str,
) -> Dict[str, Any]:
    """Calculate classification metrics per stratum.

    Parameters
    ----------
    module_eval : pd.DataFrame
        Must contain columns ``y_true``, ``y_pred_module``, and *stratum_column*.
    stratum_column : str
        Column name to group by.
    """
    if stratum_column not in module_eval.columns:
        raise ValueError(f"stratum column '{stratum_column}' not in module_eval")
    groups = module_eval.groupby(stratum_column, sort=True)
    strata = {}
    for name, group in groups:
        m = classification_metrics(group["y_true"].to_numpy(), group["y_pred_module"].to_numpy())
        m["n_modules"] = len(group)
        strata[str(name)] = m
    return strata


def compute_lead_times(
    module_eval: pd.DataFrame,
) -> Dict[str, Any]:
    """Compute detection-timing metrics for degraded/terminal modules.

    Uses the frozen M7 **module threshold** to define the first flag cycle,
    NOT the observation-level threshold.

    Parameters
    ----------
    module_eval : pd.DataFrame
        Must contain columns ``y_true``, ``first_flag_cycle``, ``onset_cycle``,
        ``cycle_measurable``.
    """
    detected = module_eval.loc[
        module_eval["y_true"] & module_eval["first_flag_cycle"].notna()
    ].copy()
    if detected.empty:
        return {
            "n_detected_positives": 0,
            "mean_lead_vs_onset_cycles": float("nan"),
            "median_lead_vs_onset_cycles": float("nan"),
            "mean_lead_vs_measurable_cycles": float("nan"),
            "median_lead_vs_measurable_cycles": float("nan"),
            "note": "No true-positive modules with a first flag cycle.",
        }
    onset = pd.to_numeric(detected["onset_cycle"], errors="coerce")
    measurable = pd.to_numeric(detected["cycle_measurable"], errors="coerce")
    flag = pd.to_numeric(detected["first_flag_cycle"], errors="coerce")
    lead_onset = onset - flag
    lead_meas = measurable - flag
    return {
        "n_detected_positives": int(len(detected)),
        "mean_lead_vs_onset_cycles": float(lead_onset.mean()) if lead_onset.notna().any() else float("nan"),
        "median_lead_vs_onset_cycles": float(lead_onset.median()) if lead_onset.notna().any() else float("nan"),
        "iqr_lead_vs_onset": float(lead_onset.quantile(0.75) - lead_onset.quantile(0.25)) if lead_onset.notna().any() else float("nan"),
        "mean_lead_vs_measurable_cycles": float(lead_meas.mean()) if lead_meas.notna().any() else float("nan"),
        "median_lead_vs_measurable_cycles": float(lead_meas.median()) if lead_meas.notna().any() else float("nan"),
        "note": "Positive lead time means the flag occurs before the reference cycle. Negative values are preserved.",
    }


def timing_by_mechanism(
    module_eval: pd.DataFrame,
) -> Dict[str, Any]:
    """Timing metrics stratified by degradation mechanism for detected positives.

    Parameters
    ----------
    module_eval : pd.DataFrame
        Must contain ``y_true``, ``first_flag_cycle``, ``onset_cycle``,
        ``cycle_measurable``, ``degradation_mechanism``.
    """
    detected = module_eval.loc[
        module_eval["y_true"] & module_eval["first_flag_cycle"].notna()
    ].copy()
    if detected.empty:
        return {"n_total_detected": 0, "by_mechanism": {}}
    result: Dict[str, Any] = {}
    for mech, group in detected.groupby("degradation_mechanism", sort=True):
        onset = pd.to_numeric(group["onset_cycle"], errors="coerce")
        measurable = pd.to_numeric(group["cycle_measurable"], errors="coerce")
        flag = pd.to_numeric(group["first_flag_cycle"], errors="coerce")
        lead_onset = onset - flag
        lead_meas = measurable - flag
        n_det = len(group)
        early = int((lead_onset > 0).sum())
        result[str(mech)] = {
            "n_detected": n_det,
            "mean_lead_vs_onset": float(lead_onset.mean()) if lead_onset.notna().any() else float("nan"),
            "median_lead_vs_onset": float(lead_onset.median()) if lead_onset.notna().any() else float("nan"),
            "iqr_lead_vs_onset": float(lead_onset.quantile(0.75) - lead_onset.quantile(0.25)) if lead_onset.notna().any() else float("nan"),
            "mean_lead_vs_measurable": float(lead_meas.mean()) if lead_meas.notna().any() else float("nan"),
            "median_lead_vs_measurable": float(lead_meas.median()) if lead_meas.notna().any() else float("nan"),
            "early_detection_rate": _safe_div(early, n_det),
            "detection_rate": _safe_div(n_det, len(module_eval.loc[module_eval["degradation_mechanism"] == mech])),
        }
    return {
        "n_total_detected": int(len(detected)),
        "by_mechanism": result,
    }


def observation_flag_rate_summary(
    observation_scores: pd.DataFrame,
    module_eval: pd.DataFrame,
) -> Dict[str, Any]:
    """Compute observation-level descriptive flag rates.

    Because ground truth is module-level only, no observation-level precision,
    recall, F1, FPR, or FNR is calculated.

    Parameters
    ----------
    observation_scores : pd.DataFrame
        Must contain ``module_id``, ``is_anomaly``, ``statistical_baseline_flag``.
    module_eval : pd.DataFrame
        Must contain ``module_id``, ``health_state`` (1:1 join key).
    """
    merged = observation_scores.merge(
        module_eval[["module_id", "health_state"]], on="module_id", how="inner"
    )
    result: Dict[str, Any] = {}
    for state, group in merged.groupby("health_state", sort=True):
        n_obs = len(group)
        if n_obs == 0:
            result[str(state)] = {"n_observations": 0}
            continue
        if_rate = float(group["is_anomaly"].mean())
        base_rate = float(group["statistical_baseline_flag"].mean())
        result[str(state)] = {
            "n_observations": n_obs,
            "isolation_forest_anomaly_flag_rate": if_rate,
            "statistical_baseline_flag_rate": base_rate,
        }
    result["disclaimer"] = (
        "Observation-level ground truth does not exist; observation-level metrics "
        "are flag-rate summaries only. No precision, recall, F1, FPR, or FNR "
        "is reported at the observation level."
    )
    return result


def false_positive_summary(
    module_eval: pd.DataFrame,
    observation_scores: pd.DataFrame,
) -> Dict[str, Any]:
    """False-positive descriptive summary at module level.

    Parameters
    ----------
    module_eval : pd.DataFrame
        Must contain ``y_true``, ``y_pred_module``, ``lot_id``, ``n_observations``.
    observation_scores : pd.DataFrame
        Must contain ``module_id``, ``anomaly_score``, ``is_anomaly``.
    """
    healthy = module_eval.loc[~module_eval["y_true"]]
    fp_modules = healthy.loc[healthy["y_pred_module"]]
    result: Dict[str, Any] = {
        "n_healthy_modules": int(len(healthy)),
        "n_false_positives": int(len(fp_modules)),
        "false_positive_rate": _safe_div(len(fp_modules), len(healthy)),
    }
    if len(fp_modules) > 0:
        scores = fp_modules["max_anomaly_score"]
        result["fp_score_distribution"] = {
            "min": float(scores.min()),
            "max": float(scores.max()),
            "mean": float(scores.mean()),
            "median": float(scores.median()),
        }
        lot_fp: Dict[str, int] = {}
        for lot_id, group in fp_modules.groupby("lot_id", sort=True):
            lot_fp[str(lot_id)] = int(len(group))
        result["fp_by_lot"] = lot_fp
        # Healthy observation flag rate (descriptive only).
        healthy_obs = observation_scores.loc[
            observation_scores["module_id"].isin(healthy["module_id"])
        ]
        if len(healthy_obs) > 0:
            result["healthy_observation_anomaly_flag_rate"] = float(healthy_obs["is_anomaly"].mean())
            so = healthy_obs["anomaly_score"]
            result["healthy_observation_score_distribution"] = {
                "min": float(so.min()),
                "max": float(so.max()),
                "mean": float(so.mean()),
                "median": float(so.median()),
            }
    else:
        result["note"] = "No false positives to describe."
    result["disclaimer"] = "Observation-level ground truth does not exist; observation-level metrics are flag-rate summaries only."
    return result


def baseline_comparison_metrics(
    module_eval: pd.DataFrame,
) -> Dict[str, Any]:
    """Compare Isolation Forest and statistical baseline on the same module population.

    Parameters
    ----------
    module_eval : pd.DataFrame
        Must contain ``y_true``, ``y_pred_module`` (IF), ``y_pred_baseline``,
        ``max_anomaly_score``, ``statistical_baseline_max``.
    """
    if_metrics = classification_metrics(
        module_eval["y_true"].to_numpy(), module_eval["y_pred_module"].to_numpy()
    )
    base_metrics = classification_metrics(
        module_eval["y_true"].to_numpy(), module_eval["y_pred_baseline"].to_numpy()
    )
    # Agreement matrix
    agreement = pd.crosstab(
        module_eval["y_pred_module"],
        module_eval["y_pred_baseline"],
        rownames=["IF"],
        colnames=["Baseline"],
    )
    if_vals = pd.to_numeric(module_eval["max_anomaly_score"], errors="coerce")
    base_vals = pd.to_numeric(module_eval["statistical_baseline_max"], errors="coerce")
    valid = if_vals.notna() & base_vals.notna()
    rho: float = float("nan")
    p_val: float = float("nan")
    if valid.sum() > 2:
        rho_s, p_s = spearmanr(if_vals[valid], base_vals[valid])
        rho = float(rho_s)
        p_val = float(p_s)
    return {
        "isolation_forest": {
            "module_threshold": None,
            "metrics": if_metrics,
        },
        "statistical_baseline": {
            "module_threshold": STATISTICAL_BASELINE_THRESHOLD,
            "metrics": base_metrics,
        },
        "agreement_matrix": {
            str(k): {str(c): int(v) for c, v in row.items()}
            for k, row in agreement.items()
        },
        "spearman_correlation": {"rho": rho, "p_value": p_val},
        "note": "Both detectors evaluated on the same 750-module population. Baseline threshold=3.0.",
    }


def compute_test_lot_metrics(
    module_eval: pd.DataFrame,
    test_lots: List[str],
) -> Dict[str, Any]:
    """Reproduce M8 metrics on the frozen M7 held-out test lots only.

    This is a **compatibility** view: it subsets the 750-module evaluation
    population to the M7 ``lot_holdout`` test lots and recomputes the same
    module-level classification metrics used for the overall population. It does **not**
    retrain, modify the frozen detector, or alter the overall-population evaluation.

    Parameters
    ----------
    module_eval : pd.DataFrame
        The 750-module evaluation frame. Must contain ``module_id``,
        ``lot_id``, ``y_true``, ``y_pred_module``.
    test_lots : List[str]
        The M7 held-out test lot ids (e.g. ``["lot-01", "lot-04"]``).
    """
    lot_col = "lot_id" if "lot_id" in module_eval.columns else "module_id"
    test = module_eval.loc[module_eval[lot_col].isin(test_lots)].copy()
    if test.empty:
        raise ValueError("No modules found for the given test lots")
    metrics = classification_metrics(
        test["y_true"].to_numpy(), test["y_pred_module"].to_numpy()
    )
    return {
        "split_type": "lot_holdout",
        "test_lots": list(test_lots),
        "n_modules": int(len(test)),
        "metrics": metrics,
        "note": (
            "Reproduced M8 metrics on the frozen M7 held-out test lots. "
            "Compatibility view only; the overall 750-module population evaluation "
            "is unchanged."
        ),
    }


def severity_binned_label(severity: float) -> str:
    """Map continuous severity to a descriptive bin label."""
    if pd.isna(severity):
        return "unknown"
    for label, low, high in zip(
        SEVERITY_LABELS, SEVERITY_BINS[:-1], SEVERITY_BINS[1:]
    ):
        if low <= severity < high:
            return label
    return "unknown"


def detection_rate_by_severity(
    module_eval: pd.DataFrame,
) -> Dict[str, Any]:
    """Detection rate stratified by severity bin for positive modules."""
    pos = module_eval.loc[module_eval["y_true"]].copy()
    if pos.empty:
        return {}
    pos["severity_bin"] = pos["degradation_severity"].apply(severity_binned_label)
    result: Dict[str, Any] = {}
    for bin_label, group in pos.groupby("severity_bin", sort=True):
        n = len(group)
        n_detected = int(group["y_pred_module"].sum())
        result[bin_label] = {
            "n_modules": n,
            "n_detected": n_detected,
            "detection_rate": _safe_div(n_detected, n),
        }
    return result
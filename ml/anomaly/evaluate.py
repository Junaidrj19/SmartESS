"""Evaluation-only metrics. Ground truth is loaded here, never during training."""

from __future__ import annotations

from typing import Any, Dict

import numpy as np
import pandas as pd


def _safe_div(num: float, den: float) -> float:
    if den == 0:
        return float("nan")
    return num / den


def module_score_threshold(train_scores: pd.DataFrame, contamination: float) -> float:
    maxima = train_scores.groupby("module_id")["anomaly_score"].max()
    if maxima.empty:
        raise ValueError("cannot calibrate module threshold on empty train scores")
    return float(np.quantile(maxima.to_numpy(dtype=float), 1.0 - contamination))


def module_detection_table(
    observation_scores: pd.DataFrame,
    ground_truth: pd.DataFrame,
    *,
    module_threshold: float,
) -> pd.DataFrame:
    required = {"module_id", "cycle_number", "anomaly_score"}
    missing = required - set(observation_scores.columns)
    if missing:
        raise ValueError(f"scores missing columns: {sorted(missing)}")
    gt = ground_truth.copy()
    if "module_id" not in gt.columns:
        raise ValueError("ground truth must include module_id")
    gt["module_id"] = gt["module_id"].astype(str)
    health = gt["health_state"] if "health_state" in gt.columns else pd.Series(["unknown"] * len(gt))
    y_true = health.astype(str).ne("healthy")
    labels = gt.assign(y_true=y_true)[["module_id", "y_true"]].drop_duplicates("module_id")
    if "onset_cycle" in gt.columns:
        labels = labels.merge(gt[["module_id", "onset_cycle"]].drop_duplicates("module_id"), on="module_id", how="left")
    else:
        labels["onset_cycle"] = np.nan
    if "cycle_measurable" in gt.columns:
        labels = labels.merge(
            gt[["module_id", "cycle_measurable"]].drop_duplicates("module_id"), on="module_id", how="left"
        )
    else:
        labels["cycle_measurable"] = np.nan

    flagged_obs = observation_scores.loc[observation_scores["anomaly_score"] >= module_threshold]
    first_flag = (
        flagged_obs.sort_values(["module_id", "cycle_number"])
        .groupby("module_id", sort=False)["cycle_number"]
        .first()
        .rename("first_flag_cycle")
    )
    module_scores = observation_scores.groupby("module_id")["anomaly_score"].max().rename("module_score")
    table = labels.merge(module_scores.reset_index(), on="module_id", how="inner")
    table = table.merge(first_flag.reset_index(), on="module_id", how="left")
    table["y_pred"] = table["module_score"] >= module_threshold
    return table


def classification_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, Any]:
    y_true = np.asarray(y_true, dtype=bool)
    y_pred = np.asarray(y_pred, dtype=bool)
    tp = int((y_true & y_pred).sum())
    tn = int((~y_true & ~y_pred).sum())
    fp = int((~y_true & y_pred).sum())
    fn = int((y_true & ~y_pred).sum())
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    if np.isfinite(precision) and np.isfinite(recall) and (precision + recall) > 0:
        f1 = _safe_div(2 * precision * recall, precision + recall)
    else:
        f1 = float("nan")
    return {
        "n_modules": int(len(y_true)),
        "n_positive": int(y_true.sum()),
        "n_negative": int((~y_true).sum()),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": _safe_div(fp, fp + tn),
        "false_negative_rate": _safe_div(fn, fn + tp),
    }


def lead_time_metrics(table: pd.DataFrame) -> Dict[str, Any]:
    detected = table.loc[table["y_true"] & table["y_pred"] & table["first_flag_cycle"].notna()].copy()
    if detected.empty:
        return {
            "n_detected_positives": 0,
            "mean_lead_vs_onset_cycles": float("nan"),
            "mean_lead_vs_measurable_cycles": float("nan"),
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
        "mean_lead_vs_measurable_cycles": float(lead_meas.mean()) if lead_meas.notna().any() else float("nan"),
        "median_lead_vs_measurable_cycles": float(lead_meas.median()) if lead_meas.notna().any() else float("nan"),
        "note": "Positive lead time means the flag occurs before the reference cycle.",
    }


def evaluate_scores(
    observation_scores: pd.DataFrame,
    ground_truth: pd.DataFrame,
    *,
    split_name: str,
    module_threshold: float,
) -> Dict[str, Any]:
    table = module_detection_table(
        observation_scores, ground_truth, module_threshold=module_threshold
    )
    metrics = classification_metrics(table["y_true"].to_numpy(), table["y_pred"].to_numpy())
    lead = lead_time_metrics(table)
    return {
        "split": split_name,
        "unit": "module",
        "module_score": "max_observation_anomaly_score",
        "module_threshold": module_threshold,
        "metrics": metrics,
        "lead_time": lead,
        "disclaimer": (
            "Metrics are for this synthetic evaluation split only. "
            "They are not a universal accuracy claim. An anomaly is not a confirmed failure."
        ),
    }

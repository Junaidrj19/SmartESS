"""Module-level anomaly summary for M7.

Descriptive summary of observation-level anomaly outputs, one row per module.
This is NOT a failure diagnosis and NOT a complex health score.
"""

from __future__ import annotations

from typing import Dict

import pandas as pd

ANOMALY_RATE_SPORADIC_CUTOFF: float = 0.1

SCORE_COLUMNS = ("module_id", "test_id", "lot_id", "dataset_id")
BASE_COLUMNS = (
    "module_id",
    "test_id",
    "lot_id",
    "dataset_id",
    "n_observations",
    "n_anomalous_observations",
    "anomaly_rate",
    "max_anomaly_score",
    "mean_anomaly_score",
    "first_anomalous_cycle",
    "last_anomalous_cycle",
    "anomalous_cycle_span",
    "statistical_baseline_max",
    "statistical_baseline_flag_rate",
    "module_anomaly_status",
)


def module_status(anomaly_rate: float, *, n_anomalous: int) -> str:
    """Classify a module as clean / sporadic / persistent.

    - clean:      0 flagged observations
    - sporadic:   anomaly_rate < 0.1
    - persistent: anomaly_rate >= 0.1
    """
    if n_anomalous == 0 or anomaly_rate == 0.0:
        return "clean"
    if anomaly_rate < ANOMALY_RATE_SPORADIC_CUTOFF:
        return "sporadic"
    return "persistent"


def aggregate_module_summary(observation_scores: pd.DataFrame) -> pd.DataFrame:
    """Summarize observation scores into one row per module.

    Parameters
    ----------
    observation_scores : pd.DataFrame
        The M7 observation-scores output (module_id ... is_anomaly,
        statistical_baseline_score, statistical_baseline_flag ...).

    Returns
    -------
    pd.DataFrame
        One row per module with the documented summary fields.
    """
    missing = [c for c in SCORE_COLUMNS + ("cycle_number", "is_anomaly", "anomaly_score",
                                             "statistical_baseline_score", "statistical_baseline_flag")
               if c not in observation_scores.columns]
    if missing:
        raise ValueError(f"observation_scores missing required columns: {sorted(missing)}")

    ids = observation_scores[list(SCORE_COLUMNS)].drop_duplicates("module_id").set_index("module_id")

    grouped = observation_scores.groupby("module_id", sort=False)
    n_obs = grouped.size()
    is_anom = observation_scores["is_anomaly"].astype(bool)
    n_anomalous = grouped["is_anomaly"].apply(lambda s: int(s.astype(bool).sum()))
    anomaly_rate = n_anomalous / n_obs
    max_score = grouped["anomaly_score"].max()
    mean_score = grouped["anomaly_score"].mean()

    anomaly_rows = observation_scores.loc[is_anom]
    if anomaly_rows.empty:
        first_cycle = pd.Series([None] * len(n_obs), index=n_obs.index, dtype=object)
        last_cycle = pd.Series([None] * len(n_obs), index=n_obs.index, dtype=object)
    else:
        first_cycle = (
            anomaly_rows.sort_values(["module_id", "cycle_number"])
            .groupby("module_id", sort=False)["cycle_number"]
            .first()
        )
        last_cycle = (
            anomaly_rows.sort_values(["module_id", "cycle_number"])
            .groupby("module_id", sort=False)["cycle_number"]
            .last()
        )
    first_cycle = first_cycle.reindex(n_obs.index)
    last_cycle = last_cycle.reindex(n_obs.index)
    cycle_span = pd.Series(
        [
            (None if (pd.isna(f) or pd.isna(l)) else int(l) - int(f))
            for f, l in zip(first_cycle, last_cycle)
        ],
        index=n_obs.index,
        dtype=object,
    )

    stat_max = grouped["statistical_baseline_score"].max()
    stat_flag = observation_scores["statistical_baseline_flag"].astype(bool)
    stat_flag_rate = grouped["statistical_baseline_flag"].apply(
        lambda s: float(s.astype(bool).mean())
    )

    status = pd.Series(
        [module_status(r, n_anomalous=n_anom) for r, n_anom in zip(anomaly_rate, n_anomalous)],
        index=n_obs.index,
    )

    summary = pd.DataFrame(
        {
            "n_observations": n_obs,
            "n_anomalous_observations": n_anomalous,
            "anomaly_rate": anomaly_rate,
            "max_anomaly_score": max_score,
            "mean_anomaly_score": mean_score,
            "first_anomalous_cycle": first_cycle,
            "last_anomalous_cycle": last_cycle,
            "anomalous_cycle_span": cycle_span,
            "statistical_baseline_max": stat_max,
            "statistical_baseline_flag_rate": stat_flag_rate,
            "module_anomaly_status": status,
        },
        index=n_obs.index,
    )
    out = pd.concat([ids, summary], axis=1).reset_index()
    return out.reindex(columns=[c for c in BASE_COLUMNS if c in out.columns])


def module_summary_config() -> Dict[str, object]:
    return {
        "module_status.clean": "0 flagged observations",
        "module_status.sporadic": "anomaly_rate < 0.1",
        "module_status.persistent": "anomaly_rate >= 0.1",
        "note": "Descriptive anomaly summary only. Not a failure diagnosis.",
    }
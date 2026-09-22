"""Deterministic statistical baseline for M7 anomaly detection.

Uses the M6 robust-normalized-deviation features for the 8 core
baseline/rolling signals. Higher score = more anomalous.
No ML model is involved. No ground truth is used.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from .features import observation_model_feature_names

BASELINE_SIGNALS: Tuple[str, ...] = (
    "RDS_on",
    "VTH",
    "IGSS",
    "IDSS",
    "VDS_on",
    "electrical_power",
    "Tj",
    "Tc",
)
BASELINE_THRESHOLD: float = 3.0
BASELINE_TYPE: str = "robust_normalized_deviation_max"


def _assert_features_present(observation_features: pd.DataFrame) -> None:
    for signal in BASELINE_SIGNALS:
        col = f"{signal}_robust_normalized_deviation"
        if col not in observation_features.columns:
            raise ValueError(
                f"Statistical baseline requires M6 column '{col}', which is missing. "
                "Ensure the observation features were produced by the v1 feature pipeline."
            )


def compute_statistical_baseline(
    observation_features: pd.DataFrame,
) -> pd.DataFrame:
    """Compute statistical baseline scores and flags.

    Parameters
    ----------
    observation_features : pd.DataFrame
        Must contain the 160-column M6 v1 observation schema, including the 8
        robust_normalized_deviation columns and the 7 identifier columns.

    Returns
    -------
    pd.DataFrame
        Index-aligned frame with columns:
        - statistical_baseline_score  (float, NaN where all 8 signals are missing)
        - statistical_baseline_flag   (bool)
    """
    _assert_features_present(observation_features)

    deviations: List[pd.Series] = []
    for signal in BASELINE_SIGNALS:
        col = f"{signal}_robust_normalized_deviation"
        series = pd.to_numeric(observation_features[col], errors="coerce")
        deviations.append(series)

    stacked = np.abs(np.column_stack(deviations))
    score = pd.Series(
        np.nanmax(stacked, axis=1),
        index=observation_features.index,
        dtype=float,
    )
    mask = np.all(np.isnan(stacked), axis=1)
    score[mask] = np.nan

    flag = score >= BASELINE_THRESHOLD

    return pd.DataFrame(
        {
            "statistical_baseline_score": score,
            "statistical_baseline_flag": flag,
        },
        index=observation_features.index,
    )


def baseline_config() -> Dict[str, object]:
    return {
        "baseline_type": BASELINE_TYPE,
        "baseline_threshold": BASELINE_THRESHOLD,
        "baseline_definition": "max(abs(robust_normalized_deviation)) across the 8 core signals",
        "baseline_signals": list(BASELINE_SIGNALS),
        "score_direction": "higher = more anomalous",
    }
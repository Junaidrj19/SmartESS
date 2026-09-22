"""Small vectorized helpers. No sklearn / no classifiers."""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from ml.validators.synthetic.constants import VALID_VALUE_STATUSES


def finite_series(values: pd.Series) -> np.ndarray:
    numeric = pd.to_numeric(values, errors="coerce")
    array = numeric.to_numpy(dtype=float)
    return array[np.isfinite(array)]


def pearson(x: np.ndarray, y: np.ndarray) -> Optional[float]:
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) < 8:
        return None
    xa = x[mask]
    ya = y[mask]
    if float(np.std(xa)) == 0.0 or float(np.std(ya)) == 0.0:
        return None
    return float(np.corrcoef(xa, ya)[0, 1])


def cohens_d(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    a = a[np.isfinite(a)]
    b = b[np.isfinite(b)]
    if len(a) < 3 or len(b) < 3:
        return None
    var_a = float(np.var(a, ddof=1))
    var_b = float(np.var(b, ddof=1))
    pooled = np.sqrt(((len(a) - 1) * var_a + (len(b) - 1) * var_b) / (len(a) + len(b) - 2))
    if pooled == 0.0:
        return 0.0
    return float((np.mean(a) - np.mean(b)) / pooled)


def mad_z_outlier_rate(values: np.ndarray, *, z: float = 8.0) -> float:
    values = values[np.isfinite(values)]
    if len(values) < 20:
        return 0.0
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    if mad == 0.0:
        std = float(np.std(values))
        if std == 0.0:
            return 0.0
        score = np.abs(values - median) / std
    else:
        score = 0.6745 * np.abs(values - median) / mad
    return float(np.mean(score > z))


def valid_mask(frame: pd.DataFrame, channel: str) -> pd.Series:
    status_col = f"{channel}_status"
    if channel not in frame.columns or status_col not in frame.columns:
        return pd.Series(False, index=frame.index)
    status = frame[status_col].astype(str)
    numeric = pd.to_numeric(frame[channel], errors="coerce")
    return status.isin(VALID_VALUE_STATUSES) & numeric.notna() & np.isfinite(numeric.to_numpy())


def channel_values(frame: pd.DataFrame, channel: str) -> np.ndarray:
    mask = valid_mask(frame, channel)
    return pd.to_numeric(frame.loc[mask, channel], errors="coerce").to_numpy(dtype=float)


def attach_ground_truth(telemetry: pd.DataFrame, ground_truth: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Join GT labels without colliding with leaked telemetry columns."""

    keep = ["module_id"] + [c for c in columns if c in ground_truth.columns]
    labels = ground_truth[keep].copy()
    overlap = [c for c in labels.columns if c != "module_id" and c in telemetry.columns]
    left = telemetry.drop(columns=overlap)
    return left.merge(labels, on="module_id", how="left")


def last_per_module(telemetry: pd.DataFrame) -> pd.DataFrame:
    ordered = telemetry.sort_values(["module_id", "cycle_number"], kind="mergesort")
    return ordered.groupby("module_id", sort=False, as_index=False).tail(1)


def first_per_module(telemetry: pd.DataFrame) -> pd.DataFrame:
    ordered = telemetry.sort_values(["module_id", "cycle_number"], kind="mergesort")
    return ordered.groupby("module_id", sort=False, as_index=False).head(1)

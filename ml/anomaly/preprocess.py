"""Train-only preprocessing. Does not mutate M6 feature parquet files."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np
import pandas as pd


@dataclass
class MedianImputer:
    """Column medians fit on the training matrix only."""

    medians: Dict[str, float]
    all_nan_columns: List[str]
    feature_names: List[str]

    def transform(self, frame: pd.DataFrame) -> np.ndarray:
        ordered = frame.loc[:, self.feature_names].copy()
        for name in self.feature_names:
            median = self.medians[name]
            ordered[name] = pd.to_numeric(ordered[name], errors="coerce").fillna(median)
        array = ordered.to_numpy(dtype=float)
        array = np.where(np.isfinite(array), array, 0.0)
        return array

    def to_dict(self) -> dict:
        return {
            "strategy": "median_fit_on_train_only",
            "all_nan_columns": list(self.all_nan_columns),
            "n_features": len(self.feature_names),
            "note": (
                "Imputation is a model-preprocessing step. M6 feature parquet values "
                "are not modified. All-NaN train columns use 0.0 as a placeholder."
            ),
        }


def fit_median_imputer(train_features: pd.DataFrame) -> MedianImputer:
    medians: Dict[str, float] = {}
    all_nan: List[str] = []
    names = list(train_features.columns)
    for name in names:
        series = pd.to_numeric(train_features[name], errors="coerce")
        median = series.median(skipna=True)
        if pd.isna(median):
            all_nan.append(name)
            medians[name] = 0.0
        else:
            medians[name] = float(median)
    return MedianImputer(medians=medians, all_nan_columns=all_nan, feature_names=names)

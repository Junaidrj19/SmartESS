"""Isolation Forest wrapper. Unsupervised; no labels in fit()."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import IsolationForest

from .config import AnomalyConfig


@dataclass
class IsolationForestDetector:
    config: AnomalyConfig
    model: IsolationForest
    threshold: float

    def score(self, x: np.ndarray) -> np.ndarray:
        # sklearn: lower decision_function => more anomalous. Invert so higher = more anomalous.
        return -self.model.decision_function(x)

    def predict_is_anomaly(self, scores: np.ndarray) -> np.ndarray:
        return scores >= self.threshold


def fit_isolation_forest(x_train: np.ndarray, config: AnomalyConfig) -> IsolationForestDetector:
    if x_train.ndim != 2 or x_train.shape[0] < 2:
        raise ValueError("training matrix must have at least 2 rows")
    model = IsolationForest(
        n_estimators=config.n_estimators,
        contamination=config.contamination,
        max_samples=config.max_samples,
        random_state=config.random_state,
        n_jobs=1,
    )
    model.fit(x_train)
    scores = -model.decision_function(x_train)
    threshold = float(np.quantile(scores, 1.0 - config.contamination))
    return IsolationForestDetector(config=config, model=model, threshold=threshold)

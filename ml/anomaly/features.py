"""Observation-feature matrix construction for M7.

Uses the M6 v1 observation feature registry. Does not use module-level
retrospective aggregates as model inputs.
"""

from __future__ import annotations

from typing import List

import pandas as pd

from ml.features.definitions import (
    FORBIDDEN_FEATURE_COLUMNS,
    OBSERVATION_IDENTIFIER_COLUMNS,
    create_v1_feature_set,
)

IDENTIFIER_COLUMNS = list(OBSERVATION_IDENTIFIER_COLUMNS)


def observation_model_feature_names() -> List[str]:
    return list(create_v1_feature_set().observation_feature_names())


def extract_feature_matrix(observation_features: pd.DataFrame) -> pd.DataFrame:
    leaked = set(observation_features.columns) & FORBIDDEN_FEATURE_COLUMNS
    if leaked:
        raise ValueError(f"Forbidden ground-truth/prediction columns in features: {sorted(leaked)}")
    names = observation_model_feature_names()
    missing = [name for name in names if name not in observation_features.columns]
    if missing:
        raise ValueError(f"Observation features missing v1 columns: {missing[:20]}")
    return observation_features.loc[:, names].copy()

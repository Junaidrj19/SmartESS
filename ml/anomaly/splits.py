"""Lot-level splits. Never split telemetry rows within a module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class LotSplit:
    train_lots: tuple[str, ...]
    test_lots: tuple[str, ...]
    train_modules: tuple[str, ...]
    test_modules: tuple[str, ...]


def lot_holdout_split(
    observation_features: pd.DataFrame,
    *,
    random_state: int,
    test_lot_fraction: float,
    min_train_lots: int = 1,
) -> LotSplit:
    if "lot_id" not in observation_features.columns or "module_id" not in observation_features.columns:
        raise ValueError("observation features must include lot_id and module_id")
    lots = tuple(sorted(observation_features["lot_id"].astype(str).unique()))
    if len(lots) < 2:
        raise ValueError("lot-level holdout requires at least 2 lots")
    n_test = max(1, int(round(len(lots) * test_lot_fraction)))
    n_test = min(n_test, len(lots) - min_train_lots)
    if n_test < 1:
        raise ValueError("cannot hold out a test lot while keeping min_train_lots")
    rng = np.random.default_rng(random_state)
    perm = rng.permutation(len(lots))
    test_idx = set(int(i) for i in perm[:n_test])
    test_lots = tuple(lots[i] for i in range(len(lots)) if i in test_idx)
    train_lots = tuple(lots[i] for i in range(len(lots)) if i not in test_idx)
    train_modules = tuple(
        sorted(observation_features.loc[observation_features["lot_id"].astype(str).isin(train_lots), "module_id"].astype(str).unique())
    )
    test_modules = tuple(
        sorted(observation_features.loc[observation_features["lot_id"].astype(str).isin(test_lots), "module_id"].astype(str).unique())
    )
    overlap = set(train_modules) & set(test_modules)
    if overlap:
        raise ValueError(f"module leakage across lot split: {sorted(overlap)}")
    return LotSplit(
        train_lots=train_lots,
        test_lots=test_lots,
        train_modules=train_modules,
        test_modules=test_modules,
    )


def mask_lots(df: pd.DataFrame, lots: Sequence[str]) -> pd.DataFrame:
    return df.loc[df["lot_id"].astype(str).isin([str(x) for x in lots])].copy()

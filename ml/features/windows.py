"""Window calculation utilities for causal trailing-window features."""

from __future__ import annotations

from typing import List

import numpy as np
import pandas as pd


def trailing_slope(values: np.ndarray) -> float:
    """Causal linear-regression slope on a trailing window. NaN if < 2 finite points."""

    y = np.asarray(values, dtype=float)
    finite = np.isfinite(y)
    if int(finite.sum()) < 2:
        return np.nan
    x = np.arange(len(y), dtype=float)[finite]
    y = y[finite]
    n = float(len(y))
    sx = float(x.sum())
    sy = float(y.sum())
    sxx = float((x * x).sum())
    sxy = float((x * y).sum())
    denom = n * sxx - sx * sx
    if denom == 0.0:
        return np.nan
    return (n * sxy - sx * sy) / denom


def trailing_mad(values: np.ndarray) -> float:
    """Median absolute deviation over a trailing window. NaN if < 2 finite points."""

    y = np.asarray(values, dtype=float)
    y = y[np.isfinite(y)]
    if len(y) < 2:
        return np.nan
    median = np.median(y)
    return float(np.median(np.abs(y - median)))


class WindowCalculator:
    """Calculates trailing (never centered) rolling statistics."""

    def __init__(self, window_sizes: List[int]):
        self.window_sizes = window_sizes

    def rolling_mean(self, series: pd.Series, window: int, min_periods: int = 1) -> pd.Series:
        return series.rolling(window=window, min_periods=min_periods, center=False).mean()

    def rolling_median(self, series: pd.Series, window: int, min_periods: int = 1) -> pd.Series:
        return series.rolling(window=window, min_periods=min_periods, center=False).median()

    def rolling_std(self, series: pd.Series, window: int, min_periods: int = 2) -> pd.Series:
        return series.rolling(window=window, min_periods=min_periods, center=False).std()

    def rolling_mad(self, series: pd.Series, window: int, min_periods: int = 2) -> pd.Series:
        return series.rolling(window=window, min_periods=min_periods, center=False).apply(
            trailing_mad, raw=True
        )

    def rolling_slope(self, series: pd.Series, window: int, min_periods: int = 2) -> pd.Series:
        return series.rolling(window=window, min_periods=min_periods, center=False).apply(
            trailing_slope, raw=True
        )

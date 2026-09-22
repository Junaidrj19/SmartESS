"""Feature transformation: telemetry → versioned, causal, leakage-safe features."""

from __future__ import annotations

import logging
from typing import Dict, Tuple

import numpy as np
import pandas as pd

from .config import DEFAULT_MODULE_PROFILE_PATH, FeatureConfig
from .definitions import (
    BASELINE_ROLLING_SIGNALS,
    ELECTRICAL_RAW_SIGNALS,
    FEATURE_VERSION,
    MODULE_IDENTIFIER_COLUMNS,
    OBSERVATION_IDENTIFIER_COLUMNS,
    THERMAL_RAW_SIGNALS,
    TREND_SIGNALS,
    FeatureSet,
    create_v1_feature_set,
)
from .temperature import TemperatureNormalizer
from .windows import trailing_mad, trailing_slope

logger = logging.getLogger(__name__)


class FeatureTransformer:
    """Transforms validated telemetry into observation- and module-level features."""

    def __init__(self, config: FeatureConfig):
        self.config = config
        if config.feature_version != FEATURE_VERSION:
            raise ValueError(f"Unsupported feature version {config.feature_version}")
        self.feature_set: FeatureSet = create_v1_feature_set(config.window_sizes)
        self.temp_normalizer = self._build_normalizer(config)

    def _build_normalizer(self, config: FeatureConfig) -> TemperatureNormalizer:
        if config.rds_on_ref_mohm is not None and config.rds_on_hot_mohm is not None:
            return TemperatureNormalizer(
                rds_on_ref_mohm=config.rds_on_ref_mohm,
                rds_on_hot_mohm=config.rds_on_hot_mohm,
                t_ref_C=config.t_ref_C,
                t_hot_C=config.t_hot_C,
            )
        profile_path = config.module_profile_path or DEFAULT_MODULE_PROFILE_PATH
        return TemperatureNormalizer.from_module_profile_path(
            profile_path,
            t_ref_C=config.t_ref_C,
            t_hot_C=config.t_hot_C,
        )

    def transform(self, telemetry_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Transform telemetry. Never reads ground truth. Never mutates the input frame."""

        logger.info("Starting feature transformation for %s telemetry records", len(telemetry_df))
        df = telemetry_df.copy()
        self._validate_telemetry_schema(df)
        df = df.sort_values(["module_id", "cycle_number"]).reset_index(drop=True)
        df["observation_index_within_module"] = df.groupby("module_id", sort=False).cumcount()

        observation_features = self._compute_observation_features(df)
        if self.config.compute_module_features:
            module_features = self._compute_module_features(observation_features)
        else:
            module_features = pd.DataFrame(columns=self.feature_set.module_parquet_columns())

        observation_features = observation_features.reindex(
            columns=self.feature_set.observation_parquet_columns()
        )
        if self.config.compute_module_features:
            module_features = module_features.reindex(columns=self.feature_set.module_parquet_columns())

        logger.info(
            "Feature transformation complete. observation=%s module=%s",
            observation_features.shape,
            module_features.shape,
        )
        return observation_features, module_features

    def _validate_telemetry_schema(self, df: pd.DataFrame) -> None:
        required = ["module_id", "cycle_number", "timestamp"]
        missing = [col for col in required if col not in df.columns]
        if missing:
            raise ValueError(f"Missing required telemetry columns: {missing}")
        if self.config.target_cycles is None or self.config.target_cycles <= 0:
            raise ValueError(
                "target_cycles must be configured in FeatureConfig for normalized_cycle_position. "
                "It is obtained from TestProfile.cycle_profile.target_cycles (known a priori). "
                "Cannot use max observed cycle as that would leak future information."
            )

    def _column_or_nan(self, df: pd.DataFrame, name: str) -> pd.Series:
        if name in df.columns:
            return df[name]
        return pd.Series(np.nan, index=df.index, dtype=float)

    def _compute_observation_features(self, df: pd.DataFrame) -> pd.DataFrame:
        feature_df = pd.DataFrame(index=df.index)
        for col in OBSERVATION_IDENTIFIER_COLUMNS:
            if col == "observation_index_within_module":
                feature_df[col] = df[col]
            elif col in df.columns:
                feature_df[col] = df[col]
            else:
                feature_df[col] = pd.Series([None] * len(df), index=df.index)

        feature_df = self._compute_temporal_features(feature_df, df)
        feature_df = self._compute_electrical_features(feature_df, df)
        feature_df = self._compute_thermal_features(feature_df, df)
        baseline_df = self._compute_baselines(df)
        feature_df = self._compute_baseline_relative_features(feature_df, df, baseline_df)
        feature_df = self._compute_rolling_features(feature_df, df)
        feature_df = self._compute_trend_features(feature_df, df)
        return feature_df

    def _compute_temporal_features(self, feature_df: pd.DataFrame, telemetry_df: pd.DataFrame) -> pd.DataFrame:
        target_cycles = int(self.config.target_cycles)  # validated earlier
        feature_df["normalized_cycle_position"] = telemetry_df["cycle_number"] / target_cycles

        timestamp = pd.to_datetime(telemetry_df["timestamp"], utc=True)
        first_timestamp = timestamp.groupby(telemetry_df["module_id"], sort=False).transform("first")
        feature_df["elapsed_time"] = (timestamp - first_timestamp).dt.total_seconds()
        feature_df["observation_index"] = telemetry_df["observation_index_within_module"]
        feature_df["cycle_delta"] = telemetry_df.groupby("module_id", sort=False)["cycle_number"].diff()
        return feature_df

    def _compute_electrical_features(self, feature_df: pd.DataFrame, telemetry_df: pd.DataFrame) -> pd.DataFrame:
        for signal in ELECTRICAL_RAW_SIGNALS:
            feature_df[signal] = self._column_or_nan(telemetry_df, signal)
        return feature_df

    def _compute_thermal_features(self, feature_df: pd.DataFrame, telemetry_df: pd.DataFrame) -> pd.DataFrame:
        for signal in THERMAL_RAW_SIGNALS:
            feature_df[signal] = self._column_or_nan(telemetry_df, signal)
        feature_df["delta_Tj"] = self._column_or_nan(telemetry_df, "delta_Tj")
        tj = self._column_or_nan(telemetry_df, "Tj")
        tc = self._column_or_nan(telemetry_df, "Tc")
        feature_df["Tj_minus_Tc"] = tj - tc
        rds = self._column_or_nan(telemetry_df, "RDS_on")
        feature_df["temperature_normalized_RDS_on"] = self.temp_normalizer.normalize(rds, tj)
        return feature_df

    def _baseline_size(self, n_obs: int) -> int:
        return min(
            max(self.config.baseline_min_cycles, int(n_obs * self.config.baseline_window_fraction)),
            n_obs,
        )

    def _compute_baselines(self, telemetry_df: pd.DataFrame) -> pd.DataFrame:
        parts = []
        for _, group in telemetry_df.groupby("module_id", sort=False):
            group_sorted = group.sort_values("cycle_number")
            size = self._baseline_size(len(group_sorted))
            parts.append(group_sorted.head(size))
        if not parts:
            return telemetry_df.iloc[0:0]
        return pd.concat(parts, ignore_index=True)

    def _compute_baseline_relative_features(
        self,
        feature_df: pd.DataFrame,
        telemetry_df: pd.DataFrame,
        baseline_telemetry_df: pd.DataFrame,
    ) -> pd.DataFrame:
        module_ids = telemetry_df["module_id"]
        for signal in BASELINE_ROLLING_SIGNALS:
            values = self._column_or_nan(telemetry_df, signal)
            if signal in baseline_telemetry_df.columns:
                grouped_baseline = baseline_telemetry_df.groupby("module_id", sort=False)[signal]
                baseline_median = grouped_baseline.median()
                baseline_mad = grouped_baseline.agg(lambda x: trailing_mad(np.asarray(x, dtype=float)))
            else:
                baseline_median = pd.Series(dtype=float)
                baseline_mad = pd.Series(dtype=float)

            median_series = module_ids.map(baseline_median).astype(float)
            mad_series = module_ids.map(baseline_mad).astype(float)
            feature_df[f"{signal}_baseline_median"] = median_series
            feature_df[f"{signal}_delta_from_baseline"] = values - median_series
            baseline_safe = median_series.replace(0, np.nan)
            feature_df[f"{signal}_pct_change_from_baseline"] = (values - median_series) / baseline_safe * 100
            mad_safe = mad_series.replace(0, np.nan)
            feature_df[f"{signal}_robust_normalized_deviation"] = (values - median_series) / (1.4826 * mad_safe)
        return feature_df

    def _grouped_rolling(self, telemetry_df: pd.DataFrame, signal: str, window: int, how: str) -> pd.Series:
        source = self._column_or_nan(telemetry_df, signal)
        grouped = source.groupby(telemetry_df["module_id"], sort=False)
        if how == "mean":
            rolled = grouped.rolling(window=window, min_periods=1, center=False).mean()
        elif how == "median":
            rolled = grouped.rolling(window=window, min_periods=1, center=False).median()
        elif how == "std":
            rolled = grouped.rolling(window=window, min_periods=2, center=False).std()
        elif how == "mad":
            rolled = grouped.rolling(window=window, min_periods=2, center=False).apply(trailing_mad, raw=True)
        else:
            raise ValueError(how)
        return rolled.reset_index(level=0, drop=True)

    def _compute_rolling_features(self, feature_df: pd.DataFrame, telemetry_df: pd.DataFrame) -> pd.DataFrame:
        rolling_features: Dict[str, np.ndarray] = {}
        for signal in BASELINE_ROLLING_SIGNALS:
            for window in self.config.window_sizes:
                rolling_features[f"{signal}_rolling_mean_{window}"] = self._grouped_rolling(
                    telemetry_df, signal, window, "mean"
                ).to_numpy()
                rolling_features[f"{signal}_rolling_median_{window}"] = self._grouped_rolling(
                    telemetry_df, signal, window, "median"
                ).to_numpy()
                rolling_features[f"{signal}_rolling_std_{window}"] = self._grouped_rolling(
                    telemetry_df, signal, window, "std"
                ).to_numpy()
                rolling_features[f"{signal}_rolling_mad_{window}"] = self._grouped_rolling(
                    telemetry_df, signal, window, "mad"
                ).to_numpy()
        if rolling_features:
            feature_df = pd.concat(
                [feature_df, pd.DataFrame(rolling_features, index=feature_df.index)],
                axis=1,
            )
        return feature_df

    def _compute_trend_features(self, feature_df: pd.DataFrame, telemetry_df: pd.DataFrame) -> pd.DataFrame:
        window = max(self.config.window_sizes) if self.config.window_sizes else 20
        for signal in TREND_SIGNALS:
            source = self._column_or_nan(telemetry_df, signal)
            rolled = (
                source.groupby(telemetry_df["module_id"], sort=False)
                .rolling(window=window, min_periods=2, center=False)
                .apply(trailing_slope, raw=True)
                .reset_index(level=0, drop=True)
            )
            feature_df[f"{signal}_trend"] = rolled.to_numpy()
        return feature_df

    def _compute_module_features(self, observation_features: pd.DataFrame) -> pd.DataFrame:
        if observation_features.empty:
            return pd.DataFrame(columns=self.feature_set.module_parquet_columns())

        groups = observation_features.groupby("module_id", sort=False)
        ids = observation_features[list(MODULE_IDENTIFIER_COLUMNS)].drop_duplicates("module_id").set_index("module_id")

        numeric_features = self.feature_set.observation_feature_names()
        module_feature_dict: Dict[str, pd.Series] = {}
        for col in numeric_features:
            grouped = observation_features.groupby("module_id", sort=False)[col]
            module_feature_dict[f"{col}_mean"] = grouped.mean()
            module_feature_dict[f"{col}_median"] = grouped.median()
            module_feature_dict[f"{col}_std"] = grouped.std()
            col_min = grouped.min()
            col_max = grouped.max()
            module_feature_dict[f"{col}_min"] = col_min
            module_feature_dict[f"{col}_max"] = col_max
            module_feature_dict[f"{col}_range"] = col_max - col_min

        module_feature_dict["observation_count"] = groups.size()
        timestamp = pd.to_datetime(observation_features["timestamp"], utc=True)
        ts_grouped = timestamp.groupby(observation_features["module_id"], sort=False)
        first_ts = ts_grouped.min()
        last_ts = ts_grouped.max()
        module_feature_dict["first_timestamp"] = first_ts
        module_feature_dict["last_timestamp"] = last_ts
        module_feature_dict["time_span_seconds"] = (last_ts - first_ts).dt.total_seconds()
        cycle_grouped = observation_features.groupby("module_id", sort=False)["cycle_number"]
        first_cycle = cycle_grouped.min()
        last_cycle = cycle_grouped.max()
        module_feature_dict["first_cycle"] = first_cycle
        module_feature_dict["last_cycle"] = last_cycle
        module_feature_dict["cycle_span"] = last_cycle - first_cycle

        agg_df = pd.DataFrame(module_feature_dict, index=ids.index)
        module_features = pd.concat([ids, agg_df], axis=1).reset_index()
        return module_features.reindex(columns=self.feature_set.module_parquet_columns())

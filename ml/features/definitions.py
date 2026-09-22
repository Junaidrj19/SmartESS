"""Authoritative v1 feature registry.

Every schema, count, metadata field, and validator expectation is derived from
this module. Do not maintain independent feature counts elsewhere.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
import re


FEATURE_VERSION = "v1"

WINDOW_SIZES_V1: Tuple[int, ...] = (5, 10, 20)

OBSERVATION_IDENTIFIER_COLUMNS: Tuple[str, ...] = (
    "module_id",
    "test_id",
    "lot_id",
    "dataset_id",
    "timestamp",
    "cycle_number",
    "observation_index_within_module",
)

MODULE_IDENTIFIER_COLUMNS: Tuple[str, ...] = (
    "module_id",
    "test_id",
    "lot_id",
    "dataset_id",
)

MODULE_METADATA_COLUMNS: Tuple[str, ...] = (
    "observation_count",
    "first_timestamp",
    "last_timestamp",
    "time_span_seconds",
    "first_cycle",
    "last_cycle",
    "cycle_span",
)

MODULE_AGGREGATE_STATS: Tuple[str, ...] = (
    "mean",
    "median",
    "std",
    "min",
    "max",
    "range",
)

ROLLING_STATS: Tuple[str, ...] = ("mean", "median", "std", "mad")

BASELINE_KINDS: Tuple[str, ...] = (
    "baseline_median",
    "delta_from_baseline",
    "pct_change_from_baseline",
    "robust_normalized_deviation",
)

ELECTRICAL_RAW_SIGNALS: Tuple[str, ...] = (
    "RDS_on",
    "VTH",
    "IGSS",
    "IDSS",
    "VDS_on",
    "VF",
    "VDS",
    "VGS",
    "ID",
    "electrical_power",
)

THERMAL_RAW_SIGNALS: Tuple[str, ...] = ("Tj", "Tc", "Ta")

# v1 baseline/rolling set is definition-driven and excludes VF.
# VF remains an electrical passthrough (raw measurement) only.
BASELINE_ROLLING_SIGNALS: Tuple[str, ...] = (
    "RDS_on",
    "VTH",
    "IGSS",
    "IDSS",
    "VDS_on",
    "electrical_power",
    "Tj",
    "Tc",
)

TREND_SIGNALS: Tuple[str, ...] = ("RDS_on", "VTH", "IGSS", "IDSS", "Tj")

VF_BASELINE_ROLLING_POLICY = (
    "VF is a v1 electrical passthrough feature only. It is not part of the v1 "
    "baseline or rolling signal set. Presence, absence, or all-NaN VF telemetry "
    "must not change the v1 feature schema."
)

FORBIDDEN_FEATURE_COLUMNS: frozenset[str] = frozenset(
    {
        "anomaly_score",
        "anomaly_scores",
        "prediction",
        "predictions",
        "predicted_failure",
        "failure_probability",
        "failure_mechanism",
        "hypothesis",
        "investigation_result",
        "investigation",
        "investigation_id",
        "degradation_state",
        "ground_truth",
        "model_prediction",
        "module_profile",
        "test_profile",
        "mechanism",
        "health_state",
        "onset_cycle",
        "stage",
        "severity",
        "rate_scale",
        "terminal_cycle",
        "mechanism_model",
    }
)


class FeatureLevel(Enum):
    OBSERVATION = "observation"
    MODULE = "module"


class FeatureType(Enum):
    TEMPORAL = "temporal"
    ELECTRICAL = "electrical"
    THERMAL = "thermal"
    BASELINE_RELATIVE = "baseline_relative"
    ROLLING = "rolling"
    TREND = "trend"


@dataclass
class FeatureDefinition:
    """One feature definition in the authoritative registry."""

    name: str
    feature_type: FeatureType
    feature_level: FeatureLevel
    description: str
    formula: str
    version: str = FEATURE_VERSION
    source_parameters: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    is_baseline_dependent: bool = False
    requires_temperature: bool = False
    window_sizes: List[int] = field(default_factory=list)
    is_causal: bool = True
    is_retrospective: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Feature name cannot be empty")
        if not self.formula:
            raise ValueError("Feature formula cannot be empty")
        if not re.match(r"^[a-zA-Z0-9_]+$", self.name):
            raise ValueError("Feature name must contain only alphanumeric characters and underscores")
        if self.feature_level is FeatureLevel.OBSERVATION and self.is_retrospective:
            raise ValueError(f"Observation feature {self.name} cannot be retrospective")
        if self.feature_level is FeatureLevel.OBSERVATION and not self.is_causal:
            raise ValueError(
                f"Observation feature {self.name} must be causal in {FEATURE_VERSION}; "
                "non-causal observation features require a new feature version"
            )
        if self.feature_level is FeatureLevel.MODULE and not self.is_retrospective:
            raise ValueError(f"Module feature {self.name} must be retrospective")
        if not self.source_parameters and self.dependencies:
            self.source_parameters = list(self.dependencies)

    @property
    def expands_over_windows(self) -> bool:
        return bool(self.window_sizes)

    def expand_names(self) -> List[str]:
        if self.window_sizes:
            return [f"{self.name}_{w}" for w in self.window_sizes]
        return [self.name]


@dataclass
class FeatureSet:
    """Collection of feature definitions for a specific version."""

    version: str
    features: Dict[str, FeatureDefinition] = field(default_factory=dict)
    window_sizes: List[int] = field(default_factory=lambda: list(WINDOW_SIZES_V1))

    def add_feature(self, feature: FeatureDefinition) -> None:
        if feature.version != self.version:
            raise ValueError(f"Feature version {feature.version} does not match set version {self.version}")
        if feature.name in self.features:
            raise ValueError(f"Duplicate feature definition: {feature.name}")
        self.features[feature.name] = feature

    def get_feature(self, name: str) -> Optional[FeatureDefinition]:
        return self.features.get(name)

    def get_features_by_level(self, level: FeatureLevel) -> List[FeatureDefinition]:
        return [f for f in self.features.values() if f.feature_level == level]

    def get_features_by_type(self, feature_type: FeatureType) -> List[FeatureDefinition]:
        return [f for f in self.features.values() if f.feature_type == feature_type]

    def observation_definitions(self) -> List[FeatureDefinition]:
        return self.get_features_by_level(FeatureLevel.OBSERVATION)

    def observation_feature_names(self) -> List[str]:
        names: List[str] = []
        for feat in self.observation_definitions():
            names.extend(feat.expand_names())
        return names

    def observation_parquet_columns(self) -> List[str]:
        return list(OBSERVATION_IDENTIFIER_COLUMNS) + self.observation_feature_names()

    def module_aggregate_columns(self) -> List[str]:
        columns: List[str] = []
        for feature_name in self.observation_feature_names():
            for stat in MODULE_AGGREGATE_STATS:
                columns.append(f"{feature_name}_{stat}")
        return columns

    def module_parquet_columns(self) -> List[str]:
        return (
            list(MODULE_IDENTIFIER_COLUMNS)
            + self.module_aggregate_columns()
            + list(MODULE_METADATA_COLUMNS)
        )

    def count_definitions(self) -> int:
        return len(self.features)

    def count_observation_features(self) -> int:
        return len(self.observation_feature_names())

    def count_observation_parquet_columns(self) -> int:
        return len(self.observation_parquet_columns())

    def count_module_parquet_columns(self) -> int:
        return len(self.module_parquet_columns())

    def category_feature_counts(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for feat in self.observation_definitions():
            key = feat.feature_type.value
            counts[key] = counts.get(key, 0) + len(feat.expand_names())
        return counts

    def registry_records(self) -> List[Dict[str, object]]:
        records: List[Dict[str, object]] = []
        for feat in self.features.values():
            records.append(
                {
                    "name": feat.name,
                    "family": feat.feature_type.value,
                    "level": feat.feature_level.value,
                    "source_parameters": list(feat.source_parameters),
                    "formula": feat.formula,
                    "expands_over_windows": feat.expands_over_windows,
                    "window_sizes": list(feat.window_sizes) if feat.window_sizes else [],
                    "expanded_names": feat.expand_names(),
                    "is_causal": feat.is_causal,
                    "is_retrospective": feat.is_retrospective,
                    "version": feat.version,
                    "description": feat.description,
                    "dependencies": list(feat.dependencies),
                    "is_baseline_dependent": feat.is_baseline_dependent,
                    "requires_temperature": feat.requires_temperature,
                }
            )
        return records


def _temporal_features() -> List[FeatureDefinition]:
    return [
        FeatureDefinition(
            name="normalized_cycle_position",
            feature_type=FeatureType.TEMPORAL,
            feature_level=FeatureLevel.OBSERVATION,
            description="Normalized position within the declared test using a priori target_cycles",
            formula="cycle_number / target_cycles",
            source_parameters=["cycle_number"],
            is_causal=True,
        ),
        FeatureDefinition(
            name="elapsed_time",
            feature_type=FeatureType.TEMPORAL,
            feature_level=FeatureLevel.OBSERVATION,
            description="Elapsed seconds since the first observation of the module in cycle order",
            formula="timestamp - first_timestamp_by_cycle_order",
            source_parameters=["timestamp"],
            is_causal=True,
        ),
        FeatureDefinition(
            name="observation_index",
            feature_type=FeatureType.TEMPORAL,
            feature_level=FeatureLevel.OBSERVATION,
            description="0-based observation index within the module after cycle ordering",
            formula="observation_index_within_module",
            source_parameters=["cycle_number"],
            is_causal=True,
        ),
        FeatureDefinition(
            name="cycle_delta",
            feature_type=FeatureType.TEMPORAL,
            feature_level=FeatureLevel.OBSERVATION,
            description="Difference in cycle number from the previous observation",
            formula="cycle_number - previous_cycle_number",
            source_parameters=["cycle_number"],
            is_causal=True,
        ),
    ]


def _electrical_features() -> List[FeatureDefinition]:
    features: List[FeatureDefinition] = []
    for signal in ELECTRICAL_RAW_SIGNALS:
        features.append(
            FeatureDefinition(
                name=signal,
                feature_type=FeatureType.ELECTRICAL,
                feature_level=FeatureLevel.OBSERVATION,
                description=f"Raw {signal} measurement; missing values remain missing",
                formula=signal,
                source_parameters=[signal],
                requires_temperature=(signal == "RDS_on"),
                is_causal=True,
            )
        )
    return features


def _thermal_features() -> List[FeatureDefinition]:
    features: List[FeatureDefinition] = [
        FeatureDefinition(
            name=signal,
            feature_type=FeatureType.THERMAL,
            feature_level=FeatureLevel.OBSERVATION,
            description=f"Raw {signal} measurement; missing values remain missing",
            formula=signal,
            source_parameters=[signal],
            is_causal=True,
        )
        for signal in THERMAL_RAW_SIGNALS
    ]
    features.extend(
        [
            FeatureDefinition(
                name="delta_Tj",
                feature_type=FeatureType.THERMAL,
                feature_level=FeatureLevel.OBSERVATION,
                description="Declared junction temperature delta for the cycle",
                formula="delta_Tj",
                source_parameters=["delta_Tj"],
                is_causal=True,
            ),
            FeatureDefinition(
                name="Tj_minus_Tc",
                feature_type=FeatureType.THERMAL,
                feature_level=FeatureLevel.OBSERVATION,
                description="Junction-to-case temperature difference from current observations only",
                formula="Tj - Tc",
                source_parameters=["Tj", "Tc"],
                is_causal=True,
            ),
            FeatureDefinition(
                name="temperature_normalized_RDS_on",
                feature_type=FeatureType.THERMAL,
                feature_level=FeatureLevel.OBSERVATION,
                description="RDS_on normalized to T_ref using the M4 linear type curve",
                formula="RDS_on / (R_type(Tj) / R_type(T_ref))",
                source_parameters=["RDS_on", "Tj"],
                dependencies=["RDS_on", "Tj"],
                requires_temperature=True,
                is_causal=True,
            ),
        ]
    )
    return features


def _baseline_features() -> List[FeatureDefinition]:
    features: List[FeatureDefinition] = []
    formulas = {
        "baseline_median": "median({signal}) over early-life baseline window",
        "delta_from_baseline": "{signal} - {signal}_baseline_median",
        "pct_change_from_baseline": "({signal} - {signal}_baseline_median) / {signal}_baseline_median * 100",
        "robust_normalized_deviation": "({signal} - {signal}_baseline_median) / (1.4826 * MAD({signal}) over baseline window)",
    }
    for signal in BASELINE_ROLLING_SIGNALS:
        for kind in BASELINE_KINDS:
            features.append(
                FeatureDefinition(
                    name=f"{signal}_{kind}",
                    feature_type=FeatureType.BASELINE_RELATIVE,
                    feature_level=FeatureLevel.OBSERVATION,
                    description=f"{kind.replace('_', ' ')} for {signal}",
                    formula=formulas[kind].format(signal=signal),
                    source_parameters=[signal],
                    dependencies=[signal],
                    is_baseline_dependent=True,
                    is_causal=True,
                )
            )
    return features


def _rolling_features(window_sizes: Sequence[int]) -> List[FeatureDefinition]:
    features: List[FeatureDefinition] = []
    for signal in BASELINE_ROLLING_SIGNALS:
        for stat in ROLLING_STATS:
            features.append(
                FeatureDefinition(
                    name=f"{signal}_rolling_{stat}",
                    feature_type=FeatureType.ROLLING,
                    feature_level=FeatureLevel.OBSERVATION,
                    description=f"Trailing rolling {stat} of {signal}",
                    formula=f"trailing_rolling_{stat}({signal}, window)",
                    source_parameters=[signal],
                    dependencies=[signal],
                    window_sizes=list(window_sizes),
                    is_causal=True,
                )
            )
    return features


def _trend_features() -> List[FeatureDefinition]:
    return [
        FeatureDefinition(
            name=f"{signal}_trend",
            feature_type=FeatureType.TREND,
            feature_level=FeatureLevel.OBSERVATION,
            description=f"Trailing linear-regression slope of {signal} over max(window_sizes)",
            formula=f"trailing_linear_regression_slope({signal})",
            source_parameters=[signal],
            dependencies=[signal],
            is_causal=True,
        )
        for signal in TREND_SIGNALS
    ]


def create_v1_feature_set(window_sizes: Optional[Iterable[int]] = None) -> FeatureSet:
    """Create the v1 feature set. Schema does not depend on dataset missingness."""

    sizes = list(WINDOW_SIZES_V1 if window_sizes is None else window_sizes)
    feature_set = FeatureSet(version=FEATURE_VERSION, window_sizes=sizes)
    for definition in (
        *_temporal_features(),
        *_electrical_features(),
        *_thermal_features(),
        *_baseline_features(),
        *_rolling_features(sizes),
        *_trend_features(),
    ):
        feature_set.add_feature(definition)
    return feature_set


V1_FEATURE_SET = create_v1_feature_set()
V1_OBSERVATION_FEATURE_COUNT = V1_FEATURE_SET.count_observation_features()
V1_OBSERVATION_COLUMN_COUNT = V1_FEATURE_SET.count_observation_parquet_columns()
V1_MODULE_COLUMN_COUNT = V1_FEATURE_SET.count_module_parquet_columns()
V1_MODULE_AGGREGATE_COUNT = len(V1_FEATURE_SET.module_aggregate_columns())
V1_CATEGORY_COUNTS = V1_FEATURE_SET.category_feature_counts()

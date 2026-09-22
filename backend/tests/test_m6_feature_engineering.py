"""Tests for M6 feature engineering — registry-driven, causal, leakage-safe v1."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.features import FeatureConfig, FeatureTransformer, FeatureValidator, TemperatureNormalizer
from ml.features.definitions import (
    BASELINE_ROLLING_SIGNALS,
    FEATURE_VERSION,
    FORBIDDEN_FEATURE_COLUMNS,
    MODULE_IDENTIFIER_COLUMNS,
    OBSERVATION_IDENTIFIER_COLUMNS,
    V1_CATEGORY_COUNTS,
    V1_FEATURE_SET,
    V1_MODULE_COLUMN_COUNT,
    V1_OBSERVATION_COLUMN_COUNT,
    V1_OBSERVATION_FEATURE_COUNT,
    FeatureLevel,
    create_v1_feature_set,
)
from ml.features.pipeline import BlockedDatasetError, build_features_from_dataset, load_validation_metadata
from ml.generators.synthetic.anchors import TypeAnchors
from ml.generators.synthetic.temperature import rds_type_ratio


REFERENCE_PROFILE = Path("examples/module-profiles/sic-reference-module.json")


def _sample_telemetry(*, n_modules: int = 4, n_obs: int = 30, include_vf: bool = True, vf_values=None) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    rows = []
    for module_i in range(n_modules):
        for obs_i in range(n_obs):
            cycle = obs_i * 10
            temp = 25.0 + obs_i
            rds = 4.5 * (1.0 + 0.0048 * (temp - 25.0)) + module_i * 0.01
            vf = np.nan if vf_values is None and not include_vf else (
                vf_values if np.isscalar(vf_values) else (3.2 + 0.01 * obs_i if include_vf else np.nan)
            )
            if vf_values is None and include_vf:
                vf = 3.2 + 0.01 * obs_i
            rows.append(
                {
                    "module_id": f"mod_{module_i:03d}",
                    "test_id": "test_001",
                    "lot_id": f"lot_{module_i // 2:02d}",
                    "dataset_id": "test_dataset",
                    "timestamp": pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(hours=cycle),
                    "cycle_number": cycle,
                    "RDS_on": rds + float(rng.normal(0, 1e-4)),
                    "VTH": 2.8 - 0.002 * (temp - 25.0),
                    "IGSS": 1e-3,
                    "IDSS": 1e-2,
                    "VDS_on": 1.8,
                    "VF": vf,
                    "Tj": temp,
                    "Tc": temp - 5.0,
                    "Ta": 25.0,
                    "delta_Tj": 80.0,
                    "ID": 10.0,
                    "VDS": 400.0,
                    "VGS": 15.0,
                    "electrical_power": 4000.0,
                }
            )
    df = pd.DataFrame(rows)
    if not include_vf:
        df = df.drop(columns=["VF"])
    return df


@pytest.fixture
def sample_telemetry() -> pd.DataFrame:
    return _sample_telemetry()


class TestRegistryContract:
    def test_v1_counts_are_derived_from_registry(self):
        feature_set = create_v1_feature_set()
        assert feature_set.count_observation_features() == 153
        assert feature_set.count_observation_parquet_columns() == 160
        assert len(feature_set.module_aggregate_columns()) == 918
        assert feature_set.count_module_parquet_columns() == 929
        assert V1_OBSERVATION_FEATURE_COUNT == 153
        assert V1_OBSERVATION_COLUMN_COUNT == 160
        assert V1_MODULE_COLUMN_COUNT == 929
        assert V1_CATEGORY_COUNTS == {
            "temporal": 4,
            "electrical": 10,
            "thermal": 6,
            "baseline_relative": 32,
            "rolling": 96,
            "trend": 5,
        }
        assert len(OBSERVATION_IDENTIFIER_COLUMNS) == 7
        assert len(MODULE_IDENTIFIER_COLUMNS) == 4
        assert 4 + 10 + 6 + 32 + 96 + 5 == 153
        assert 153 + 7 == 160
        assert 153 * 6 == 918
        assert 918 + 7 + 4 == 929

    def test_vf_is_electrical_passthrough_only(self):
        names = V1_FEATURE_SET.observation_feature_names()
        assert "VF" in names
        assert not any(name.startswith("VF_baseline") or name.startswith("VF_rolling") for name in names)
        assert "VF" not in BASELINE_ROLLING_SIGNALS
        assert len(BASELINE_ROLLING_SIGNALS) == 8
        assert BASELINE_ROLLING_SIGNALS == (
            "RDS_on",
            "VTH",
            "IGSS",
            "IDSS",
            "VDS_on",
            "electrical_power",
            "Tj",
            "Tc",
        )

    def test_observation_features_are_causal(self):
        for feat in V1_FEATURE_SET.observation_definitions():
            assert feat.is_causal is True
            assert feat.is_retrospective is False
            assert feat.version == FEATURE_VERSION

    def test_non_causal_observation_feature_rejected(self):
        from ml.features.definitions import FeatureDefinition, FeatureType

        with pytest.raises(ValueError, match="must be causal"):
            FeatureDefinition(
                name="leaky",
                feature_type=FeatureType.TREND,
                feature_level=FeatureLevel.OBSERVATION,
                description="future looking",
                formula="centered window",
                is_causal=False,
            )


class TestFeatureEngineering:
    def test_feature_transformer_initialization(self):
        config = FeatureConfig(target_cycles=100)
        transformer = FeatureTransformer(config)
        assert transformer.config.feature_version == "v1"
        assert transformer.feature_set.version == "v1"

    def test_rejects_non_v1_version(self):
        with pytest.raises(ValueError, match="v1"):
            FeatureConfig(feature_version="v2", target_cycles=100)

    def test_temporal_features(self, sample_telemetry):
        transformer = FeatureTransformer(FeatureConfig(target_cycles=100))
        observation_features, _ = transformer.transform(sample_telemetry)
        assert "normalized_cycle_position" in observation_features.columns
        assert (observation_features["normalized_cycle_position"] >= 0).all()
        first_obs = observation_features.groupby("module_id")["observation_index"].idxmin()
        assert observation_features.loc[first_obs, "cycle_delta"].isna().all()
        assert observation_features["observation_index"].min() == 0

    def test_target_cycles_required(self, sample_telemetry):
        config = FeatureConfig(target_cycles=100)
        transformer = FeatureTransformer(config)
        transformer.config.target_cycles = None
        with pytest.raises(ValueError, match="target_cycles"):
            transformer.transform(sample_telemetry)

    def test_normalized_cycle_position_uses_target_cycles(self, sample_telemetry):
        target_cycles = 500
        observation_features, _ = FeatureTransformer(FeatureConfig(target_cycles=target_cycles)).transform(
            sample_telemetry
        )
        cycle_0 = observation_features[observation_features["cycle_number"] == 0]
        assert (cycle_0["normalized_cycle_position"] == 0).all()
        max_cycle = observation_features["cycle_number"].max()
        assert observation_features["normalized_cycle_position"].max() == pytest.approx(max_cycle / target_cycles)

    def test_normalized_cycle_does_not_use_max_observed(self, sample_telemetry):
        target_cycles = 200
        full, _ = FeatureTransformer(FeatureConfig(target_cycles=target_cycles)).transform(sample_telemetry)
        truncated, _ = FeatureTransformer(FeatureConfig(target_cycles=target_cycles)).transform(
            sample_telemetry[sample_telemetry["cycle_number"] <= 50]
        )
        merged = full.merge(truncated, on=["module_id", "cycle_number"], suffixes=("_a", "_b"))
        assert np.allclose(merged["normalized_cycle_position_a"], merged["normalized_cycle_position_b"])

    def test_electrical_and_thermal_passthrough(self, sample_telemetry):
        obs, _ = FeatureTransformer(FeatureConfig(target_cycles=100)).transform(sample_telemetry)
        for col in ["RDS_on", "VTH", "VF", "Tj", "Tc", "Ta", "delta_Tj", "Tj_minus_Tc", "temperature_normalized_RDS_on"]:
            assert col in obs.columns
            assert not obs[col].isna().all()

    def test_baseline_relative_features(self, sample_telemetry):
        obs, _ = FeatureTransformer(FeatureConfig(target_cycles=100, baseline_window_fraction=0.3)).transform(
            sample_telemetry
        )
        for signal in ["RDS_on", "VTH"]:
            assert f"{signal}_baseline_median" in obs.columns
            assert f"{signal}_delta_from_baseline" in obs.columns
            assert f"{signal}_pct_change_from_baseline" in obs.columns
            assert f"{signal}_robust_normalized_deviation" in obs.columns

    def test_window_features(self, sample_telemetry):
        obs, _ = FeatureTransformer(FeatureConfig(target_cycles=100, window_sizes=[3, 5])).transform(sample_telemetry)
        for signal in ["RDS_on", "VTH"]:
            for window in [3, 5]:
                assert f"{signal}_rolling_mean_{window}" in obs.columns
                assert f"{signal}_rolling_std_{window}" in obs.columns
        first = obs.groupby("module_id").head(1)
        assert first["RDS_on_rolling_std_3"].isna().all()

    def test_trend_features_trailing(self, sample_telemetry):
        obs, _ = FeatureTransformer(FeatureConfig(target_cycles=100)).transform(sample_telemetry)
        for signal in ["RDS_on", "VTH"]:
            assert f"{signal}_trend" in obs.columns
        first = obs.groupby("module_id").head(1)
        assert first["RDS_on_trend"].isna().all()
        later = obs.groupby("module_id").tail(5)
        assert later["RDS_on_trend"].notna().all()

    def test_module_features(self, sample_telemetry):
        obs, module_features = FeatureTransformer(FeatureConfig(target_cycles=100)).transform(sample_telemetry)
        assert len(module_features) == sample_telemetry["module_id"].nunique()
        assert len(module_features.columns) == 929
        counts = sample_telemetry.groupby("module_id").size()
        for _, row in module_features.iterrows():
            assert row["observation_count"] == counts[row["module_id"]]

    def test_feature_validation_passes(self, sample_telemetry):
        obs, mod = FeatureTransformer(FeatureConfig(target_cycles=100)).transform(sample_telemetry)
        is_valid, errors = FeatureValidator(create_v1_feature_set()).validate_features(obs, mod, "test_dataset")
        assert is_valid, errors

    def test_no_forbidden_columns(self, sample_telemetry):
        obs, mod = FeatureTransformer(FeatureConfig(target_cycles=100)).transform(sample_telemetry)
        assert set(obs.columns) & FORBIDDEN_FEATURE_COLUMNS == set()
        assert set(mod.columns) & FORBIDDEN_FEATURE_COLUMNS == set()

    def test_schema_matches_registry(self, sample_telemetry):
        obs, mod = FeatureTransformer(FeatureConfig(target_cycles=100)).transform(sample_telemetry)
        feature_set = create_v1_feature_set()
        assert list(obs.columns) == feature_set.observation_parquet_columns()
        assert list(mod.columns) == feature_set.module_parquet_columns()
        assert len(obs.columns) == 160
        assert len([c for c in obs.columns if c not in OBSERVATION_IDENTIFIER_COLUMNS]) == 153

    def test_end_to_end_pipeline(self, sample_telemetry):
        obs, mod = FeatureTransformer(FeatureConfig(target_cycles=100)).transform(sample_telemetry)
        assert len(obs) == len(sample_telemetry)
        assert len(mod) == sample_telemetry["module_id"].nunique()


class TestTemperatureNormalization:
    def test_loaded_from_module_profile(self):
        normalizer = TemperatureNormalizer.from_module_profile_path(REFERENCE_PROFILE, t_ref_C=25.0, t_hot_C=150.0)
        assert normalizer.rds_on_ref_mohm == 4.5
        assert normalizer.rds_on_hot_mohm == 7.2
        assert normalizer.t_ref_C == 25.0
        assert normalizer.t_hot_C == 150.0

    def test_matches_m4_rds_type_ratio(self):
        normalizer = TemperatureNormalizer.from_module_profile_path(REFERENCE_PROFILE, t_ref_C=25.0, t_hot_C=150.0)
        anchors = TypeAnchors(
            module_profile_id="x",
            test_id="t",
            rds_ref_mohm=4.5,
            rds_hot_mohm=7.2,
            t_ref_C=25.0,
            t_hot_C=150.0,
            vth_ref_V=2.8,
            igss_base_uA=1.0,
            idss_base_uA=1.0,
            rth_jc_C_per_W=0.3,
            vds_V=400.0,
            id_A=10.0,
            vgs_on_V=15.0,
            tj_min_C=25.0,
            tj_max_C=150.0,
            delta_tj_C=125.0,
            tc_min_C=None,
            tc_max_C=None,
            ta_C=25.0,
            target_cycles=100,
            cycle_duration_s=2.0,
            heating_duration_s=1.0,
            cooling_duration_s=1.0,
            switching_frequency_Hz=None,
        )
        for tj in [25.0, 87.5, 125.0, 150.0]:
            assert normalizer.r_type_ratio(tj) == pytest.approx(float(rds_type_ratio(np.array([tj]), anchors)[0]))

    def test_anchor_and_intermediate_points(self):
        normalizer = TemperatureNormalizer.from_module_profile_path(REFERENCE_PROFILE, t_ref_C=25.0, t_hot_C=150.0)
        assert normalizer.normalize(4.5, 25.0) == pytest.approx(4.5)
        assert normalizer.normalize(7.2, 150.0) == pytest.approx(4.5)
        assert normalizer.normalize(4.5 * 1.3, 87.5) == pytest.approx(4.5)
        assert normalizer.normalize(4.5 * 1.48, 125.0) == pytest.approx(4.5)
        for tj in [25.0, 87.5, 125.0, 150.0]:
            factor = 1 + (7.2 / 4.5 - 1) * (tj - 25) / 125
            rds = 4.5 * factor
            assert normalizer.denormalize(normalizer.normalize(rds, tj), tj) == pytest.approx(rds)

    def test_missing_inputs_stay_missing(self):
        normalizer = TemperatureNormalizer.from_module_profile_path(REFERENCE_PROFILE, t_ref_C=25.0, t_hot_C=150.0)
        assert pd.isna(normalizer.normalize(np.nan, 25.0))
        assert pd.isna(normalizer.normalize(4.5, np.nan))
        series = normalizer.normalize(pd.Series([4.5, np.nan]), pd.Series([25.0, 25.0]))
        assert series.iloc[0] == pytest.approx(4.5)
        assert pd.isna(series.iloc[1])


class TestMissingnessAndBaseline:
    def test_missing_not_converted_to_zero(self, sample_telemetry):
        telemetry = sample_telemetry.copy()
        telemetry.loc[telemetry["cycle_number"] == 50, "RDS_on"] = np.nan
        obs, _ = FeatureTransformer(FeatureConfig(target_cycles=100)).transform(telemetry)
        mask = obs["cycle_number"] == 50
        assert obs.loc[mask, "RDS_on"].isna().all()
        assert obs.loc[mask, "RDS_on_delta_from_baseline"].isna().all()
        assert obs.loc[mask, "temperature_normalized_RDS_on"].isna().all()
        assert not (obs.loc[mask, "RDS_on"] == 0).any()

    def test_baseline_short_trajectory(self):
        data = []
        for module_id in range(2):
            for cycle in [0, 10, 20, 30, 40]:
                data.append(
                    {
                        "module_id": f"mod_{module_id:03d}",
                        "test_id": "test_001",
                        "lot_id": "lot_00",
                        "dataset_id": "test_dataset",
                        "timestamp": pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(days=cycle),
                        "cycle_number": cycle,
                        "RDS_on": 4.5,
                        "VTH": 2.8,
                        "IGSS": 1e-3,
                        "IDSS": 1e-2,
                        "VDS_on": 1.8,
                        "Tj": 25.0,
                        "Tc": 20.0,
                        "electrical_power": 100.0,
                    }
                )
        short = pd.DataFrame(data)
        transformer = FeatureTransformer(FeatureConfig(target_cycles=100, baseline_min_cycles=10))
        assert transformer._baseline_size(5) == 5
        obs, _ = transformer.transform(short)
        assert obs["RDS_on_baseline_median"].notna().all()
        assert obs["RDS_on_baseline_median"].iloc[0] == pytest.approx(4.5)

    def test_baseline_formula(self):
        transformer = FeatureTransformer(FeatureConfig(target_cycles=100, baseline_min_cycles=10, baseline_window_fraction=0.1))
        assert transformer._baseline_size(100) == 10
        assert transformer._baseline_size(200) == 20
        assert transformer._baseline_size(5) == 5


class TestLeakageAndGroundTruth:
    def test_future_modification_does_not_change_past_features(self, sample_telemetry):
        cutoff = 100
        config = FeatureConfig(target_cycles=400)
        original, _ = FeatureTransformer(config).transform(sample_telemetry)
        modified_telemetry = sample_telemetry.copy()
        future = modified_telemetry["cycle_number"] > cutoff
        modified_telemetry.loc[future, "RDS_on"] = modified_telemetry.loc[future, "RDS_on"] * 5
        modified_telemetry.loc[future, "VTH"] = modified_telemetry.loc[future, "VTH"] + 1.0
        modified_telemetry.loc[future, "Tj"] = modified_telemetry.loc[future, "Tj"] + 40.0
        modified_telemetry.loc[future, "electrical_power"] = 9999.0
        modified, _ = FeatureTransformer(config).transform(modified_telemetry)

        validator = FeatureValidator(create_v1_feature_set())
        ok, errors = validator.validate_leakage_prevention(
            sample_telemetry, original, cutoff, modified_observation_features=modified
        )
        assert ok, errors

        feature_cols = create_v1_feature_set().observation_feature_names()
        a = original[original["cycle_number"] <= cutoff].sort_values(["module_id", "cycle_number"])
        b = modified[modified["cycle_number"] <= cutoff].sort_values(["module_id", "cycle_number"])
        for col in feature_cols:
            assert np.allclose(a[col].to_numpy(dtype=float), b[col].to_numpy(dtype=float), equal_nan=True), col

    def test_ground_truth_columns_in_telemetry_are_dropped(self, sample_telemetry):
        telemetry = sample_telemetry.copy()
        telemetry["mechanism"] = "bond_wire_interconnect"
        telemetry["onset_cycle"] = 50
        telemetry["health_state"] = "degrading"
        telemetry["stage"] = "early"
        telemetry["severity"] = 0.4
        telemetry["rate_scale"] = 1.0
        telemetry["terminal_cycle"] = 90
        telemetry["mechanism_model"] = "bond_wire_v1"
        obs, mod = FeatureTransformer(FeatureConfig(target_cycles=100)).transform(telemetry)
        leaked = set(obs.columns) | set(mod.columns)
        assert leaked.isdisjoint(FORBIDDEN_FEATURE_COLUMNS)

    def test_pipeline_never_reads_ground_truth(self, tmp_path, monkeypatch, sample_telemetry):
        dataset_dir = tmp_path / "syn-unit"
        (dataset_dir / "telemetry").mkdir(parents=True)
        (dataset_dir / "ground_truth").mkdir()
        (dataset_dir / "metadata").mkdir()
        (dataset_dir / "validation").mkdir()
        sample_telemetry.to_parquet(dataset_dir / "telemetry" / "telemetry.parquet", index=False)
        pd.DataFrame({"module_id": ["mod_000"], "mechanism": ["healthy"], "onset_cycle": [10]}).to_parquet(
            dataset_dir / "ground_truth" / "ground-truth.parquet", index=False
        )
        (dataset_dir / "metadata" / "dataset.json").write_text(
            json.dumps(
                {
                    "dataset_id": "syn-unit",
                    "target_cycles": 400,
                    "schema_version_telemetry": "1.0.0",
                }
            )
        )
        (dataset_dir / "validation" / "validation-report.json").write_text(
            json.dumps(
                {
                    "dataset_id": "syn-unit",
                    "overall_status": "PASS",
                    "validator_version": "1.0.0",
                    "validation_timestamp": "2026-09-22T00:00:00Z",
                }
            )
        )

        original_read = pd.read_parquet

        def guarded_read(path, *args, **kwargs):
            if "ground-truth" in str(path) or "ground_truth" in str(path):
                raise AssertionError("Feature generation loaded ground-truth.parquet")
            return original_read(path, *args, **kwargs)

        monkeypatch.setattr(pd, "read_parquet", guarded_read)
        result = build_features_from_dataset(dataset_dir, output_dir=str(tmp_path / "features"), write=True)
        assert "mechanism" not in result.observation_features.columns
        gt_path = dataset_dir / "ground_truth" / "ground-truth.parquet"
        assert gt_path.exists()


class TestSchemaDeterminism:
    def test_vf_missingness_does_not_change_schema(self):
        with_nan_vf = _sample_telemetry(include_vf=True)
        with_nan_vf["VF"] = np.nan
        with_values = _sample_telemetry(include_vf=True)
        without_column = _sample_telemetry(include_vf=False)
        config = FeatureConfig(target_cycles=400)
        a, _ = FeatureTransformer(config).transform(with_nan_vf)
        b, _ = FeatureTransformer(config).transform(with_values)
        c, _ = FeatureTransformer(config).transform(without_column)
        assert list(a.columns) == list(b.columns) == list(c.columns)
        assert list(a.columns) == create_v1_feature_set().observation_parquet_columns()
        assert a["VF"].isna().all()
        assert b["VF"].notna().all()
        assert c["VF"].isna().all()
        assert "VF_baseline_median" not in a.columns
        assert "VF_rolling_mean_5" not in a.columns


class TestValidator:
    def test_detects_missing_feature_column(self, sample_telemetry):
        obs, mod = FeatureTransformer(FeatureConfig(target_cycles=100)).transform(sample_telemetry)
        modified = obs.drop(columns=["RDS_on_trend"])
        is_valid, errors = FeatureValidator(create_v1_feature_set()).validate_features(modified, mod, "test")
        assert not is_valid
        assert any("Missing expected feature" in err for err in errors)

    def test_detects_unexpected_feature_column(self, sample_telemetry):
        obs, mod = FeatureTransformer(FeatureConfig(target_cycles=100)).transform(sample_telemetry)
        modified = obs.copy()
        modified["unexpected_feature"] = 1.0
        is_valid, errors = FeatureValidator(create_v1_feature_set()).validate_features(modified, mod, "test")
        assert not is_valid
        assert any("Unexpected feature columns not in registry" in err for err in errors)

    def test_detects_invalid_feature_version_metadata(self, sample_telemetry):
        obs, mod = FeatureTransformer(FeatureConfig(target_cycles=100)).transform(sample_telemetry)
        metadata = {"feature_version": "v9", "feature_counts": {}, "feature_designation": {}}
        is_valid, errors = FeatureValidator(create_v1_feature_set()).validate_features(
            obs, mod, "test", metadata=metadata
        )
        assert not is_valid
        assert any("invalid feature_version" in err for err in errors)

    def test_detects_retrospective_metadata_mismatch(self, sample_telemetry):
        obs, mod = FeatureTransformer(FeatureConfig(target_cycles=100)).transform(sample_telemetry)
        metadata = {
            "feature_version": "v1",
            "feature_counts": {
                "observation_columns": 160,
                "observation_feature_columns": 153,
                "module_columns": 929,
            },
            "feature_designation": {"module_features_is_retrospective": False, "observation_features_is_causal": True},
        }
        is_valid, errors = FeatureValidator(create_v1_feature_set()).validate_features(
            obs, mod, "test", metadata=metadata
        )
        assert not is_valid
        assert any("Retrospective metadata mismatch" in err for err in errors)

    def test_module_features_marked_retrospective_in_registry_metadata(self, tmp_path):
        from ml.features.output import FeatureOutputWriter

        writer = FeatureOutputWriter(str(tmp_path))
        obs = pd.DataFrame(columns=create_v1_feature_set().observation_parquet_columns())
        mod = pd.DataFrame(columns=create_v1_feature_set().module_parquet_columns())
        metadata = writer.build_metadata(
            observation_features=obs,
            module_features=mod,
            feature_version="v1",
            source_dataset_id="x",
            schema_version="1.0.0",
            generation_metadata={},
            validation_metadata={"validation_status": "PASS"},
            window_config={"window_sizes": [5, 10, 20]},
            baseline_config={},
            temperature_config={},
            feature_set=create_v1_feature_set(),
        )
        assert metadata["feature_designation"]["module_features_is_retrospective"] is True
        assert metadata["feature_designation"]["observation_features_is_causal"] is True
        assert metadata["feature_counts"]["observation_feature_columns"] == 153
        assert metadata["feature_counts"]["module_columns"] == 929


class TestM5Integration:
    def test_blocked_dataset_refused(self, tmp_path):
        dataset_dir = tmp_path / "blocked"
        (dataset_dir / "validation").mkdir(parents=True)
        (dataset_dir / "validation" / "validation-report.json").write_text(
            json.dumps({"dataset_id": "blocked", "overall_status": "BLOCKED", "validator_version": "1.0.0"})
        )
        with pytest.raises(BlockedDatasetError):
            load_validation_metadata(dataset_dir)

    def test_warning_dataset_allowed(self, tmp_path):
        dataset_dir = tmp_path / "warn"
        (dataset_dir / "validation").mkdir(parents=True)
        (dataset_dir / "validation" / "validation-report.json").write_text(
            json.dumps(
                {
                    "dataset_id": "warn",
                    "overall_status": "WARNING",
                    "validator_version": "1.0.0",
                    "validation_timestamp": "2026-09-22T00:00:00Z",
                }
            )
        )
        meta = load_validation_metadata(dataset_dir)
        assert meta["validation_status"] == "WARNING"

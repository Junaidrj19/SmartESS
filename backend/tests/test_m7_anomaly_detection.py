"""Tests for M7 baseline unsupervised anomaly detection."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.anomaly import AnomalyConfig, BlockedFeaturesError, run_anomaly_pipeline
from ml.anomaly.aggregate import aggregate_module_summary, module_status
from ml.anomaly.baseline import (
    BASELINE_SIGNALS,
    BASELINE_THRESHOLD,
    compute_statistical_baseline,
)
from ml.anomaly.detector import IsolationForestDetector, fit_isolation_forest
from ml.anomaly.features import extract_feature_matrix, observation_model_feature_names
from ml.anomaly.pipeline import load_feature_bundle, score_observations, train_detector
from ml.anomaly.preprocess import fit_median_imputer
from ml.anomaly.registry import load_registry
from ml.anomaly.splits import lot_holdout_split
from ml.features import FeatureConfig, FeatureTransformer
from ml.features.definitions import FORBIDDEN_FEATURE_COLUMNS, create_v1_feature_set
from ml.features.output import FeatureOutputWriter


def _telemetry(n_modules: int = 8, n_obs: int = 24, n_lots: int = 2) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    rows = []
    per_lot = n_modules // n_lots
    for module_i in range(n_modules):
        lot = module_i // per_lot
        degrading = module_i % 4 == 0
        for obs_i in range(n_obs):
            cycle = obs_i * 10
            temp = 25.0 + obs_i
            rds = 4.5 * (1.0 + 0.0048 * (temp - 25.0))
            if degrading and obs_i > 8:
                rds += 0.15 * (obs_i - 8)
            rows.append(
                {
                    "module_id": f"mod_{module_i:03d}",
                    "test_id": "test_001",
                    "lot_id": f"lot_{lot:02d}",
                    "dataset_id": "syn-unit-ad",
                    "timestamp": pd.Timestamp("2026-01-01", tz="UTC") + pd.Timedelta(hours=cycle),
                    "cycle_number": cycle,
                    "RDS_on": rds + float(rng.normal(0, 1e-3)),
                    "VTH": 2.8,
                    "IGSS": 1e-3,
                    "IDSS": 1e-2,
                    "VDS_on": 1.8,
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
    return pd.DataFrame(rows)


def _write_features(tmp_path: Path, telemetry: pd.DataFrame, *, blocked: bool = False) -> Path:
    obs, _mod = FeatureTransformer(FeatureConfig(target_cycles=400)).transform(telemetry)
    feature_dir = tmp_path / "features" / "v1"
    writer = FeatureOutputWriter(str(tmp_path / "features"))
    writer.write_features(
        observation_features=obs,
        module_features=_mod,
        feature_version="v1",
        source_dataset_id="syn-unit-ad",
        schema_version="1.0.0",
        generation_metadata={"source": "test"},
        validation_metadata={
            "validation_status": "BLOCKED" if blocked else "PASS",
            "validator_version": "1.0.0",
            "validation_timestamp": "2026-09-22T00:00:00Z",
            "source_dataset_id": "syn-unit-ad",
            "validation_report_reference": "validation/validation-report.json",
        },
        window_config={"window_sizes": [5, 10, 20]},
        baseline_config={"baseline_window_fraction": 0.1, "baseline_min_cycles": 10},
        temperature_config={},
        feature_set=create_v1_feature_set(),
    )
    return feature_dir


def _write_ground_truth(tmp_path: Path, telemetry: pd.DataFrame) -> Path:
    dataset_dir = tmp_path / "dataset"
    (dataset_dir / "ground_truth").mkdir(parents=True)
    modules = telemetry["module_id"].drop_duplicates().tolist()
    rows = []
    for module_id in modules:
        idx = int(str(module_id).split("_")[1])
        degrading = idx % 4 == 0
        rows.append(
            {
                "module_id": module_id,
                "lot_id": telemetry.loc[telemetry["module_id"] == module_id, "lot_id"].iloc[0],
                "health_state": "degrading" if degrading else "healthy",
                "degradation_mechanism": "bond_wire_interconnect" if degrading else "healthy",
                "onset_cycle": 80 if degrading else None,
                "cycle_measurable": 120 if degrading else None,
            }
        )
    pd.DataFrame(rows).to_parquet(dataset_dir / "ground_truth" / "ground-truth.parquet", index=False)
    return dataset_dir


class TestAnomalyDetection:
    def test_lot_split_has_no_module_overlap(self):
        telemetry = _telemetry()
        obs, _ = FeatureTransformer(FeatureConfig(target_cycles=400)).transform(telemetry)
        split = lot_holdout_split(obs, random_state=1, test_lot_fraction=0.5)
        assert set(split.train_modules).isdisjoint(split.test_modules)
        assert split.train_lots
        assert split.test_lots
        assert set(split.train_lots).isdisjoint(split.test_lots)

    def test_model_inputs_are_observation_features_only(self):
        names = observation_model_feature_names()
        assert len(names) == 153
        assert "module_id" not in names
        assert not any(name.endswith("_mean") and name.startswith("RDS_on_mean") for name in names)

    def test_forbidden_columns_rejected_as_features(self):
        telemetry = _telemetry()
        obs, _ = FeatureTransformer(FeatureConfig(target_cycles=400)).transform(telemetry)
        obs["mechanism"] = "bond_wire_interconnect"
        with pytest.raises(ValueError, match="Forbidden"):
            extract_feature_matrix(obs)

    def test_blocked_features_refused(self, tmp_path):
        telemetry = _telemetry()
        feature_dir = _write_features(tmp_path, telemetry, blocked=True)
        with pytest.raises(BlockedFeaturesError):
            load_feature_bundle(feature_dir)

    def test_training_does_not_read_ground_truth(self, tmp_path, monkeypatch):
        telemetry = _telemetry()
        feature_dir = _write_features(tmp_path, telemetry)
        dataset_dir = _write_ground_truth(tmp_path, telemetry)
        original = pd.read_parquet

        def guarded(path, *args, **kwargs):
            if "ground-truth" in str(path) or "ground_truth" in Path(path).parts:
                raise AssertionError("training loaded ground truth")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(pd, "read_parquet", guarded)
        run_anomaly_pipeline(
            feature_dir,
            source_dataset_dir=dataset_dir,
            config=AnomalyConfig(random_state=3, output_directory=str(tmp_path / "models"), scores_directory=str(tmp_path / "scores")),
            evaluate=False,
            write=False,
        )

    def test_evaluation_uses_ground_truth_separately(self, tmp_path):
        telemetry = _telemetry()
        feature_dir = _write_features(tmp_path, telemetry)
        dataset_dir = _write_ground_truth(tmp_path, telemetry)
        result = run_anomaly_pipeline(
            feature_dir,
            source_dataset_dir=dataset_dir,
            config=AnomalyConfig(
                random_state=3,
                n_estimators=20,
                output_directory=str(tmp_path / "models"),
                scores_directory=str(tmp_path / "scores"),
            ),
            evaluate=True,
            write=True,
        )
        assert result.evaluation is not None
        assert result.evaluation["ground_truth_used_for_training"] is False
        assert "precision" in result.evaluation["test_lots"]["metrics"]
        assert result.record["uses_module_retrospective_features"] is False
        assert result.record["feature_version"] == "v1"
        assert "anomaly_score" in result.observation_scores.columns
        gt_fields = {
            "mechanism",
            "health_state",
            "onset_cycle",
            "stage",
            "severity",
            "rate_scale",
            "terminal_cycle",
            "mechanism_model",
            "ground_truth",
        }
        assert set(result.observation_scores.columns).isdisjoint(gt_fields)
        assert (tmp_path / "models" / result.model_id / "model-record.json").exists()

    def test_does_not_load_module_feature_parquet(self, tmp_path, monkeypatch):
        telemetry = _telemetry()
        feature_dir = _write_features(tmp_path, telemetry)
        original = pd.read_parquet

        def guarded(path, *args, **kwargs):
            if "module-features" in str(path):
                raise AssertionError("M7 loaded retrospective module-features.parquet")
            return original(path, *args, **kwargs)

        monkeypatch.setattr(pd, "read_parquet", guarded)
        run_anomaly_pipeline(
            feature_dir,
            config=AnomalyConfig(random_state=3, n_estimators=20),
            evaluate=False,
            write=False,
        )

    def test_scores_are_causal_for_held_out_module_prefix(self, tmp_path):
        telemetry = _telemetry()
        feature_dir = _write_features(tmp_path, telemetry)
        dataset_dir = _write_ground_truth(tmp_path, telemetry)
        config = AnomalyConfig(random_state=3, n_estimators=20)
        full = run_anomaly_pipeline(feature_dir, source_dataset_dir=dataset_dir, config=config, evaluate=False, write=False)

        obs, meta = load_feature_bundle(feature_dir)
        split = lot_holdout_split(obs, random_state=config.random_state, test_lot_fraction=config.test_lot_fraction)
        detector, imputer = train_detector(obs, split, config)
        cutoff = 80
        truncated = obs[obs["cycle_number"] <= cutoff].copy()
        from ml.anomaly.pipeline import score_observations

        scores_full = full.observation_scores
        scores_trunc = score_observations(truncated, detector, imputer)
        merged = scores_full.merge(scores_trunc, on=["module_id", "cycle_number"], suffixes=("_a", "_b"))
        merged = merged[merged["cycle_number"] <= cutoff]
        assert np.allclose(merged["anomaly_score_a"], merged["anomaly_score_b"])

    OBSERVATION_COLUMNS = [
        "module_id",
        "test_id",
        "lot_id",
        "dataset_id",
        "timestamp",
        "cycle_number",
        "observation_index_within_module",
        "anomaly_score",
        "is_anomaly",
        "statistical_baseline_score",
        "statistical_baseline_flag",
        "detector_version",
        "feature_version",
        "algorithm",
        "model_id",
    ]

    MODULE_COLUMNS = [
        "module_id",
        "test_id",
        "lot_id",
        "dataset_id",
        "n_observations",
        "n_anomalous_observations",
        "anomaly_rate",
        "max_anomaly_score",
        "mean_anomaly_score",
        "first_anomalous_cycle",
        "last_anomalous_cycle",
        "anomalous_cycle_span",
        "statistical_baseline_max",
        "statistical_baseline_flag_rate",
        "module_anomaly_status",
    ]

    def test_observation_output_schema(self, tmp_path):
        telemetry = _telemetry()
        feature_dir = _write_features(tmp_path, telemetry)
        dataset_dir = _write_ground_truth(tmp_path, telemetry)
        result = run_anomaly_pipeline(
            feature_dir,
            source_dataset_dir=dataset_dir,
            config=AnomalyConfig(random_state=3, n_estimators=20),
            evaluate=True,
            write=False,
        )
        obs = result.observation_scores
        assert list(obs.columns) == self.OBSERVATION_COLUMNS
        assert obs["module_id"].is_monotonic_increasing or not obs["module_id"].is_monotonic_increasing
        n_orig = len(telemetry)
        assert len(obs) == n_orig
        expected_modules = telemetry["module_id"].nunique()
        assert obs["module_id"].nunique() == expected_modules

    def test_module_output_schema(self, tmp_path):
        telemetry = _telemetry()
        feature_dir = _write_features(tmp_path, telemetry)
        dataset_dir = _write_ground_truth(tmp_path, telemetry)
        result = run_anomaly_pipeline(
            feature_dir,
            source_dataset_dir=dataset_dir,
            config=AnomalyConfig(random_state=3, n_estimators=20),
            evaluate=True,
            write=False,
        )
        summary = result.module_summary
        assert list(summary.columns) == self.MODULE_COLUMNS
        assert summary["module_id"].is_unique
        n_modules = telemetry["module_id"].nunique()
        assert len(summary) == n_modules
        assert summary["n_observations"].sum() == len(result.observation_scores)

    def test_reproducibility_deterministic_rerun(self, tmp_path):
        telemetry = _telemetry()
        feature_dir = _write_features(tmp_path, telemetry)
        dataset_dir = _write_ground_truth(tmp_path, telemetry)
        config = AnomalyConfig(random_state=3, n_estimators=20)
        first = run_anomaly_pipeline(
            feature_dir, source_dataset_dir=dataset_dir, config=config, evaluate=True, write=False
        )
        second = run_anomaly_pipeline(
            feature_dir, source_dataset_dir=dataset_dir, config=config, evaluate=True, write=False
        )
        pd.testing.assert_frame_equal(
            first.observation_scores.reset_index(drop=True),
            second.observation_scores.reset_index(drop=True),
            check_dtype=False,
        )
        pd.testing.assert_frame_equal(
            first.module_summary.reset_index(drop=True),
            second.module_summary.reset_index(drop=True),
            check_dtype=False,
        )
        assert first.record["threshold"] == second.record["threshold"]
        assert first.record["hyperparameters"] == second.record["hyperparameters"]
        assert list(first.record["split"]["train_lots"]) == list(second.record["split"]["train_lots"])

    def test_statistical_baseline_threshold(self):
        telemetry = _telemetry()
        obs, _ = FeatureTransformer(FeatureConfig(target_cycles=400)).transform(telemetry)
        baseline = compute_statistical_baseline(obs)
        assert BASELINE_THRESHOLD == 3.0
        flag = baseline["statistical_baseline_flag"]
        score = baseline["statistical_baseline_score"]
        assert flag.equals(score >= BASELINE_THRESHOLD)
        assert ((score >= BASELINE_THRESHOLD) == flag.to_numpy()).all()
        assert (score[flag]).min() >= BASELINE_THRESHOLD

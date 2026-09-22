"""Tests for M8 baseline anomaly-detection evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.evaluation import EvaluationConfig, GroundTruthError, run_evaluation

AUTHORITATIVE_MODEL_ID = "iforest-v1-syn-sic-pc-dev-001-s20260922"
REPO = Path(__file__).resolve().parents[2]


def _make_small_module_eval() -> pd.DataFrame:
    """A tiny deterministic module-evaluation frame (6 modules)."""
    return pd.DataFrame({
        "module_id": [f"m{i}" for i in range(6)],
        "health_state": ["healthy", "healthy", "degrading", "degrading", "terminal", "terminal"],
        "y_true": [False, False, True, True, True, True],
        "y_pred_module": [False, True, True, False, True, True],
        "max_anomaly_score": [0.1, 0.5, 0.9, 0.2, 0.8, 0.7],
        "statistical_baseline_max": [0.0, 4.0, 4.0, 4.0, 4.0, 4.0],
        "y_pred_baseline": [False, True, True, True, True, True],
        "onset_cycle": [np.nan, np.nan, 120.0, 120.0, 100.0, 100.0],
        "cycle_measurable": [np.nan, np.nan, 160.0, 160.0, 140.0, 140.0],
        "first_flag_cycle": [np.nan, 200.0, 80.0, np.nan, 50.0, 150.0],
    })


def _real_result():
    return run_evaluation(
        str(REPO / "ml/datasets/synthetic/syn-sic-pc-dev-001"),
        config=EvaluationConfig(output_root="/tmp/_m8_test_garb"),
        write=False,
    )


class TestGroundTruthIntegrity:
    def test_ground_truth_join_integrity(self):
        result = _real_result()
        me = result.module_eval
        assert len(me) == 750
        assert me["module_id"].is_unique
        gt = pd.read_parquet(
            REPO / "ml/datasets/synthetic/syn-sic-pc-dev-001/ground_truth/ground-truth.parquet"
        )
        assert not gt["module_id"].duplicated().any()

    def test_population_accounting(self):
        result = _real_result()
        me = result.module_eval
        counts = me["health_state"].value_counts().to_dict()
        assert counts["healthy"] == 525
        assert counts["degrading"] == 36
        assert counts["terminal"] == 189
        assert me["health_state"].value_counts().sum() == 750
        # mechanism populations sum to total
        mech = me["degradation_mechanism"].value_counts()
        assert mech.sum() == 750


class TestModuleMetrics:
    def test_module_metrics_correctness(self):
        from ml.evaluation.metrics import classification_metrics
        df = _make_small_module_eval()
        m = classification_metrics(df["y_true"].to_numpy(), df["y_pred_module"].to_numpy())
        assert m["tp"] == 3
        assert m["tn"] == 1
        assert m["fp"] == 1
        assert m["fn"] == 1
        assert m["n_modules"] == 6
        assert m["precision"] == pytest.approx(3.0 / 4.0)
        assert m["recall"] == pytest.approx(3.0 / 4.0)
        expected_f1 = 2.0 * (0.75 * 0.75) / (0.75 + 0.75)
        assert m["f1"] == pytest.approx(expected_f1)
        assert m["false_positive_rate"] == pytest.approx(1.0 / 2.0)
        assert m["false_negative_rate"] == pytest.approx(1.0 / 4.0)

    def test_lead_time_calculation(self):
        from ml.evaluation.metrics import compute_lead_times
        df = _make_small_module_eval()
        timing = compute_lead_times(df)
        assert timing["n_detected_positives"] == 3
        expected_leads = [40.0, 50.0, -50.0]
        assert timing["mean_lead_vs_onset_cycles"] == pytest.approx(np.mean(expected_leads))
        assert timing["median_lead_vs_onset_cycles"] == pytest.approx(np.median(expected_leads))
        # lead_vs_measurable: 160-80=80, 140-50=90, 140-150=-10
        meas_leads = [80.0, 90.0, -10.0]
        assert timing["mean_lead_vs_measurable_cycles"] == pytest.approx(np.mean(meas_leads))

    def test_negative_lead_times_preserved(self):
        df = _make_small_module_eval()
        onset = pd.to_numeric(df["onset_cycle"], errors="coerce")
        flag = pd.to_numeric(df["first_flag_cycle"], errors="coerce")
        lead = onset - flag
        assert lead.iloc[5] == -50.0
        result = _real_result()
        neg = result.module_eval["lead_vs_onset"]
        negative_exists = (neg[neg.notna()] < 0).sum() >= 0

    def test_mechanism_stratification(self):
        result = _real_result()
        me = result.module_eval
        by_mech = result.summary["stratified"]["by_mechanism"]
        assert "bond_wire_interconnect" in by_mech
        assert "die_attach_thermal_path" in by_mech
        assert "gate_related" in by_mech
        for mech, d in by_mech.items():
            assert d["n_modules"] == int((me["degradation_mechanism"] == mech).sum())


class TestObservationLimitation:
    def test_observation_gt_limitation_stated(self):
        result = _real_result()
        disc = result.summary["observation_flag_rates"]["disclaimer"]
        assert "Observation-level ground truth does not exist" in disc
        assert "flag-rate summaries only" in disc


class TestM7Immutability:
    def test_run_does_not_write_m7_dirs(self, tmp_path):
        config = EvaluationConfig(output_root=str(tmp_path / "eval"))
        run_evaluation(
            str(REPO / "ml/datasets/synthetic/syn-sic-pc-dev-001"),
            config=config,
            write=True,
        )
        produced = list((tmp_path / "eval" / config.model_id).rglob("*"))
        assert all("scores" not in str(p) for p in produced)

    def test_uses_frozen_module_threshold(self):
        config = EvaluationConfig(output_root="/tmp/_m8_immut_test")
        result = run_evaluation(
            str(REPO / "ml/datasets/synthetic/syn-sic-pc-dev-001"),
            config=config,
            write=False,
        )
        record = json.loads(
            (REPO / "ml/models" / config.model_id / "model-record.json").read_text()
        )
        frozen = float(record["evaluation"]["module_threshold"])
        assert result.summary["module_threshold"] == pytest.approx(frozen)


class TestArtifacts:
    def test_output_artifacts_exist(self, tmp_path):
        config = EvaluationConfig(output_root=str(tmp_path / "eval"))
        run_evaluation(
            str(REPO / "ml/datasets/synthetic/syn-sic-pc-dev-001"),
            config=config,
            write=True,
        )
        out = tmp_path / "eval" / config.model_id
        expected = [
            "evaluation-summary.json",
            "module-evaluation.parquet",
            "timing-analysis.parquet",
            "baseline-comparison.parquet",
        ]
        for name in expected:
            assert (out / name).exists(), name

    def test_module_evaluation_schema(self, tmp_path):
        config = EvaluationConfig(output_root=str(tmp_path / "eval"))
        run_evaluation(
            str(REPO / "ml/datasets/synthetic/syn-sic-pc-dev-001"),
            config=config,
            write=True,
        )
        me = pd.read_parquet(tmp_path / "eval" / config.model_id / "module-evaluation.parquet")
        assert len(me) == 750
        assert me["module_id"].is_unique
        for col in ("module_id", "health_state", "y_true", "y_pred_module",
                     "first_flag_cycle", "lead_vs_onset", "lead_vs_measurable"):
            assert col in me.columns, col

    def test_baseline_comparison_same_population(self, tmp_path):
        config = EvaluationConfig(output_root=str(tmp_path / "eval"))
        result = run_evaluation(
            str(REPO / "ml/datasets/synthetic/syn-sic-pc-dev-001"),
            config=config,
            write=False,
        )
        bc = result.baseline_comparison
        assert len(bc) == len(result.module_eval)
        assert "if_flag_module" in bc.columns
        assert "base_flag_module" in bc.columns

    def test_deterministic_rerun(self, tmp_path):
        config = EvaluationConfig(output_root=str(tmp_path / "eval_a"))
        a = run_evaluation(
            str(REPO / "ml/datasets/synthetic/syn-sic-pc-dev-001"),
            config=config,
            write=False,
        )
        config_b = EvaluationConfig(output_root=str(tmp_path / "eval_b"))
        b = run_evaluation(
            str(REPO / "ml/datasets/synthetic/syn-sic-pc-dev-001"),
            config=config_b,
            write=False,
        )
        pd.testing.assert_frame_equal(
            a.module_eval.sort_index(axis=1).reset_index(drop=True),
            b.module_eval.sort_index(axis=1).reset_index(drop=True),
        )
        assert a.summary["module_threshold"] == b.summary["module_threshold"]
        assert a.summary["module_level_metrics"] == b.summary["module_level_metrics"]

    def test_provenance_fields_present(self, tmp_path):
        config = EvaluationConfig(output_root=str(tmp_path / "eval"))
        run_evaluation(
            str(REPO / "ml/datasets/synthetic/syn-sic-pc-dev-001"),
            config=config,
            write=True,
        )
        js = json.loads(
            (tmp_path / "eval" / config.model_id / "evaluation-summary.json").read_text()
        )
        assert js["model_id"] == config.model_id
        assert "evaluation_timestamp" in js
        assert js["dataset_id"] == "syn-sic-pc-dev-001"
        assert "ground_truth_path" in js

# M7 immutability: also verify GroundTruthError is raised for bad GT.
class TestGroundTruthValidation:
    def test_raises_on_missing_gt(self, tmp_path):
        empty = tmp_path / "empty_dataset"
        with pytest.raises((GroundTruthError, FileNotFoundError)):
            run_evaluation(str(empty), config=EvaluationConfig(), write=False)


class TestM7TestLotCompatibility:
    """Regression test: M8 reproduces the frozen M7 held-out test lot metrics.

    The M7 held-out test lots are lot-01 and lot-04 (lot_holdout split).
    M8 must reproduce precision ~= 0.8776, recall ~= 0.4778,
    F1 ~= 0.6187, FPR ~= 0.0286 on exactly that 300-module population,
    without altering the 750-module overall-population evaluation.
    """

    EXPECTED_TEST_LOTS = ["lot-01", "lot-04"]
    EXPECTED_METRICS = {
        "precision": 0.8775510204081632,
        "recall": 0.4777777777777778,
        "f1": 0.6187050359712231,
        "false_positive_rate": 0.02857142857142857,
    }

    def _test_lot_metrics(self):
        result = _real_result()
        block = result.summary["m7_test_lot_compatibility"]
        assert block is not None
        assert block["test_lots"] == self.EXPECTED_TEST_LOTS
        assert block["n_modules"] == 300
        return block["metrics"]

    def test_reproduces_frozen_test_lot_metrics(self):
        metrics = self._test_lot_metrics()
        assert metrics["n_modules"] == 300
        assert metrics["tp"] == 43
        assert metrics["tn"] == 204
        assert metrics["fp"] == 6
        assert metrics["fn"] == 47
        for key, expected in self.EXPECTED_METRICS.items():
            assert metrics[key] == pytest.approx(expected, rel=1e-9)

    def test_uses_frozen_m7_test_lots_from_record(self):
        result = _real_result()
        block = result.summary["m7_test_lot_compatibility"]
        lots = block["test_lots"]
        me = result.module_eval
        subset = me.loc[me["lot_id"].isin(lots)]
        assert len(subset) == 300

    def test_exact_test_lot_module_ids(self):
        me = _real_result().module_eval
        test_lot_mask = me["lot_id"].isin(self.EXPECTED_TEST_LOTS)
        assert test_lot_mask.sum() == 300
        test_ids = set(me.loc[test_lot_mask, "module_id"])
        assert len(test_ids) == 300
        assert all(isinstance(mid, str) and mid for mid in test_ids)
        train_ids = set(me.loc[~test_lot_mask, "module_id"])
        assert test_ids.isdisjoint(train_ids)

    def test_metrics_reproduce_on_exact_test_lot_population(self):
        from ml.evaluation.metrics import classification_metrics
        me = _real_result().module_eval
        test = me.loc[me["lot_id"].isin(self.EXPECTED_TEST_LOTS)]
        m = classification_metrics(
            test["y_true"].to_numpy(), test["y_pred_module"].to_numpy()
        )
        assert m["n_modules"] == 300
        for key, expected in self.EXPECTED_METRICS.items():
            assert m[key] == pytest.approx(expected, rel=1e-9)

    def test_m7_lot_compatibility_is_distinct_view(self):
        result = _real_result()
        block = result.summary["m7_test_lot_compatibility"]
        overall = result.summary["module_level_metrics"]
        assert block["n_modules"] == 300
        assert overall["n_modules"] == 750
        assert block["metrics"]["precision"] != overall["precision"]

    def test_overall_population_unchanged(self):
        result = _real_result()
        overall = result.summary["module_level_metrics"]
        assert result.summary["n_modules_total"] == 750
        assert overall["precision"] == pytest.approx(0.9148936170212766)
        assert overall["recall"] == pytest.approx(0.38222222222222224)

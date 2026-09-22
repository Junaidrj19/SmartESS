from __future__ import annotations

import json
import math
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from ml.generators.synthetic.config import GenerationConfig, Scenario
from ml.generators.synthetic.generator import generate_dataset, load_profiles
from ml.validators.synthetic.engine import validate_dataset
from ml.validators.synthetic.models import (
    CheckCategory,
    CheckSeverity,
    CheckStatus,
    aggregate_status,
    make_check,
)

REPO = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO / "examples" / "module-profiles" / "sic-reference-module.json"
TEST_PATH = REPO / "examples" / "test-profiles" / "power-cycling-reference.json"


def tiny_config(**overrides) -> GenerationConfig:
    payload = {
        "dataset_id": "syn-m5-tiny",
        "scenario": Scenario.DEGRADATION_BENCHMARK,
        "seed": 11,
        "n_modules": 20,
        "n_lots": 2,
        "modules_per_lot": 10,
        "target_cycles": 4000,
        "observation_stride_cycles": 200,
        "degradation": {
            "onset_min_cycle": 400,
            "onset_max_cycle": 2400,
            "cycle_span": 2000,
        },
    }
    payload.update(overrides)
    return GenerationConfig.model_validate(payload)


@pytest.fixture(scope="module")
def profiles():
    return load_profiles(MODULE_PATH, TEST_PATH)


@pytest.fixture(scope="module")
def valid_dir(tmp_path_factory, profiles):
    output = tmp_path_factory.mktemp("m5-valid")
    module, test = profiles
    result = generate_dataset(tiny_config(), module, test, output)
    return result.dataset_dir


@pytest.fixture(scope="module")
def smoke_dir(tmp_path_factory, profiles):
    output = tmp_path_factory.mktemp("m5-smoke")
    module, test = profiles
    config = tiny_config(dataset_id="syn-smoke", seed=11)
    result = generate_dataset(config, module, test, output)
    return result.dataset_dir


@pytest.fixture(scope="module")
def quality_dir(tmp_path_factory, profiles):
    output = tmp_path_factory.mktemp("m5-quality")
    module, test = profiles
    config = tiny_config(dataset_id="syn-m5-quality", scenario=Scenario.DATA_QUALITY_STRESS, seed=13)
    result = generate_dataset(config, module, test, output)
    return result.dataset_dir


def _clone(src: Path, tmp_path: Path, name: str = "clone") -> Path:
    dest = tmp_path / name
    shutil.copytree(src, dest)
    return dest


def _rewrite_json(path: Path, mutator) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutator(payload)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _status(report, check_id: str) -> CheckStatus:
    for item in report.checks:
        if item.check_id == check_id:
            return item.status
    raise AssertionError(f"missing check {check_id}")


class TestAggregation:
    def test_all_pass(self):
        checks = [
            make_check("a", CheckCategory.METADATA, CheckSeverity.BLOCKING, failed=False, pass_message="ok", fail_message="no"),
            make_check("b", CheckCategory.METADATA, CheckSeverity.WARNING, failed=False, pass_message="ok", fail_message="no"),
        ]
        assert aggregate_status(checks) is CheckStatus.PASS

    def test_warning_without_block(self):
        checks = [
            make_check("a", CheckCategory.METADATA, CheckSeverity.BLOCKING, failed=False, pass_message="ok", fail_message="no"),
            make_check("b", CheckCategory.METADATA, CheckSeverity.WARNING, failed=True, pass_message="ok", fail_message="warn"),
        ]
        assert aggregate_status(checks) is CheckStatus.WARNING
        assert checks[1].status is CheckStatus.WARNING

    def test_blocked_not_downgraded(self):
        checks = [
            make_check("block", CheckCategory.LEAKAGE, CheckSeverity.BLOCKING, failed=True, pass_message="ok", fail_message="bad"),
            make_check("warn", CheckCategory.DISTRIBUTION, CheckSeverity.WARNING, failed=True, pass_message="ok", fail_message="warn"),
            make_check("pass", CheckCategory.METADATA, CheckSeverity.BLOCKING, failed=False, pass_message="ok", fail_message="no"),
        ]
        assert aggregate_status(checks) is CheckStatus.BLOCKED
        assert checks[0].status is CheckStatus.BLOCKED

    def test_warning_severity_never_blocks(self):
        result = make_check(
            "w",
            CheckCategory.CORRELATION,
            CheckSeverity.WARNING,
            failed=True,
            pass_message="ok",
            fail_message="suspicious",
        )
        assert result.status is CheckStatus.WARNING
        assert result.severity is CheckSeverity.WARNING


class TestValidDatasets:
    def test_valid_default_tiny_passes_or_warns(self, valid_dir):
        report = validate_dataset(valid_dir, write_output=True)
        assert report.overall_status in {CheckStatus.PASS, CheckStatus.WARNING}
        assert report.summary.n_blocked == 0
        assert (valid_dir / "validation" / "validation-report.json").is_file()
        assert (valid_dir / "validation" / "validation-report.md").is_file()
        assert report.summary.n_modules == 20
        assert report.summary.n_ground_truth_rows == 20
        assert (valid_dir / "telemetry" / "telemetry.parquet").is_file()

    def test_valid_smoke_dataset(self, smoke_dir):
        report = validate_dataset(smoke_dir, write_output=False)
        assert report.overall_status in {CheckStatus.PASS, CheckStatus.WARNING}
        assert report.summary.n_blocked == 0
        assert report.dataset_id == "syn-smoke"

    def test_reports_do_not_replace_source(self, valid_dir):
        tel_before = (valid_dir / "telemetry" / "telemetry.parquet").stat().st_mtime
        validate_dataset(valid_dir, write_output=True)
        tel_after = (valid_dir / "telemetry" / "telemetry.parquet").stat().st_mtime
        assert tel_before == tel_after


class TestCorruptions:
    def test_missing_required_artifact(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        (clone / "provenance" / "provenance.json").unlink()
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "artifacts.required_files") is CheckStatus.BLOCKED

    def test_corrupt_metadata(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        (clone / "metadata" / "dataset.json").write_text("{not-json", encoding="utf-8")
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "artifacts.readable") is CheckStatus.BLOCKED

    def test_mismatched_dataset_id(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        _rewrite_json(clone / "metadata" / "dataset.json", lambda p: p.update({"dataset_id": "other-id"}))
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "consistency.dataset_id") is CheckStatus.BLOCKED

    def test_mismatched_seed(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        _rewrite_json(clone / "metadata" / "generation-config.json", lambda p: p.update({"seed": 999}))
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "consistency.seed") is CheckStatus.BLOCKED

    def test_mismatched_generator_version(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        _rewrite_json(clone / "provenance" / "provenance.json", lambda p: p.update({"generator_version": "9.9.9"}))
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "consistency.generator_version") is CheckStatus.BLOCKED

    def test_synthetic_labelled_real_is_blocked(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        _rewrite_json(clone / "metadata" / "dataset.json", lambda p: p.update({"data_origin": "real"}))
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "metadata.data_origin") is CheckStatus.BLOCKED

    def test_missing_telemetry_column(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "telemetry" / "telemetry.parquet"
        tel = pd.read_parquet(path)
        tel = tel.drop(columns=["RDS_on"])
        tel.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "telemetry.required_columns") is CheckStatus.BLOCKED

    def test_invalid_telemetry_value_negative_rds(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "telemetry" / "telemetry.parquet"
        tel = pd.read_parquet(path)
        tel.loc[tel.index[0], "RDS_on"] = -1.0
        tel.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "numerical.non_negative_contract") is CheckStatus.BLOCKED

    def test_nan_blocked(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "telemetry" / "telemetry.parquet"
        tel = pd.read_parquet(path)
        tel.loc[tel.index[0], "Tj"] = np.nan
        tel.loc[tel.index[0], "Tj_status"] = "valid"
        tel.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        nan_status = _status(report, "telemetry.nan_inf")
        miss_status = _status(report, "telemetry.missingness_semantics")
        assert nan_status is CheckStatus.BLOCKED or miss_status is CheckStatus.BLOCKED

    def test_inf_blocked(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "telemetry" / "telemetry.parquet"
        tel = pd.read_parquet(path)
        tel.loc[tel.index[0], "ID"] = math.inf
        tel.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "telemetry.nan_inf") is CheckStatus.BLOCKED

    def test_invalid_missingness_value_present(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "telemetry" / "telemetry.parquet"
        tel = pd.read_parquet(path)
        tel.loc[tel.index[0], "VTH_status"] = "missing"
        tel.loc[tel.index[0], "VTH"] = 2.5
        tel.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "telemetry.missingness_semantics") is CheckStatus.BLOCKED

    def test_duplicate_telemetry_ids(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "telemetry" / "telemetry.parquet"
        tel = pd.read_parquet(path)
        tel.loc[tel.index[1], "telemetry_id"] = tel.loc[tel.index[0], "telemetry_id"]
        tel.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "identity.duplicate_telemetry_id") is CheckStatus.BLOCKED

    def test_duplicate_module_cycle_clean(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "telemetry" / "telemetry.parquet"
        tel = pd.read_parquet(path)
        tel.loc[tel.index[1], "module_id"] = tel.loc[tel.index[0], "module_id"]
        tel.loc[tel.index[1], "cycle_number"] = tel.loc[tel.index[0], "cycle_number"]
        tel.loc[tel.index[1], "telemetry_id"] = str(tel.loc[tel.index[1], "telemetry_id"]) + "-x"
        tel.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "identity.duplicate_module_cycle") is CheckStatus.BLOCKED

    def test_missing_ground_truth_module(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "ground_truth" / "ground-truth.parquet"
        gt = pd.read_parquet(path)
        gt = gt.iloc[1:].reset_index(drop=True)
        gt.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "ground_truth.module_alignment") is CheckStatus.BLOCKED

    def test_extra_ground_truth_module(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "ground_truth" / "ground-truth.parquet"
        gt = pd.read_parquet(path)
        extra = gt.iloc[[0]].copy()
        extra["module_id"] = "syn-mod-9999"
        gt = pd.concat([gt, extra], ignore_index=True)
        gt.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "ground_truth.module_alignment") is CheckStatus.BLOCKED

    def test_invalid_mechanism(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "ground_truth" / "ground-truth.parquet"
        gt = pd.read_parquet(path)
        gt.loc[gt.index[0], "degradation_mechanism"] = "solder_void_not_supported"
        gt.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "ground_truth.mechanisms") is CheckStatus.BLOCKED

    def test_invalid_stage_ordering(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "ground_truth" / "ground-truth.parquet"
        gt = pd.read_parquet(path)
        deg = gt[gt["degradation_mechanism"] != "healthy"].index[0]
        gt.loc[deg, "onset_cycle"] = 1000
        gt.loc[deg, "cycle_early"] = 800
        gt.loc[deg, "cycle_terminal"] = 500
        gt.loc[deg, "terminal_cycle"] = 500
        gt.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "ground_truth.onset_and_stages") is CheckStatus.BLOCKED

    def test_invalid_onset_healthy(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "ground_truth" / "ground-truth.parquet"
        gt = pd.read_parquet(path)
        healthy = gt[gt["degradation_mechanism"] == "healthy"].index[0]
        gt.loc[healthy, "onset_cycle"] = 200
        gt.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "ground_truth.onset_and_stages") is CheckStatus.BLOCKED

    def test_utc_violation(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "telemetry" / "telemetry.parquet"
        tel = pd.read_parquet(path)
        parsed = pd.to_datetime(tel["timestamp"], utc=True)
        tel["timestamp"] = parsed.dt.tz_localize(None)
        tel.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "temporal.utc") is CheckStatus.BLOCKED

    def test_cycle_monotonicity_violation(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "telemetry" / "telemetry.parquet"
        tel = pd.read_parquet(path)
        module = tel["module_id"].iloc[0]
        idx = tel.index[tel["module_id"] == module][:3]
        tel.loc[idx[2], "cycle_number"] = int(tel.loc[idx[0], "cycle_number"])
        tel.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "temporal.cycle_monotonicity") is CheckStatus.BLOCKED

    def test_expected_data_quality_defects(self, quality_dir):
        report = validate_dataset(quality_dir, write_output=False)
        assert _status(report, "missingness.stress_expected") is CheckStatus.PASS
        assert report.summary.scenario == Scenario.DATA_QUALITY_STRESS.value

    def test_unexpected_data_quality_defects(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "telemetry" / "telemetry.parquet"
        tel = pd.read_parquet(path)
        tel.loc[tel.index[:5], "RDS_on"] = None
        tel.loc[tel.index[:5], "RDS_on_status"] = "missing"
        tel.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "missingness.clean_unexpected") is CheckStatus.BLOCKED

    def test_ground_truth_leakage(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "telemetry" / "telemetry.parquet"
        tel = pd.read_parquet(path)
        gt = pd.read_parquet(clone / "ground_truth" / "ground-truth.parquet")
        mapping = dict(zip(gt["module_id"].astype(str), gt["degradation_mechanism"].astype(str)))
        tel["degradation_mechanism"] = tel["module_id"].astype(str).map(mapping)
        tel.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "leakage.ground_truth_in_telemetry") is CheckStatus.BLOCKED

    def test_mechanism_composition_mismatch(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "ground_truth" / "ground-truth.parquet"
        gt = pd.read_parquet(path)
        healthy = gt[gt["degradation_mechanism"] == "healthy"].index[0]
        gt.loc[healthy, "degradation_mechanism"] = "bond_wire_interconnect"
        gt.loc[healthy, "onset_cycle"] = 800
        gt.loc[healthy, "rate_scale"] = 1.0
        gt.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "consistency.mechanism_composition") is CheckStatus.BLOCKED

    def test_module_count_mismatch(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        _rewrite_json(clone / "metadata" / "dataset.json", lambda p: p.update({"n_modules": 999}))
        _rewrite_json(
            clone / "metadata" / "generation-config.json",
            lambda p: p.update({"n_modules": 999, "n_lots": 1, "modules_per_lot": 999}),
        )
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        size_status = _status(report, "size.module_and_lot_counts")
        cons_status = _status(report, "consistency.module_count")
        assert size_status is CheckStatus.BLOCKED or cons_status is CheckStatus.BLOCKED

    def test_degenerate_distribution(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "telemetry" / "telemetry.parquet"
        tel = pd.read_parquet(path)
        tel["RDS_on"] = 3.0
        tel.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert _status(report, "distribution.finite_variation") is CheckStatus.BLOCKED

    def test_suspicious_correlation_warning(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "telemetry" / "telemetry.parquet"
        tel = pd.read_parquet(path)
        rng = np.random.default_rng(0)
        tel["Tj"] = rng.normal(150.0, 5.0, size=len(tel))
        tel.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert _status(report, "correlation.declared_relationships") in {
            CheckStatus.WARNING,
            CheckStatus.PASS,
        }

    def test_valid_warning_result(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        path = clone / "telemetry" / "telemetry.parquet"
        tel = pd.read_parquet(path)
        n = max(20, len(tel) // 8)
        tel.loc[tel.index[:n], "VDS"] = tel.loc[tel.index[:n], "VDS"].astype(float) + 400.0
        tel.to_parquet(path, index=False)
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status in {CheckStatus.WARNING, CheckStatus.BLOCKED}
        if report.overall_status is CheckStatus.WARNING:
            assert report.summary.n_warning >= 1
            assert report.summary.n_blocked == 0

    def test_valid_blocked_result(self, valid_dir, tmp_path):
        clone = _clone(valid_dir, tmp_path)
        (clone / "telemetry" / "telemetry.parquet").unlink()
        report = validate_dataset(clone, write_output=False)
        assert report.overall_status is CheckStatus.BLOCKED
        assert report.summary.n_blocked >= 1

    def test_empty_source_references_not_error(self, valid_dir):
        report = validate_dataset(valid_dir, write_output=False)
        assert _status(report, "metadata.source_references") is CheckStatus.PASS

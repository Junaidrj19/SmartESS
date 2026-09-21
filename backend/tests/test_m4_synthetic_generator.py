from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from domain.module_profiles.validation import parse_module_profile
from domain.telemetry.models import FORBIDDEN_TELEMETRY_FIELDS, TelemetryRecord
from domain.telemetry.validation import parse_telemetry_record
from domain.test_profiles.validation import parse_test_profile
from ml.generators.synthetic.config import (
    GENERATOR_VERSION,
    GenerationConfig,
    PopulationMix,
    Scenario,
)
from ml.generators.synthetic.generator import generate_dataset, load_profiles
from ml.generators.synthetic.validation import reconstruct_record

REPO = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO / "examples" / "module-profiles" / "sic-reference-module.json"
TEST_PATH = REPO / "examples" / "test-profiles" / "power-cycling-reference.json"


@pytest.fixture(scope="module")
def profiles():
    return load_profiles(MODULE_PATH, TEST_PATH)


def tiny_config(**overrides) -> GenerationConfig:
    payload = {
        "dataset_id": "syn-test-tiny",
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


class TestGenerationConfig:
    def test_defaults(self):
        config = GenerationConfig()
        assert config.n_modules == 750
        assert config.n_lots == 5
        assert config.modules_per_lot == 150
        assert config.observation_stride_cycles == 200
        assert abs(config.population_mix.healthy - 0.70) < 1e-12
        assert config.generator_version == GENERATOR_VERSION

    def test_mix_must_sum_to_one(self):
        with pytest.raises(ValidationError):
            PopulationMix(healthy=0.5, bond_wire_interconnect=0.5, die_attach_thermal_path=0.5, gate_related=0.0)

    def test_n_modules_must_match_lots(self):
        with pytest.raises(ValidationError, match="n_modules"):
            GenerationConfig(n_modules=10, n_lots=3, modules_per_lot=3)

    def test_negative_sigma_rejected(self):
        with pytest.raises(ValidationError):
            GenerationConfig(manufacturing={"lot_sigma_rds_mohm": -0.1})

    def test_unknown_channel_rejected(self):
        with pytest.raises(ValidationError):
            GenerationConfig(include_channels=["RDS_on", "Tj", "not_a_channel"])

    def test_clean_healthy_forces_mix(self):
        config = GenerationConfig(scenario=Scenario.CLEAN_HEALTHY)
        mix = config.effective_mix()
        assert mix.healthy == 1.0
        assert mix.bond_wire_interconnect == 0.0

    def test_t0_must_be_utc(self):
        with pytest.raises(ValidationError):
            GenerationConfig(t0=datetime(2024, 1, 1))


class TestGeneratorInvariants:
    @pytest.fixture(scope="class")
    def benchmark(self, tmp_path_factory, profiles):
        output = tmp_path_factory.mktemp("m4-bench")
        config = tiny_config()
        module, test = profiles
        result = generate_dataset(config, module, test, output)
        return result, config, module, test

    def test_parquet_and_metadata_exist(self, benchmark):
        result, config, _module, _test = benchmark
        root = result.dataset_dir
        assert (root / "telemetry" / "telemetry.parquet").is_file()
        assert (root / "ground_truth" / "ground-truth.parquet").is_file()
        assert (root / "metadata" / "dataset.json").is_file()
        assert (root / "metadata" / "generation-config.json").is_file()
        assert (root / "metadata" / "assumptions.json").is_file()
        assert (root / "provenance" / "provenance.json").is_file()

    def test_counts(self, benchmark):
        result, config, _m, _t = benchmark
        assert result.n_modules == 20
        assert result.n_lots == 2
        assert result.n_ground_truth_records == 20
        assert result.n_telemetry_records == 20 * (4000 // 200 + 1)
        total = sum(result.mechanism_counts.values())
        assert total == 20
        assert result.mechanism_counts["healthy"] == 14
        assert result.mechanism_counts["bond_wire_interconnect"] == 2
        assert result.mechanism_counts["die_attach_thermal_path"] == 2
        assert result.mechanism_counts["gate_related"] == 2

    def test_synthetic_provenance(self, benchmark):
        result, _c, _m, _t = benchmark
        telemetry = pd.read_parquet(result.dataset_dir / "telemetry" / "telemetry.parquet")
        meta = json.loads((result.dataset_dir / "metadata" / "dataset.json").read_text())
        assert (telemetry["data_origin"] == "synthetic").all()
        assert meta["data_origin"] == "synthetic"
        assumptions = json.loads((result.dataset_dir / "metadata" / "assumptions.json").read_text())
        assert "not measured production telemetry" in assumptions["disclaimer"].lower()
        assert assumptions["source_references"] == []

    def test_ground_truth_separated(self, benchmark):
        result, _c, _m, _t = benchmark
        telemetry = pd.read_parquet(result.dataset_dir / "telemetry" / "telemetry.parquet")
        for name in FORBIDDEN_TELEMETRY_FIELDS | {"degradation_mechanism", "onset_cycle", "health_state"}:
            assert name not in telemetry.columns
        gt = pd.read_parquet(result.dataset_dir / "ground_truth" / "ground-truth.parquet")
        assert "degradation_mechanism" in gt.columns
        assert "onset_cycle" in gt.columns
        assert "cycle_measurable" in gt.columns

    def test_utc_and_cycles(self, benchmark):
        result, _c, _m, _t = benchmark
        telemetry = pd.read_parquet(result.dataset_dir / "telemetry" / "telemetry.parquet")
        sample = telemetry.iloc[0]
        parsed = datetime.fromisoformat(str(sample["timestamp"]).replace("Z", "+00:00"))
        assert parsed.tzinfo is not None
        assert parsed.utcoffset().total_seconds() == 0
        for _, group in telemetry.groupby("module_id"):
            cycles = group["cycle_number"].to_numpy()
            assert (cycles[1:] > cycles[:-1]).all()

    def test_manufacturing_variation(self, benchmark):
        result, _c, _m, _t = benchmark
        gt = pd.read_parquet(result.dataset_dir / "ground_truth" / "ground-truth.parquet")
        assert gt["latent_rds_on_ref_mohm"].nunique() > 1
        lot_means = gt.groupby("lot_id")["latent_rds_on_ref_mohm"].mean()
        assert lot_means.nunique() == 2

    def test_not_flat_and_temperature(self, benchmark):
        result, _c, _m, _t = benchmark
        telemetry = pd.read_parquet(result.dataset_dir / "telemetry" / "telemetry.parquet")
        gt = pd.read_parquet(result.dataset_dir / "ground_truth" / "ground-truth.parquet")
        healthy_ids = set(gt.loc[gt["degradation_mechanism"] == "healthy", "module_id"])
        healthy = telemetry[telemetry["module_id"].isin(healthy_ids)]
        assert healthy["RDS_on"].nunique() > len(healthy_ids)
        assert healthy["Tj"].nunique() > 1
        corr = healthy[["RDS_on", "Tj"]].astype(float).corr().iloc[0, 1]
        assert corr > 0.05

    def test_m3_record_compatibility(self, benchmark):
        result, config, _m, _t = benchmark
        telemetry = pd.read_parquet(result.dataset_dir / "telemetry" / "telemetry.parquet")
        payload = reconstruct_record(telemetry.iloc[3], config.include_channels)
        record = parse_telemetry_record(payload)
        assert isinstance(record, TelemetryRecord)
        assert record.provenance.data_origin.value == "synthetic"

    def test_onset_and_stage_order(self, benchmark):
        result, _c, _m, _t = benchmark
        gt = pd.read_parquet(result.dataset_dir / "ground_truth" / "ground-truth.parquet")
        degrading = gt[gt["degradation_mechanism"] != "healthy"]
        assert len(degrading) > 0
        for _, row in degrading.iterrows():
            onset = int(row["onset_cycle"])
            for field in ("cycle_early", "cycle_measurable", "cycle_advanced", "cycle_terminal"):
                value = row[field]
                if pd.notna(value):
                    assert int(value) >= onset

    def test_progressive_not_step(self, benchmark):
        result, _c, _m, _t = benchmark
        telemetry = pd.read_parquet(result.dataset_dir / "telemetry" / "telemetry.parquet")
        gt = pd.read_parquet(result.dataset_dir / "ground_truth" / "ground-truth.parquet")
        bond = gt[gt["degradation_mechanism"] == "bond_wire_interconnect"]
        if bond.empty:
            pytest.skip("no bond-wire module in this seed")
        module_id = bond.iloc[0]["module_id"]
        onset = int(bond.iloc[0]["onset_cycle"])
        series = telemetry[telemetry["module_id"] == module_id].sort_values("cycle_number")
        pre = series[series["cycle_number"] < onset]["RDS_on"].astype(float)
        post = series[series["cycle_number"] > onset]["RDS_on"].astype(float)
        assert len(pre) > 0 and len(post) > 3
        # last post should exceed median pre, and increase is gradual (not a single jump of the whole delta)
        diffs = post.diff().dropna().abs()
        span = float(post.iloc[-1] - pre.median())
        if span > 0.05:
            assert diffs.max() < 0.75 * span


def test_each_mechanism_can_be_generated(tmp_path, profiles):
    module, test = profiles
    mix = PopulationMix(healthy=0.25, bond_wire_interconnect=0.25, die_attach_thermal_path=0.25, gate_related=0.25)
    config = tiny_config(n_modules=8, n_lots=2, modules_per_lot=4, population_mix=mix.model_dump(), seed=99)
    result = generate_dataset(config, module, test, tmp_path)
    gt = pd.read_parquet(result.dataset_dir / "ground_truth" / "ground-truth.parquet")
    present = set(gt["degradation_mechanism"])
    assert present == {
        "healthy",
        "bond_wire_interconnect",
        "die_attach_thermal_path",
        "gate_related",
    }


def test_clean_healthy_only(tmp_path, profiles):
    module, test = profiles
    config = tiny_config(dataset_id="syn-clean", scenario=Scenario.CLEAN_HEALTHY, seed=3)
    result = generate_dataset(config, module, test, tmp_path)
    gt = pd.read_parquet(result.dataset_dir / "ground_truth" / "ground-truth.parquet")
    assert (gt["degradation_mechanism"] == "healthy").all()
    telemetry = pd.read_parquet(result.dataset_dir / "telemetry" / "telemetry.parquet")
    assert (telemetry["RDS_on_status"] == "valid").all()


def test_data_quality_stress_injects_defects(tmp_path, profiles):
    module, test = profiles
    config = tiny_config(
        dataset_id="syn-quality",
        scenario=Scenario.DATA_QUALITY_STRESS,
        seed=21,
        n_modules=12,
        n_lots=2,
        modules_per_lot=6,
        quality={"p_missing": 0.08, "p_duplicate_record": 0.05, "p_invalid": 0.03, "p_spike": 0.02},
    )
    result = generate_dataset(config, module, test, tmp_path)
    telemetry = pd.read_parquet(result.dataset_dir / "telemetry" / "telemetry.parquet")
    status_cols = [c for c in telemetry.columns if c.endswith("_status")]
    stacked = pd.concat([telemetry[c] for c in status_cols], axis=0)
    assert (stacked == "missing").any()
    assert (stacked == "invalid").any()
    assert result.n_telemetry_records >= 12 * (4000 // 200 + 1)


def test_determinism_same_seed(tmp_path, profiles):
    module, test = profiles
    a = tmp_path / "a"
    b = tmp_path / "b"
    config = tiny_config(seed=42, dataset_id="syn-det")
    generate_dataset(config, module, test, a)
    generate_dataset(config, module, test, b)
    tel_a = pd.read_parquet(a / "syn-det" / "telemetry" / "telemetry.parquet")
    tel_b = pd.read_parquet(b / "syn-det" / "telemetry" / "telemetry.parquet")
    gt_a = pd.read_parquet(a / "syn-det" / "ground_truth" / "ground-truth.parquet")
    gt_b = pd.read_parquet(b / "syn-det" / "ground_truth" / "ground-truth.parquet")
    pd.testing.assert_frame_equal(tel_a.reset_index(drop=True), tel_b.reset_index(drop=True), check_exact=True)
    pd.testing.assert_frame_equal(gt_a.reset_index(drop=True), gt_b.reset_index(drop=True), check_exact=True)


def test_different_seeds_differ(tmp_path, profiles):
    module, test = profiles
    r1 = generate_dataset(tiny_config(seed=1, dataset_id="s1"), module, test, tmp_path / "s1")
    r2 = generate_dataset(tiny_config(seed=2, dataset_id="s2"), module, test, tmp_path / "s2")
    a = pd.read_parquet(r1.dataset_dir / "telemetry" / "telemetry.parquet")["RDS_on"].astype(float)
    b = pd.read_parquet(r2.dataset_dir / "telemetry" / "telemetry.parquet")["RDS_on"].astype(float)
    assert not a.equals(b)


def test_sensor_noise_changes_latent_identity(tmp_path, profiles):
    module, test = profiles
    quiet = tiny_config(dataset_id="q", seed=8, sensor_noise={k: 0.0 for k in GenerationConfig().sensor_noise.model_dump()})
    noisy = tiny_config(dataset_id="n", seed=8)
    rq = generate_dataset(quiet, module, test, tmp_path / "q")
    rn = generate_dataset(noisy, module, test, tmp_path / "n")
    vq = pd.read_parquet(rq.dataset_dir / "telemetry" / "telemetry.parquet")["VTH"].astype(float)
    vn = pd.read_parquet(rn.dataset_dir / "telemetry" / "telemetry.parquet")["VTH"].astype(float)
    assert (vq - vn).abs().mean() > 0


def test_wrong_test_type_rejected(tmp_path, profiles):
    module, test = profiles
    raw = json.loads(TEST_PATH.read_text())
    raw["test_type"] = "HTOL"
    raw["htol_configuration"] = {
        "temperature": {"value": 150, "unit": "C"},
        "duration_s": 1000,
    }
    raw.pop("cycle_profile", None)
    htol = parse_test_profile(raw)
    with pytest.raises(ValueError, match="power_cycling"):
        generate_dataset(tiny_config(), module, htol, tmp_path)


def test_profiles_parse_still_work():
    parse_module_profile(json.loads(MODULE_PATH.read_text()))
    parse_test_profile(json.loads(TEST_PATH.read_text()))

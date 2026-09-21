"""Orchestrate M4-B synthetic dataset generation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from domain.module_profiles.models import ModuleProfile
from domain.module_profiles.validation import parse_module_profile
from domain.test_profiles.models import TestProfile
from domain.test_profiles.validation import parse_test_profile
from ml.generators.synthetic.anchors import TypeAnchors, extract_anchors
from ml.generators.synthetic.config import GENERATOR_VERSION, GenerationConfig, Mechanism
from ml.generators.synthetic.degradation import (
    damage_index,
    first_cycle_at_or_above,
    observation_cycles,
    stage_from_severity,
)
from ml.generators.synthetic.ground_truth import build_ground_truth
from ml.generators.synthetic.healthy import ar1_jitter, cycle_stress_jitter, healthy_electrical_jitter
from ml.generators.synthetic.population import ModulePopulation, build_population
from ml.generators.synthetic.provenance import ASSUMPTIONS, dataset_metadata, provenance_document
from ml.generators.synthetic.sensors import DERIVED, UNITS, apply_quality_defects, apply_sensor_model
from ml.generators.synthetic.temperature import conduction_power_W, rds_at_temperature, vth_at_temperature
from ml.generators.synthetic.validation import validate_generated_dataset


def _require_parquet() -> None:
    try:
        import pyarrow  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "Parquet support requires pyarrow. Install the project dependencies "
            "(pip install -e '.[dev]') rather than writing CSV."
        ) from exc


def _profile_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_finite(name: str, array: np.ndarray) -> None:
    if not np.isfinite(array).all():
        raise RuntimeError(f"non-finite values generated in latent array {name}")


@dataclass
class GenerationResult:
    dataset_dir: Path
    n_modules: int
    n_lots: int
    n_telemetry_records: int
    n_ground_truth_records: int
    mechanism_counts: dict[str, int]
    elapsed_s: float


def _latent_fields(
    pop: ModulePopulation,
    config: GenerationConfig,
    anchors: TypeAnchors,
    cycles: np.ndarray,
    rng_healthy: np.random.Generator,
    rng_extra: np.random.Generator,
) -> dict[str, np.ndarray]:
    n_mod = len(pop.module_id)
    n_obs = len(cycles)
    shape = (n_mod, n_obs)
    tm = config.temperature_model
    deg = config.degradation

    d = damage_index(
        cycles,
        pop.onset_cycle,
        span=deg.cycle_span,
        exponent=deg.progression_exponent_p,
        rate_scale=pop.rate_scale,
    )
    if deg.damage_process_sigma > 0:
        d = np.clip(d + rng_extra.normal(0.0, deg.damage_process_sigma, size=shape), 0.0, 1.0)

    rate = pop.rate_scale.reshape(n_mod, 1)
    is_bond = (pop.mechanism == Mechanism.BOND_WIRE_INTERCONNECT.value).reshape(n_mod, 1)
    is_die = (pop.mechanism == Mechanism.DIE_ATTACH_THERMAL_PATH.value).reshape(n_mod, 1)
    is_gate = (pop.mechanism == Mechanism.GATE_RELATED.value).reshape(n_mod, 1)

    id_j, dtj_j, tj_j = cycle_stress_jitter(rng_healthy, shape, config.stress_variation)
    rds_j, vth_j = healthy_electrical_jitter(rng_healthy, shape, config.healthy_jitter)
    tj_wander = ar1_jitter(
        rng_healthy,
        shape,
        sigma=config.healthy_jitter.tj_wander_sigma_C,
        rho=config.healthy_jitter.ar1_rho,
    )

    id_A = anchors.id_A * (1.0 + pop.id_rel_offset.reshape(n_mod, 1)) * (1.0 + id_j)
    id_A = np.clip(id_A, 0.05 * anchors.id_A, 5.0 * anchors.id_A)
    vds = np.broadcast_to(
        anchors.vds_V + pop.vds_offset_V.reshape(n_mod, 1),
        shape,
    ).copy()
    vgs = np.full(shape, anchors.vgs_on_V)
    ta = np.full(shape, anchors.ta_C)

    tj_overshoot = tm.die_attach_tj_overshoot_max_C * d * rate * is_die
    tj = (
        anchors.tj_max_C
        + pop.tj_tracking_offset_C.reshape(n_mod, 1)
        + tj_j
        + tj_wander
        + tj_overshoot
    )
    delta_tj = np.clip(
        anchors.delta_tj_C + pop.delta_tj_offset_C.reshape(n_mod, 1) + dtj_j,
        1.0,
        None,
    )

    rth = pop.rth_jc_C_per_W.reshape(n_mod, 1) * (1.0 + deg.die_attach.gamma_rth * d * rate * is_die)
    rds_ref = pop.rds_on_ref_mohm.reshape(n_mod, 1)
    rds_bond = rds_ref * deg.bond_wire.delta_rds_max_rel * d * rate * is_bond
    rds_die_sec = rds_ref * deg.die_attach.secondary_rds_ref_rel * d * rate * is_die
    vth_shift = pop.gate_shift_sign.reshape(n_mod, 1) * deg.gate.delta_vth_max_V * d * rate * is_gate
    rds_gate = deg.gate.rds_per_vth_mohm * np.abs(vth_shift)

    rds_temp = rds_at_temperature(pop.rds_on_ref_mohm.reshape(n_mod, 1), tj, anchors)
    rds = rds_temp + rds_bond + rds_die_sec + rds_gate + rds_j
    rds = np.clip(rds, 1e-4, None)

    p_sw = tm.p_switching_W
    if anchors.switching_frequency_Hz:
        p_sw = tm.p_switching_W * (anchors.switching_frequency_Hz / 10000.0)
    power = conduction_power_W(id_A, rds) + p_sw
    gap = power * rth * pop.k_th.reshape(n_mod, 1)
    tc = tj - gap

    vth = vth_at_temperature(pop.vth_ref_V.reshape(n_mod, 1), tj, tm) + vth_shift + vth_j
    igss_scale = rng_extra.uniform(0.45, 1.2, size=(n_mod, 1))
    idss_scale = rng_extra.uniform(0.2, 1.0, size=(n_mod, 1))
    igss = pop.igss_base_uA.reshape(n_mod, 1) + deg.gate.igss_delta_uA * d * rate * is_gate * igss_scale
    idss = (
        pop.idss_base_uA.reshape(n_mod, 1)
        + deg.gate.idss_delta_uA * d * rate * is_gate * deg.gate.idss_coupling * idss_scale
        + rng_extra.normal(0.0, 1.5, size=shape) * is_gate
    )
    igss = np.clip(igss, 1e-6, None)
    idss = np.clip(idss, 1e-6, None)

    vds_on = id_A * (rds / 1000.0)
    rds_tref_residual = rds_bond + rds_die_sec + rds_gate
    rds_residual_rel = rds_tref_residual / rds_ref
    rth_increase_rel = (rth / pop.rth_jc_C_per_W.reshape(n_mod, 1)) - 1.0
    vth_shift_abs = np.abs(vth_shift)

    latent = {
        "RDS_on": rds,
        "VTH": vth,
        "IGSS": igss,
        "IDSS": idss,
        "VDS_on": vds_on,
        "Tj": tj,
        "Tc": tc,
        "Ta": ta,
        "Rth": rth,
        "VDS": vds,
        "VGS": vgs,
        "ID": id_A,
        "delta_Tj": delta_tj,
        "electrical_power": power,
        "damage": d,
        "rds_residual_rel": rds_residual_rel,
        "rth_increase_rel": rth_increase_rel,
        "vth_shift_abs": vth_shift_abs,
        "rds_tref_residual": rds_tref_residual,
    }
    include = config.include_channels
    for name, array in latent.items():
        _require_finite(name, array)
        if name in include and array.shape != shape:
            raise RuntimeError(f"latent {name} shape {array.shape} != {shape}")
    return latent


def _timestamps(t0: datetime, cycles: np.ndarray, cycle_duration_s: float, n_mod: int) -> np.ndarray:
    base = cycles.astype(float) * float(cycle_duration_s)
    return np.broadcast_to(base, (n_mod, len(cycles))).copy()


def _flatten_telemetry(
    pop: ModulePopulation,
    config: GenerationConfig,
    observed: dict[str, np.ndarray],
    status: dict[str, np.ndarray],
    timestamps_s: np.ndarray,
    extra_dup: np.ndarray,
    cycles: np.ndarray,
    test_id: str,
) -> pd.DataFrame:
    include = config.include_channels
    n_mod, n_obs = timestamps_s.shape
    copies = []
    for duplicate_pass in (False, True):
        mask = np.ones((n_mod, n_obs), dtype=bool) if not duplicate_pass else extra_dup
        if not mask.any():
            continue
        mi, oi = np.nonzero(mask)
        seconds = timestamps_s[mi, oi]
        ts = pd.to_datetime(config.t0) + pd.to_timedelta(seconds, unit="s")
        ts = ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")
        cyc = cycles[oi].astype(int)
        suffix = "-dup" if duplicate_pass else ""
        telemetry_ids = np.fromiter(
            (
                f"{config.dataset_id}-{pop.module_id[i]}-c{int(c):06d}{suffix}"
                for i, c in zip(mi, cyc)
            ),
            dtype=object,
            count=len(mi),
        )
        data: dict[str, Any] = {
            "schema_version": "1.0.0",
            "telemetry_id": telemetry_ids,
            "module_id": pop.module_id[mi],
            "test_id": test_id,
            "lot_id": pop.lot_id[mi],
            "dataset_id": config.dataset_id,
            "timestamp": ts,
            "cycle_number": cyc,
            "cycle_phase": config.cycle_phase.value,
            "data_origin": "synthetic",
            "source_type": "parquet",
            "source_dataset": config.dataset_id,
            "provenance_notes": (
                "Synthetic development telemetry. Not measured production data. "
                "Generator version " + GENERATOR_VERSION
            ),
        }
        for name in include:
            values = observed[name][mi, oi].astype(float)
            st = status[name][mi, oi].astype(str)
            missing = st == "missing"
            col = values.astype(object)
            col[missing] = None
            data[name] = col
            data[f"{name}_status"] = st
            data[f"{name}_origin"] = ["derived" if name in DERIVED else "measured"] * len(mi)
            data[f"{name}_unit"] = [UNITS[name]] * len(mi)
        copies.append(pd.DataFrame(data))
    frame = pd.concat(copies, ignore_index=True)
    if config.quality_enabled():
        return frame
    return frame.sort_values(["module_id", "cycle_number", "timestamp"], kind="mergesort").reset_index(drop=True)


def generate_dataset(
    config: GenerationConfig,
    module_profile: ModuleProfile,
    test_profile: TestProfile,
    output_root: Path,
    *,
    generated_at: datetime | None = None,
    run_validation: bool = True,
) -> GenerationResult:
    started = datetime.now(timezone.utc)
    _require_parquet()
    generated_at = generated_at or started
    if generated_at.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware UTC")

    tm = config.temperature_model
    anchors = extract_anchors(module_profile, test_profile, t_ref_C=tm.t_ref_C, t_hot_C=150.0)
    target_cycles = config.target_cycles if config.target_cycles is not None else anchors.target_cycles
    if target_cycles < config.observation_stride_cycles:
        raise ValueError("target_cycles must be >= observation_stride_cycles")
    if config.degradation.onset_max_cycle > target_cycles:
        # still allowed: onset clipped at target
        pass

    cycles = observation_cycles(target_cycles, config.observation_stride_cycles)
    root = np.random.default_rng(config.seed)
    pop_rng, healthy_rng, sensor_rng, quality_rng, extra_rng = root.spawn(5)
    population = build_population(config, anchors, pop_rng, target_cycles=target_cycles)
    latent = _latent_fields(population, config, anchors, cycles, healthy_rng, extra_rng)

    include = config.include_channels
    latent_obs = {name: latent[name] for name in include}
    observed, status = apply_sensor_model(latent_obs, config, sensor_rng, include=include)
    timestamps = _timestamps(config.t0, cycles, anchors.cycle_duration_s, len(population.module_id))
    observed, status, timestamps, extra_dup = apply_quality_defects(
        observed, status, timestamps, config, quality_rng, include=include
    )

    telemetry = _flatten_telemetry(
        population, config, observed, status, timestamps, extra_dup, cycles, anchors.test_id
    )

    n_mod = len(population.module_id)
    severity = np.zeros((n_mod, len(cycles)))
    bond = population.mechanism == Mechanism.BOND_WIRE_INTERCONNECT.value
    die = population.mechanism == Mechanism.DIE_ATTACH_THERMAL_PATH.value
    gate = population.mechanism == Mechanism.GATE_RELATED.value
    severity[bond] = latent["rds_residual_rel"][bond]
    severity[die] = latent["rth_increase_rel"][die]
    denom = max(config.degradation.gate.delta_vth_max_V, 1e-9)
    severity[gate] = latent["vth_shift_abs"][gate] / denom

    thr = config.degradation.stage_thresholds
    cycle_early = first_cycle_at_or_above(cycles, severity, 1e-12)
    cycle_early[np.isnan(population.onset_cycle)] = np.nan
    cycle_meas = first_cycle_at_or_above(cycles, severity, thr.measurable)
    cycle_adv = first_cycle_at_or_above(cycles, severity, thr.advanced)
    cycle_term = first_cycle_at_or_above(cycles, severity, thr.terminal)
    stages = stage_from_severity(severity[:, -1], population.onset_cycle, thr)

    gt = build_ground_truth(
        population,
        config,
        module_profile_id=anchors.module_profile_id,
        test_id=anchors.test_id,
        stages_end=list(stages),
        cycle_early=cycle_early,
        cycle_measurable=cycle_meas,
        cycle_advanced=cycle_adv,
        cycle_terminal=cycle_term,
        severity_end=severity[:, -1],
        damage_end=latent["damage"][:, -1],
        rds_ref=population.rds_on_ref_mohm,
        vth_ref=population.vth_ref_V,
        rth_0=population.rth_jc_C_per_W,
        calibration_drift_injected=config.sensor_drift.enabled,
    )

    counts = {mech.value: int((population.mechanism == mech.value).sum()) for mech in Mechanism}
    module_hash = _profile_hash(module_profile.model_dump(mode="json"))
    test_hash = _profile_hash(test_profile.model_dump(mode="json"))
    meta = dataset_metadata(
        config,
        generated_at=generated_at.astimezone(timezone.utc),
        module_profile_id=anchors.module_profile_id,
        module_profile_hash=module_hash,
        test_profile_id=anchors.test_id,
        test_profile_hash=test_hash,
        n_telemetry_rows=len(telemetry),
        n_modules=n_mod,
        n_lots=config.n_lots,
        n_observations_per_module=len(cycles),
        mechanism_counts=counts,
        target_cycles=target_cycles,
    )
    prov = provenance_document(meta, config)

    dataset_dir = Path(output_root) / config.dataset_id
    (dataset_dir / "metadata").mkdir(parents=True, exist_ok=True)
    (dataset_dir / "telemetry").mkdir(parents=True, exist_ok=True)
    (dataset_dir / "ground_truth").mkdir(parents=True, exist_ok=True)
    (dataset_dir / "provenance").mkdir(parents=True, exist_ok=True)

    telemetry_path = dataset_dir / "telemetry" / "telemetry.parquet"
    gt_path = dataset_dir / "ground_truth" / "ground-truth.parquet"
    telemetry.to_parquet(telemetry_path, index=False)
    gt.to_parquet(gt_path, index=False)

    config_payload = json.loads(config.model_dump_json())
    (dataset_dir / "metadata" / "generation-config.json").write_text(
        json.dumps(config_payload, indent=2) + "\n", encoding="utf-8"
    )
    (dataset_dir / "metadata" / "dataset.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    (dataset_dir / "metadata" / "assumptions.json").write_text(
        json.dumps(ASSUMPTIONS, indent=2) + "\n", encoding="utf-8"
    )
    (dataset_dir / "provenance" / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n", encoding="utf-8")

    if run_validation:
        validate_generated_dataset(
            dataset_dir,
            config=config,
            module_profile=module_profile,
            test_profile=test_profile,
            target_cycles=target_cycles,
            n_obs_nominal=len(cycles),
            latent_end_severity=severity[:, -1],
            population_mechanisms=population.mechanism,
            population_onset=population.onset_cycle,
            population_module_ids=population.module_id,
        )

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    return GenerationResult(
        dataset_dir=dataset_dir,
        n_modules=n_mod,
        n_lots=config.n_lots,
        n_telemetry_records=len(telemetry),
        n_ground_truth_records=len(gt),
        mechanism_counts=counts,
        elapsed_s=elapsed,
    )


def load_profiles(module_path: Path, test_path: Path) -> tuple[ModuleProfile, TestProfile]:
    module = parse_module_profile(json.loads(module_path.read_text(encoding="utf-8")))
    test = parse_test_profile(json.loads(test_path.read_text(encoding="utf-8")))
    return module, test


def generate_from_paths(
    config: GenerationConfig,
    module_profile_path: Path,
    test_profile_path: Path,
    output_root: Path,
    **kwargs: Any,
) -> GenerationResult:
    module, test = load_profiles(module_profile_path, test_profile_path)
    return generate_dataset(config, module, test, output_root, **kwargs)

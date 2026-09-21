"""Dataset provenance and assumption catalogs.

Source references remain empty until verified external evidence is ingested.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ml.generators.synthetic.config import GENERATOR_VERSION, GenerationConfig


ASSUMPTIONS: dict[str, Any] = {
    "disclaimer": (
        "This dataset is synthetic and intended for development, benchmarking, and "
        "validation of SmartESS analytical pipelines. It is not measured production "
        "telemetry. Trajectories are not experimentally validated semiconductor physics."
    ),
    "engineering_rationale_qualitative": [
        {
            "id": "rds_increases_with_tj",
            "class": "A_engineering_fact_qualitative",
            "statement": "In typical on-state operating ranges, SiC MOSFET RDS(on) increases as junction temperature increases. The coefficient is device-specific.",
        },
        {
            "id": "vth_typically_falls_with_tj",
            "class": "A_engineering_fact_qualitative",
            "statement": "MOSFET threshold voltage typically decreases as temperature increases.",
        },
        {
            "id": "conduction_loss_i2r",
            "class": "A_engineering_fact_qualitative",
            "statement": "Conduction dissipation scales with I_D^2 * RDS(on).",
        },
        {
            "id": "lumped_heating",
            "class": "A_engineering_fact_qualitative",
            "statement": "Dissipated power raises junction temperature above case through a thermal path.",
        },
        {
            "id": "lot_vs_module_variation",
            "class": "A_engineering_fact_qualitative",
            "statement": "Manufacturing lots often share systematic offsets; units within a lot still differ.",
        },
        {
            "id": "power_cycling_fatigue_class",
            "class": "A_engineering_fact_qualitative",
            "statement": "Power cycling is a known stress class for interconnect and die-attach fatigue. This does not validate the injected numeric signatures.",
        },
    ],
    "simulation_assumptions": [
        {
            "id": "population_mix",
            "class": "B_simulation_assumption",
            "statement": "Class fractions are a benchmark choice, not field prevalence.",
        },
        {
            "id": "onset_uniform",
            "class": "B_simulation_assumption",
            "statement": "Degradation onset is drawn uniformly on a configured cycle window, not from a Weibull field model.",
        },
        {
            "id": "manufacturing_sigmas",
            "class": "B_simulation_assumption",
            "statement": "Lot/module Gaussian widths are convenience values so variation is visible but smaller than degradation amplitudes.",
        },
        {
            "id": "alpha_vth",
            "class": "B_simulation_assumption",
            "statement": "VTH temperature coefficient is a configurable default, not a measured SiC parameter.",
        },
        {
            "id": "bond_wire_rds_residual",
            "class": "B_simulation_assumption",
            "statement": "Bond-wire/interconnect category injects a T_ref RDS residual. Increased RDS(on) does not prove bond-wire failure.",
        },
        {
            "id": "die_attach_rth",
            "class": "B_simulation_assumption",
            "statement": "Die-attach/thermal-path category increases effective Rth. Candidate signature, not a diagnosis.",
        },
        {
            "id": "gate_under_power_cycling",
            "class": "B_simulation_assumption",
            "statement": "Gate-related signatures under power cycling are a simulation choice so detectors can be tested against package signatures. Power cycling is not uniquely a gate-oxide test. This category may be revised if evidence does not support the intended use.",
        },
        {
            "id": "single_primary_mechanism",
            "class": "B_simulation_assumption",
            "statement": "v1 assigns one primary injected mechanism per degrading module.",
        },
        {
            "id": "lifetime_not_predicted",
            "class": "B_simulation_assumption",
            "statement": "Onset is assigned, not predicted from a calibrated Coffin-Manson/LESIT model of delta_Tj.",
        },
        {
            "id": "sensor_sigmas",
            "class": "B_simulation_assumption",
            "statement": "Measurement noise widths are not from a calibrated instrument datasheet.",
        },
    ],
    "mathematical_approximations": [
        {
            "id": "linear_rds_temperature_map",
            "class": "C_mathematical_approximation",
            "statement": "RDS(on)(Tj) linearly interpolates two ModuleProfile typicals and scales by the module reference. Domain: configured T_ref to hot typical, with linear extrapolation outside. Not a universal MOSFET law.",
        },
        {
            "id": "linear_vth_temperature",
            "class": "C_mathematical_approximation",
            "statement": "VTH(Tj) = VTH_ref + alpha * (Tj - T_ref).",
        },
        {
            "id": "lumped_rth",
            "class": "C_mathematical_approximation",
            "statement": "Tj ≈ Tc + P * Rth_jc with P ≈ I^2 R + P_sw. Not a Cauer/Foster identification or FEM.",
        },
        {
            "id": "ohms_law_vdson",
            "class": "C_mathematical_approximation",
            "statement": "VDS(on) ≈ ID * RDS(on) in ohms, plus sensor noise.",
        },
        {
            "id": "power_law_damage",
            "class": "C_mathematical_approximation",
            "statement": "d(c) = clip(((c - onset)/span)^p, 0, 1). p is a convenience exponent, not a fatigue exponent.",
        },
        {
            "id": "gaussian_measurement_noise",
            "class": "C_mathematical_approximation",
            "statement": "Additive Gaussian measurement noise on latent values.",
        },
        {
            "id": "closed_loop_tj_targeting",
            "class": "C_mathematical_approximation",
            "statement": "Power-cycling Tj follows TestProfile setpoints plus tracking error rather than a free-running thermal ODE.",
        },
    ],
    "synthetic_ground_truth": [
        {
            "id": "injected_labels",
            "class": "D_synthetic_ground_truth",
            "statement": "Mechanism, onset, stages, and severity are simulator labels for evaluation. They are not laboratory failure analysis.",
        }
    ],
    "unverified_benchmark_parameters": [
        {
            "id": "illustrative_module_profile_values",
            "class": "E_unverified_default",
            "statement": "Numeric ModuleProfile/TestProfile anchors come from illustrative_reference examples, not a verified datasheet extraction.",
        }
    ],
    "source_references": [],
    "evidence_note": "No verified external sources have been ingested. Do not invent citations.",
}


MECHANISM_MODELS = {
    "healthy_v1": "No injected degradation; manufacturing, temperature, stress jitter, and sensors only.",
    "bond_wire_v1": "Progressive T_ref RDS residual, VDS(on) and conduction loss coupling. Simulation signature, not a diagnosis.",
    "die_attach_v1": "Progressive Rth increase, Tj-Tc gap change, optional modest Tj overshoot; RDS at T_ref nearly unchanged. Simulation signature, not a diagnosis.",
    "gate_related_v1": "Progressive VTH shift and IGSS increase with weaker IDSS coupling. Simulation choice under power cycling, not unique oxide proof.",
}


def dataset_metadata(
    config: GenerationConfig,
    *,
    generated_at: datetime,
    module_profile_id: str,
    module_profile_hash: str,
    test_profile_id: str,
    test_profile_hash: str,
    n_telemetry_rows: int,
    n_modules: int,
    n_lots: int,
    n_observations_per_module: int,
    mechanism_counts: dict[str, int],
    target_cycles: int,
) -> dict[str, Any]:
    return {
        "dataset_id": config.dataset_id,
        "data_origin": "synthetic",
        "disclaimer": ASSUMPTIONS["disclaimer"],
        "scenario": config.scenario.value,
        "generator_version": GENERATOR_VERSION,
        "generation_timestamp": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "random_seed": config.seed,
        "module_profile_id": module_profile_id,
        "module_profile_version": "1.0.0",
        "module_profile_hash": module_profile_hash,
        "test_profile_id": test_profile_id,
        "test_profile_version": "1.0.0",
        "test_profile_hash": test_profile_hash,
        "schema_version_module_profile": "1.0.0",
        "schema_version_test_profile": "1.0.0",
        "schema_version_telemetry": "1.0.0",
        "n_modules": n_modules,
        "n_lots": n_lots,
        "n_telemetry_records": n_telemetry_rows,
        "n_observations_per_module_nominal": n_observations_per_module,
        "target_cycles": target_cycles,
        "observation_stride_cycles": config.observation_stride_cycles,
        "mechanism_counts": mechanism_counts,
        "mechanism_counts_note": "Simulation allocation, not failure prevalence.",
        "population_mix_configured": config.effective_mix().model_dump(),
    }


def provenance_document(
    metadata: dict[str, Any],
    config: GenerationConfig,
) -> dict[str, Any]:
    return {
        **metadata,
        "generation_config_file": "metadata/generation-config.json",
        "assumptions_file": "metadata/assumptions.json",
        "mechanism_models": MECHANISM_MODELS,
        "source_references": [],
        "rng": {
            "library": "numpy.random.Generator",
            "policy": "root seed -> spawn(population, degradation-unused, healthy, sensor, quality); lots spawned from population stream so adding a later lot does not reshuffle earlier lots",
        },
        "timestamp_model": (
            "UTC t = t0 + cycle_number * TestProfile.cycle_duration_s "
            "(plus quality-scenario jitter/jumps when enabled). "
            "observation_stride_cycles is the dataset cadence and is not TestProfile.sampling_interval_s."
        ),
        "notes": config.notes,
    }

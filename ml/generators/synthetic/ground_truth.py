"""Ground-truth table construction. Evaluation only — never telemetry."""

from __future__ import annotations

import pandas as pd

from ml.generators.synthetic.config import GENERATOR_VERSION, GenerationConfig, HealthState, Mechanism
from ml.generators.synthetic.population import ModulePopulation


def mechanism_model_id(mechanism: str, config: GenerationConfig) -> str:
    if mechanism == Mechanism.BOND_WIRE_INTERCONNECT.value:
        return config.degradation.bond_wire.model_id
    if mechanism == Mechanism.DIE_ATTACH_THERMAL_PATH.value:
        return config.degradation.die_attach.model_id
    if mechanism == Mechanism.GATE_RELATED.value:
        return config.degradation.gate.model_id
    return "healthy_v1"


def build_ground_truth(
    population: ModulePopulation,
    config: GenerationConfig,
    *,
    module_profile_id: str,
    test_id: str,
    stages_end: list[str],
    cycle_early,
    cycle_measurable,
    cycle_advanced,
    cycle_terminal,
    severity_end,
    damage_end,
    rds_ref,
    vth_ref,
    rth_0,
    calibration_drift_injected: bool,
) -> pd.DataFrame:
    n = len(population.module_id)
    health = []
    for i in range(n):
        mech = population.mechanism[i]
        stage = stages_end[i]
        if mech == Mechanism.HEALTHY.value:
            health.append(HealthState.HEALTHY.value)
        elif stage == "terminal":
            health.append(HealthState.TERMINAL.value)
        else:
            health.append(HealthState.DEGRADING.value)

    onset = []
    rate = []
    for i in range(n):
        if population.mechanism[i] == Mechanism.HEALTHY.value:
            onset.append(None)
            rate.append(None)
        else:
            onset.append(int(population.onset_cycle[i]))
            rate.append(float(population.rate_scale[i]))

    def _opt_cycle(values, i):
        value = values[i]
        if value != value:  # NaN
            return None
        return int(value)

    rows = {
        "module_id": population.module_id,
        "lot_id": population.lot_id,
        "module_profile_id": module_profile_id,
        "test_id": test_id,
        "health_state": health,
        "degradation_mechanism": population.mechanism,
        "degradation_stage": stages_end,
        "onset_cycle": onset,
        "cycle_early": [_opt_cycle(cycle_early, i) for i in range(n)],
        "cycle_measurable": [_opt_cycle(cycle_measurable, i) for i in range(n)],
        "cycle_advanced": [_opt_cycle(cycle_advanced, i) for i in range(n)],
        "cycle_terminal": [_opt_cycle(cycle_terminal, i) for i in range(n)],
        "terminal_cycle": [_opt_cycle(cycle_terminal, i) for i in range(n)],
        "degradation_severity": [float(severity_end[i]) for i in range(n)],
        "damage_index_end": [float(damage_end[i]) for i in range(n)],
        "rate_scale": rate,
        "simulation_seed": config.seed,
        "generator_version": GENERATOR_VERSION,
        "mechanism_model": [mechanism_model_id(m, config) for m in population.mechanism],
        "generation_assumptions": "assumptions.json",
        "latent_rds_on_ref_mohm": rds_ref,
        "latent_vth_ref_V": vth_ref,
        "latent_rth_jc_C_per_W": rth_0,
        "calibration_drift_injected": calibration_drift_injected,
        "dataset_id": config.dataset_id,
        "scenario": config.scenario.value,
        "data_origin": "synthetic",
    }
    return pd.DataFrame(rows)

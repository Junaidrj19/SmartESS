"""Observation layer: latent state plus measurement effects.

Quality defects apply only when the scenario enables them.
Missing samples use status=missing and no numeric value (never zero).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ml.generators.synthetic.config import GenerationConfig, QuantizationConfig

CHANNEL_NAMES = (
    "RDS_on",
    "VTH",
    "IGSS",
    "IDSS",
    "VDS_on",
    "Tj",
    "Tc",
    "Ta",
    "Rth",
    "VDS",
    "VGS",
    "ID",
    "delta_Tj",
    "electrical_power",
)

DERIVED = frozenset({"RDS_on", "VDS_on", "delta_Tj", "electrical_power", "Rth"})

UNITS = {
    "RDS_on": "mOhm",
    "VTH": "V",
    "IGSS": "uA",
    "IDSS": "uA",
    "VDS_on": "V",
    "Tj": "C",
    "Tc": "C",
    "Ta": "C",
    "Rth": "C_per_W",
    "VDS": "V",
    "VGS": "V",
    "ID": "A",
    "delta_Tj": "C",
    "electrical_power": "W",
}


@dataclass
class ObservedArrays:
    values: dict[str, np.ndarray]
    status: dict[str, np.ndarray]
    timestamps_s: np.ndarray
    duplicate_of: np.ndarray | None = None


def _quantize(values: np.ndarray, step: float) -> np.ndarray:
    return np.round(values / step) * step


def apply_sensor_model(
    latent: dict[str, np.ndarray],
    config: GenerationConfig,
    rng: np.random.Generator,
    *,
    include: list[str],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    n_mod, n_obs = next(iter(latent.values())).shape
    noise_map = config.sensor_noise.sigma_map()
    bias_map = config.sensor_bias.sigma_map()
    observed: dict[str, np.ndarray] = {}
    status: dict[str, np.ndarray] = {}
    drift = config.sensor_drift
    cycle_frac = np.linspace(0.0, 1.0, n_obs).reshape(1, n_obs)

    for name in include:
        base = latent[name]
        sigma_n = noise_map.get(name, 0.0)
        sigma_b = bias_map.get(name, 0.0)
        bias = rng.normal(0.0, sigma_b, size=(n_mod, 1))
        noise = rng.normal(0.0, sigma_n, size=base.shape)
        values = base + bias + noise
        if drift.enabled:
            if name == "RDS_on":
                values = values + drift.rds_mohm_over_test * cycle_frac
            elif name == "VTH":
                values = values + drift.vth_V_over_test * cycle_frac
        observed[name] = values
        status[name] = np.full(base.shape, "valid", dtype=object)

    q = config.quantization
    if q.enabled:
        for name in include:
            if name in {"Tj", "Tc", "Ta", "delta_Tj"}:
                observed[name] = _quantize(observed[name], q.temperature_C)
            elif name == "RDS_on":
                observed[name] = _quantize(observed[name], q.rds_mohm)

    return observed, status


def apply_quality_defects(
    observed: dict[str, np.ndarray],
    status: dict[str, np.ndarray],
    timestamps_s: np.ndarray,
    config: GenerationConfig,
    rng: np.random.Generator,
    *,
    include: list[str],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], np.ndarray, np.ndarray]:
    """Returns observed, status, timestamps, extra_duplicate_mask (n_mod, n_obs)."""

    n_mod, n_obs = timestamps_s.shape
    quality = config.quality
    extra_dup = np.zeros((n_mod, n_obs), dtype=bool)

    if not config.quality_enabled():
        return observed, status, timestamps_s, extra_dup

    jitter = rng.normal(0.0, quality.timestamp_jitter_s, size=timestamps_s.shape)
    timestamps_s = timestamps_s + jitter

    jump_mask = rng.random(size=(n_mod, n_obs)) < quality.p_time_jump
    timestamps_s = timestamps_s + jump_mask * quality.time_jump_seconds

    for name in include:
        miss = rng.random(size=(n_mod, n_obs)) < quality.p_missing
        drop_start = rng.random(size=(n_mod, n_obs)) < quality.p_dropout
        if quality.dropout_run_length > 1:
            for lag in range(1, quality.dropout_run_length):
                shifted = np.zeros_like(drop_start)
                shifted[:, lag:] = drop_start[:, :-lag]
                miss = miss | drop_start | shifted
        else:
            miss = miss | drop_start

        invalid = rng.random(size=(n_mod, n_obs)) < quality.p_invalid
        spike = rng.random(size=(n_mod, n_obs)) < quality.p_spike
        sigma = config.sensor_noise.sigma_map().get(name, 1.0) or 1.0
        observed[name] = observed[name] + spike * rng.choice([-1.0, 1.0], size=(n_mod, n_obs)) * quality.spike_sigma_mult * sigma

        invalid_values = observed[name] + rng.choice([-1.0, 1.0], size=(n_mod, n_obs)) * 1.0e4
        observed[name] = np.where(invalid & ~miss, invalid_values, observed[name])

        st = np.array(status[name], dtype=object, copy=True)
        st[spike & ~miss & ~invalid] = "valid"
        st[invalid & ~miss] = "invalid"
        st[miss] = "missing"
        status[name] = st

    extra_dup = rng.random(size=(n_mod, n_obs)) < quality.p_duplicate_record
    return observed, status, timestamps_s, extra_dup

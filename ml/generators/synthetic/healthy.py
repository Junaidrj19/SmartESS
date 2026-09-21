"""Healthy temporal processes (stationary jitter).

Healthy means no injected mechanism, not a perfectly flat line.
"""

from __future__ import annotations

import numpy as np

from ml.generators.synthetic.config import HealthyJitterConfig, StressVariationConfig


def ar1_jitter(
    rng: np.random.Generator,
    shape: tuple[int, int],
    *,
    sigma: float,
    rho: float,
) -> np.ndarray:
    n_mod, n_obs = shape
    eps = rng.normal(0.0, sigma, size=shape)
    if n_obs == 0 or sigma == 0:
        return eps
    out = np.empty(shape, dtype=float)
    out[:, 0] = eps[:, 0]
    scale = np.sqrt(max(1.0 - rho * rho, 1e-12))
    for t in range(1, n_obs):
        out[:, t] = rho * out[:, t - 1] + scale * eps[:, t]
    return out


def cycle_stress_jitter(
    rng: np.random.Generator,
    shape: tuple[int, int],
    stress: StressVariationConfig,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    id_j = rng.normal(0.0, stress.cycle_id_rel_sigma, size=shape)
    dtj_j = rng.normal(0.0, stress.cycle_delta_tj_sigma_C, size=shape)
    tj_j = rng.normal(0.0, stress.cycle_tj_sigma_C, size=shape)
    return id_j, dtj_j, tj_j


def healthy_electrical_jitter(
    rng: np.random.Generator,
    shape: tuple[int, int],
    config: HealthyJitterConfig,
) -> tuple[np.ndarray, np.ndarray]:
    rds = ar1_jitter(rng, shape, sigma=config.rds_sigma_mohm, rho=config.ar1_rho)
    vth = ar1_jitter(rng, shape, sigma=config.vth_sigma_V, rho=config.ar1_rho)
    return rds, vth

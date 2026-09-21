"""Progressive degradation residuals and stage labeling.

Simulation categories, not field prevalence or confirmed diagnoses.
v1 assigns one primary mechanism per degrading module.
"""

from __future__ import annotations

import numpy as np

from ml.generators.synthetic.config import DegradationConfig, DegradationStage, Mechanism


def observation_cycles(target_cycles: int, stride: int) -> np.ndarray:
    return np.arange(0, target_cycles + 1, stride, dtype=np.int64)


def damage_index(
    cycles: np.ndarray,
    onset: np.ndarray,
    *,
    span: int,
    exponent: float,
    rate_scale: np.ndarray,
) -> np.ndarray:
    """d in [0, 1] after onset; 0 before onset / for healthy (onset NaN)."""

    n_mod = onset.shape[0]
    n_obs = cycles.shape[0]
    onset_col = onset.reshape(n_mod, 1)
    healthy = np.isnan(onset_col)
    elapsed = cycles.reshape(1, n_obs) - onset_col
    elapsed = np.where(healthy | (elapsed < 0), 0.0, elapsed)
    scaled = elapsed / float(span)
    damage = np.clip(scaled**exponent, 0.0, 1.0)
    return damage


def first_cycle_at_or_above(cycles: np.ndarray, severity: np.ndarray, threshold: float) -> np.ndarray:
    """Per module, first observation cycle where severity >= threshold; NaN if never."""

    n_mod, _n_obs = severity.shape
    crossed = severity >= threshold
    result = np.full(n_mod, np.nan)
    any_cross = crossed.any(axis=1)
    first_idx = np.argmax(crossed, axis=1)
    result[any_cross] = cycles[first_idx[any_cross]].astype(float)
    return result


def mechanism_severity(
    *,
    mechanism: np.ndarray,
    damage: np.ndarray,
    rate_scale: np.ndarray,
    rds_residual_rel: np.ndarray,
    rth_increase_rel: np.ndarray,
    vth_shift_abs: np.ndarray,
    config: DegradationConfig,
) -> np.ndarray:
    """Latent severity used for stage labels (pre-sensor)."""

    n_mod, n_obs = damage.shape
    rate = rate_scale.reshape(n_mod, 1)
    s = np.zeros((n_mod, n_obs), dtype=float)
    bond = mechanism == Mechanism.BOND_WIRE_INTERCONNECT.value
    die = mechanism == Mechanism.DIE_ATTACH_THERMAL_PATH.value
    gate = mechanism == Mechanism.GATE_RELATED.value
    s[bond] = rds_residual_rel[bond]
    s[die] = rth_increase_rel[die]
    s[gate] = vth_shift_abs[gate] / max(config.gate.delta_vth_max_V, 1e-9)
    return s


def stage_from_severity(severity_end: np.ndarray, onset: np.ndarray, thresholds) -> np.ndarray:
    stages = np.full(severity_end.shape[0], DegradationStage.HEALTHY.value, dtype=object)
    started = ~np.isnan(onset)
    stages[started] = DegradationStage.EARLY.value
    stages[started & (severity_end >= thresholds.measurable)] = DegradationStage.MEASURABLE.value
    stages[started & (severity_end >= thresholds.advanced)] = DegradationStage.ADVANCED.value
    stages[started & (severity_end >= thresholds.terminal)] = DegradationStage.TERMINAL.value
    stages[~started] = DegradationStage.HEALTHY.value
    return stages.astype(str)

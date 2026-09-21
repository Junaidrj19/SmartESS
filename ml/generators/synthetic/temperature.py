"""Temperature and lumped thermal maps.

RDS(on)(Tj) uses linear interpolation between ModuleProfile typicals.
VTH(T) uses a configurable linear coefficient.
Tj ≈ Tc + P * Rth is a single-lump cycle-level approximation.

None of these are validated universal SiC MOSFET laws.
"""

from __future__ import annotations

import numpy as np

from ml.generators.synthetic.anchors import TypeAnchors
from ml.generators.synthetic.config import TemperatureModelConfig


def rds_type_ratio(tj_C: np.ndarray, anchors: TypeAnchors) -> np.ndarray:
    """R_type(Tj) / R_type(T_ref), piecewise-linear through the two typicals."""

    t0 = anchors.t_ref_C
    t1 = anchors.t_hot_C
    r0 = anchors.rds_ref_mohm
    r1 = anchors.rds_hot_mohm
    slope = (r1 - r0) / (t1 - t0)
    r_type = r0 + slope * (tj_C - t0)
    return r_type / r0


def rds_at_temperature(rds_ref_mohm: np.ndarray, tj_C: np.ndarray, anchors: TypeAnchors) -> np.ndarray:
    return rds_ref_mohm * rds_type_ratio(tj_C, anchors)


def vth_at_temperature(
    vth_ref_V: np.ndarray,
    tj_C: np.ndarray,
    config: TemperatureModelConfig,
) -> np.ndarray:
    return vth_ref_V + config.alpha_vth_V_per_C * (tj_C - config.t_ref_C)


def conduction_power_W(id_A: np.ndarray, rds_mohm: np.ndarray) -> np.ndarray:
    rds_ohm = rds_mohm / 1000.0
    return (id_A**2) * rds_ohm

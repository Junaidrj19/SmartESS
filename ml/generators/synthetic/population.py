"""Module population, lot assignment, and manufacturing variation.

Lot vs module offsets exist so later evaluation can test lot-level generalization.
Quantitative σ values are simulation assumptions, not measured yield data.

A shared lot/module quality factor correlates RDS(on) and Rth in the same
direction. VTH uses an independent factor. Leakages share a weak leakage factor.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ml.generators.synthetic.anchors import TypeAnchors
from ml.generators.synthetic.config import GenerationConfig, Mechanism, PopulationMix


@dataclass
class ModulePopulation:
    module_id: np.ndarray
    lot_id: np.ndarray
    mechanism: np.ndarray
    rds_on_ref_mohm: np.ndarray
    vth_ref_V: np.ndarray
    igss_base_uA: np.ndarray
    idss_base_uA: np.ndarray
    rth_jc_C_per_W: np.ndarray
    k_th: np.ndarray
    id_rel_offset: np.ndarray
    vds_offset_V: np.ndarray
    delta_tj_offset_C: np.ndarray
    tj_tracking_offset_C: np.ndarray
    onset_cycle: np.ndarray
    rate_scale: np.ndarray
    gate_shift_sign: np.ndarray
    module_index: np.ndarray


def largest_remainder_counts(n: int, mix: PopulationMix) -> dict[Mechanism, int]:
    mapping = mix.as_mechanism_map()
    raw = {mech: frac * n for mech, frac in mapping.items()}
    counts = {mech: int(np.floor(value)) for mech, value in raw.items()}
    remainder = n - sum(counts.values())
    order = sorted(raw, key=lambda mech: (raw[mech] - counts[mech], mech.value), reverse=True)
    for mech in order[:remainder]:
        counts[mech] += 1
    return counts


def _assign_mechanisms(config: GenerationConfig, mix: PopulationMix) -> np.ndarray:
    n = config.n_modules
    lot_size = config.modules_per_lot
    assigned = np.empty(n, dtype=object)
    if config.stratify_mix_by_lot:
        offset = 0
        for _lot in range(config.n_lots):
            counts = largest_remainder_counts(lot_size, mix)
            cursor = offset
            for mech in Mechanism:
                k = counts[mech]
                assigned[cursor : cursor + k] = mech.value
                cursor += k
            offset += lot_size
        return assigned.astype(str)
    counts = largest_remainder_counts(n, mix)
    cursor = 0
    for mech in Mechanism:
        k = counts[mech]
        assigned[cursor : cursor + k] = mech.value
        cursor += k
    return assigned.astype(str)


def _align_cycle(value: int, stride: int, target: int) -> int:
    aligned = int(round(value / stride) * stride)
    aligned = max(0, min(target, aligned))
    return aligned


def build_population(
    config: GenerationConfig,
    anchors: TypeAnchors,
    rng: np.random.Generator,
    *,
    target_cycles: int,
) -> ModulePopulation:
    n = config.n_modules
    mix = config.effective_mix()
    mechanisms = _assign_mechanisms(config, mix)

    lot_ids = np.empty(n, dtype=object)
    module_ids = np.empty(n, dtype=object)
    idx = 0
    for lot_i in range(config.n_lots):
        lot_name = f"lot-{lot_i + 1:02d}"
        for _j in range(config.modules_per_lot):
            lot_ids[idx] = lot_name
            module_ids[idx] = f"syn-mod-{idx + 1:04d}"
            idx += 1

    pop_streams = rng.spawn(config.n_lots)
    lot_quality = np.empty(n)
    lot_vth = np.empty(n)
    lot_leak = np.empty(n)
    mod_quality = np.empty(n)
    mod_vth = np.empty(n)
    mod_leak = np.empty(n)
    k_th = np.empty(n)
    id_rel = np.empty(n)
    vds_off = np.empty(n)
    dtj_off = np.empty(n)
    tj_off = np.empty(n)
    onset = np.empty(n)
    rate = np.empty(n)
    gate_sign = np.empty(n)

    man = config.manufacturing
    stress = config.stress_variation
    deg = config.degradation
    stride = config.observation_stride_cycles

    idx = 0
    for lot_i, lot_rng in enumerate(pop_streams):
        lq = float(lot_rng.normal())
        lv = float(lot_rng.normal())
        ll = float(lot_rng.normal())
        module_rngs = lot_rng.spawn(config.modules_per_lot)
        for j in range(config.modules_per_lot):
            mr = module_rngs[j]
            mq = float(mr.normal())
            mv = float(mr.normal())
            ml = float(mr.normal())
            lot_quality[idx] = lq
            lot_vth[idx] = lv
            lot_leak[idx] = ll
            mod_quality[idx] = mq
            mod_vth[idx] = mv
            mod_leak[idx] = ml
            k_th[idx] = max(0.7, 1.0 + man.module_sigma_k_th * float(mr.normal()))
            id_rel[idx] = float(mr.normal() * stress.id_rel_sigma)
            vds_off[idx] = float(mr.normal() * stress.vds_sigma_V)
            dtj_off[idx] = float(mr.normal() * stress.delta_tj_sigma_C)
            tj_off[idx] = float(mr.normal() * stress.tj_tracking_sigma_C)
            if mechanisms[idx] == Mechanism.HEALTHY.value:
                onset[idx] = np.nan
                rate[idx] = 1.0
                gate_sign[idx] = 0.0
            else:
                raw_onset = int(mr.integers(deg.onset_min_cycle, deg.onset_max_cycle + 1))
                onset[idx] = _align_cycle(raw_onset, stride, target_cycles)
                rate[idx] = float(mr.lognormal(mean=0.0, sigma=deg.rate_scale_lognormal_sigma))
                gate_sign[idx] = 1.0 if mr.random() < 0.5 else -1.0
            idx += 1

    rds = anchors.rds_ref_mohm + man.lot_sigma_rds_mohm * lot_quality + man.module_sigma_rds_mohm * mod_quality
    rth = anchors.rth_jc_C_per_W + man.lot_sigma_rth_C_per_W * lot_quality + man.module_sigma_rth_C_per_W * mod_quality
    vth = anchors.vth_ref_V + man.lot_sigma_vth_V * lot_vth + man.module_sigma_vth_V * mod_vth
    igss = anchors.igss_base_uA + man.lot_sigma_igss_uA * lot_leak + man.module_sigma_igss_uA * mod_leak
    idss = anchors.idss_base_uA + man.lot_sigma_idss_uA * lot_leak + man.module_sigma_idss_uA * mod_leak

    rds = np.clip(rds, 0.2 * anchors.rds_ref_mohm, 3.0 * anchors.rds_ref_mohm)
    rth = np.clip(rth, 0.3 * anchors.rth_jc_C_per_W, 3.0 * anchors.rth_jc_C_per_W)
    vth = np.clip(vth, 0.5, 6.0)
    igss = np.clip(igss, 1e-5, 1e3)
    idss = np.clip(idss, 1e-4, 1e5)

    return ModulePopulation(
        module_id=module_ids.astype(str),
        lot_id=lot_ids.astype(str),
        mechanism=mechanisms,
        rds_on_ref_mohm=rds.astype(float),
        vth_ref_V=vth.astype(float),
        igss_base_uA=igss.astype(float),
        idss_base_uA=idss.astype(float),
        rth_jc_C_per_W=rth.astype(float),
        k_th=k_th.astype(float),
        id_rel_offset=id_rel.astype(float),
        vds_offset_V=vds_off.astype(float),
        delta_tj_offset_C=dtj_off.astype(float),
        tj_tracking_offset_C=tj_off.astype(float),
        onset_cycle=onset.astype(float),
        rate_scale=rate.astype(float),
        gate_shift_sign=gate_sign.astype(float),
        module_index=np.arange(n, dtype=int),
    )

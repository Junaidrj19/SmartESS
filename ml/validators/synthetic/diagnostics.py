"""Statistical, correlation, temperature, degradation, and mechanism diagnostics."""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from ml.generators.synthetic.config import Mechanism
from ml.validators.synthetic.constants import DISTRIBUTION_SIGNALS
from ml.validators.synthetic.loader import LoadedDataset
from ml.validators.synthetic.models import CheckCategory, CheckResult, CheckSeverity, make_check
from ml.validators.synthetic.stats import (
    attach_ground_truth,
    channel_values,
    cohens_d,
    first_per_module,
    last_per_module,
    mad_z_outlier_rate,
    pearson,
    valid_mask,
)


def check_distribution(loaded: LoadedDataset) -> list[CheckResult]:
    tel = loaded.telemetry
    gt = loaded.ground_truth
    if tel is None:
        return [
            make_check(
                "distribution.prerequisites",
                CheckCategory.DISTRIBUTION,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="Cannot run distribution checks without telemetry.",
            )
        ]
    metrics: dict[str, Any] = {}
    degenerate = []
    low_var = []
    high_outliers = []
    blocked_outliers = []
    for name in DISTRIBUTION_SIGNALS:
        if name not in tel.columns:
            continue
        values = channel_values(tel, name)
        if len(values) < 10:
            continue
        nunique = int(np.unique(np.round(values, 12)).size)
        var = float(np.var(values))
        out = mad_z_outlier_rate(values)
        metrics[name] = {
            "n": int(len(values)),
            "mean": float(np.mean(values)),
            "std": float(np.std(values)),
            "nunique": nunique,
            "outlier_rate_mad8": out,
        }
        expected_variation = name not in {"VGS"}  # VGS is a held setpoint plus small noise
        if expected_variation and nunique <= 1:
            degenerate.append(name)
        elif expected_variation and var == 0.0:
            degenerate.append(name)
        elif expected_variation and metrics[name]["std"] < 1e-12 * max(abs(metrics[name]["mean"]), 1.0):
            low_var.append(name)
        if out > 0.25:
            blocked_outliers.append(name)
        elif out > 0.05:
            high_outliers.append(name)

    checks = [
        make_check(
            "distribution.finite_variation",
            CheckCategory.DISTRIBUTION,
            CheckSeverity.BLOCKING,
            failed=bool(degenerate),
            pass_message="Important signals have nonzero variation where the simulator injects it.",
            fail_message=f"Degenerate distributions (no variation): {degenerate}",
            metrics={"signals": metrics, "degenerate": degenerate},
        ),
        make_check(
            "distribution.suspicious_or_outliers",
            CheckCategory.DISTRIBUTION,
            CheckSeverity.BLOCKING if blocked_outliers else CheckSeverity.WARNING,
            failed=bool(high_outliers or blocked_outliers or low_var),
            pass_message="Distributions are finite with reasonable outlier rates for a simulation.",
            fail_message=(
                f"Suspicious distributions: low_var={low_var} outlier_warning={high_outliers} "
                f"outlier_blocked={blocked_outliers}"
            ),
            metrics={"low_variance": low_var, "outlier_warning": high_outliers, "outlier_blocked": blocked_outliers},
        ),
    ]

    sep_fail = False
    sep_warn = False
    sep_metrics: dict[str, Any] = {}
    if gt is not None and "degradation_mechanism" in gt.columns and "RDS_on" in tel.columns:
        last = last_per_module(tel)
        last = attach_ground_truth(last, gt, ["degradation_mechanism", "onset_cycle", "rate_scale", "degradation_stage"])
        healthy = last["degradation_mechanism"].astype(str).eq(Mechanism.HEALTHY.value)
        bond = last["degradation_mechanism"].astype(str).eq(Mechanism.BOND_WIRE_INTERCONNECT.value)
        if int(healthy.sum()) >= 3 and int(bond.sum()) >= 2 and valid_mask(last, "RDS_on").any():
            h = pd.to_numeric(last.loc[healthy, "RDS_on"], errors="coerce").to_numpy(dtype=float)
            b = pd.to_numeric(last.loc[bond, "RDS_on"], errors="coerce").to_numpy(dtype=float)
            d = cohens_d(b, h)
            sep_metrics["rds_bond_vs_healthy_cohens_d"] = d
            if d is not None and abs(d) < 0.02:
                sep_warn = True
            if d is not None and d < -1.5:
                sep_warn = True
        groups = last.groupby("degradation_mechanism")
        means = {}
        for mech, part in groups:
            if "RDS_on" in part.columns:
                vals = pd.to_numeric(part["RDS_on"], errors="coerce").to_numpy(dtype=float)
                means[str(mech)] = float(np.nanmean(vals))
        if len(means) >= 2:
            vector = np.array(list(means.values()), dtype=float)
            if float(np.std(vector)) == 0.0:
                sep_fail = True
            sep_metrics["last_cycle_rds_means"] = means
    checks.append(
        make_check(
            "distribution.healthy_degraded_separation",
            CheckCategory.DISTRIBUTION,
            CheckSeverity.BLOCKING if sep_fail else CheckSeverity.WARNING,
            failed=sep_fail or sep_warn,
            pass_message="Mechanism groups are not completely identical on last-cycle RDS_on.",
            fail_message=f"Healthy/degraded groups look collapsed or inverted: {sep_metrics}",
            metrics=sep_metrics,
        )
    )
    return checks


def check_correlations(loaded: LoadedDataset) -> list[CheckResult]:
    tel = loaded.telemetry
    gt = loaded.ground_truth
    if tel is None:
        return [
            make_check(
                "correlation.prerequisites",
                CheckCategory.CORRELATION,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="Cannot run correlation checks without telemetry.",
            )
        ]
    frame = tel
    if gt is not None and "degradation_mechanism" in gt.columns:
        frame = attach_ground_truth(tel, gt, ["degradation_mechanism"])
        healthy = frame["degradation_mechanism"].astype(str).eq(Mechanism.HEALTHY.value)
        hframe = frame.loc[healthy] if healthy.any() else frame
    else:
        hframe = frame

    pairs = [
        ("Tj", "RDS_on", "positive", "tj_rds"),
        ("ID", "electrical_power", "positive", "id_power"),
        ("RDS_on", "electrical_power", "positive", "rds_power"),
    ]
    metrics: dict[str, Any] = {}
    absent = []
    perfect = []
    for a, b, expected, key in pairs:
        if a not in hframe.columns or b not in hframe.columns:
            continue
        mask = valid_mask(hframe, a) & valid_mask(hframe, b)
        r = pearson(
            pd.to_numeric(hframe.loc[mask, a], errors="coerce").to_numpy(dtype=float),
            pd.to_numeric(hframe.loc[mask, b], errors="coerce").to_numpy(dtype=float),
        )
        metrics[key] = r
        if r is None:
            continue
        if abs(r) > 0.9995 and key != "id_power":
            # ID vs power can be strong; RDS vs Tj should not be a perfect line after sensor noise.
            if key == "tj_rds":
                perfect.append(key)
        if expected == "positive" and r < -0.05:
            absent.append(key)
        if expected == "positive" and r < 0.02 and key in {"tj_rds", "id_power"}:
            absent.append(key)

    cycle_r = None
    if gt is not None and "RDS_on" in tel.columns and "cycle_number" in tel.columns:
        healthy_ids = set(gt.loc[gt["degradation_mechanism"].astype(str).eq(Mechanism.HEALTHY.value), "module_id"].astype(str))
        htel = tel[tel["module_id"].astype(str).isin(healthy_ids)]
        mask = valid_mask(htel, "RDS_on")
        cycle_r = pearson(
            pd.to_numeric(htel.loc[mask, "cycle_number"], errors="coerce").to_numpy(dtype=float),
            pd.to_numeric(htel.loc[mask, "RDS_on"], errors="coerce").to_numpy(dtype=float),
        )
        metrics["healthy_rds_vs_cycle"] = cycle_r
        if cycle_r is not None and abs(cycle_r) > 0.999:
            perfect.append("healthy_rds_vs_cycle")

    blocked = False
    warn = bool(absent or perfect)
    return [
        make_check(
            "correlation.declared_relationships",
            CheckCategory.CORRELATION,
            CheckSeverity.BLOCKING if blocked else CheckSeverity.WARNING,
            failed=warn,
            pass_message="Declared simulation relationships are present and not suspiciously perfect.",
            fail_message=f"Correlation diagnostics: absent={absent} suspiciously_perfect={perfect} r={metrics}",
            metrics={"correlations": metrics, "absent": absent, "perfect": perfect},
        )
    ]


def check_temperature_confounding(loaded: LoadedDataset) -> list[CheckResult]:
    tel = loaded.telemetry
    gt = loaded.ground_truth
    if tel is None or gt is None or "Tj" not in tel.columns or "RDS_on" not in tel.columns:
        return [
            make_check(
                "temperature.prerequisites",
                CheckCategory.TEMPERATURE_CONFOUNDING,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="Temperature-confounding check requires telemetry Tj, RDS_on, and ground truth.",
            )
        ]
    last = attach_ground_truth(
        last_per_module(tel),
        gt,
        ["degradation_mechanism", "onset_cycle", "rate_scale", "degradation_stage"],
    )
    healthy = last["degradation_mechanism"].astype(str).eq(Mechanism.HEALTHY.value)
    degraded = ~healthy
    checks: list[CheckResult] = []

    htel = attach_ground_truth(tel, gt, ["degradation_mechanism"])
    hmask = htel["degradation_mechanism"].astype(str).eq(Mechanism.HEALTHY.value)
    hobs = htel.loc[hmask]
    mask = valid_mask(hobs, "Tj") & valid_mask(hobs, "RDS_on")
    r = pearson(
        pd.to_numeric(hobs.loc[mask, "Tj"], errors="coerce").to_numpy(dtype=float),
        pd.to_numeric(hobs.loc[mask, "RDS_on"], errors="coerce").to_numpy(dtype=float),
    )
    rds_tj_fail = r is not None and r < 0.0
    rds_tj_block = r is not None and r < -0.3
    checks.append(
        make_check(
            "temperature.healthy_rds_vs_tj",
            CheckCategory.TEMPERATURE_CONFOUNDING,
            CheckSeverity.BLOCKING if rds_tj_block else CheckSeverity.WARNING,
            failed=rds_tj_fail,
            pass_message=f"Healthy RDS_on increases with Tj as the declared temperature map intends (r={r}).",
            fail_message=f"Healthy RDS_on vs Tj relationship is missing or inverted (r={r}).",
            metrics={"pearson_rds_tj_healthy": r},
        )
    )

    tj_h = pd.to_numeric(last.loc[healthy, "Tj"], errors="coerce").to_numpy(dtype=float) if int(healthy.sum()) else np.array([])
    tj_d = pd.to_numeric(last.loc[degraded, "Tj"], errors="coerce").to_numpy(dtype=float) if int(degraded.sum()) else np.array([])
    d_tj = cohens_d(tj_d, tj_h) if len(tj_h) and len(tj_d) else None
    trivial = False
    blocked = False
    if len(tj_h) >= 3 and len(tj_d) >= 3:
        if float(np.max(tj_h)) < float(np.min(tj_d)) or float(np.max(tj_d)) < float(np.min(tj_h)):
            trivial = True
            blocked = True
        if d_tj is not None and abs(d_tj) > 3.5:
            trivial = True
            # strong temperature shift can still be usable if overlap exists
            overlap = not (
                float(np.quantile(tj_h, 0.9)) < float(np.quantile(tj_d, 0.1))
                or float(np.quantile(tj_d, 0.9)) < float(np.quantile(tj_h, 0.1))
            )
            blocked = blocked or not overlap
    per_mech = {}
    for mech, part in last.groupby("degradation_mechanism"):
        vals = pd.to_numeric(part["Tj"], errors="coerce").to_numpy(dtype=float)
        per_mech[str(mech)] = {"mean_tj": float(np.nanmean(vals)), "n": int(len(part))}
    checks.append(
        make_check(
            "temperature.mechanism_not_just_tj",
            CheckCategory.TEMPERATURE_CONFOUNDING,
            CheckSeverity.BLOCKING if blocked else CheckSeverity.WARNING,
            failed=trivial,
            pass_message="Mechanism labels are not trivially recoverable from temperature alone.",
            fail_message=(
                "Degradation labels appear trivially encoded as high/low Tj. "
                "The dataset is unusable as a temperature-conditioned degradation benchmark."
                if blocked
                else "Temperature differs strongly by mechanism group; labels may be partly recoverable from Tj."
            ),
            metrics={"cohens_d_tj_degraded_vs_healthy": d_tj, "group_tj": per_mech, "non_overlapping": blocked},
        )
    )
    return checks


def _signal_for_mechanism(mech: str) -> Optional[str]:
    if mech == Mechanism.BOND_WIRE_INTERCONNECT.value:
        return "RDS_on"
    if mech == Mechanism.DIE_ATTACH_THERMAL_PATH.value:
        return "Rth"
    if mech == Mechanism.GATE_RELATED.value:
        return "IGSS"
    return None


def check_degradation(loaded: LoadedDataset) -> list[CheckResult]:
    tel = loaded.telemetry
    gt = loaded.ground_truth
    if tel is None or gt is None:
        return [
            make_check(
                "degradation.prerequisites",
                CheckCategory.DEGRADATION,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="Cannot validate degradation trajectories without telemetry and ground truth.",
            )
        ]
    merged = attach_ground_truth(tel, gt, ["degradation_mechanism", "onset_cycle", "rate_scale", "degradation_stage"])
    first = attach_ground_truth(first_per_module(tel), gt, ["degradation_mechanism", "onset_cycle", "rate_scale", "degradation_stage"])
    last = attach_ground_truth(last_per_module(tel), gt, ["degradation_mechanism", "onset_cycle", "rate_scale", "degradation_stage"])
    cycles_by_mod = tel.groupby("module_id")["cycle_number"].agg(["min", "max"])

    onset_outside = []
    for _, row in gt.iterrows():
        mech = str(row["degradation_mechanism"])
        if mech == Mechanism.HEALTHY.value:
            continue
        mid = str(row["module_id"])
        onset = row["onset_cycle"]
        if pd.isna(onset) or mid not in cycles_by_mod.index:
            onset_outside.append(mid)
            continue
        cmin, cmax = cycles_by_mod.loc[mid]
        if int(onset) < int(cmin) or int(onset) > int(cmax):
            onset_outside.append(mid)

    checks = [
        make_check(
            "degradation.onset_within_trajectory",
            CheckCategory.DEGRADATION,
            CheckSeverity.BLOCKING,
            failed=bool(onset_outside),
            pass_message="Degrading-module onset occurs within the observed cycle trajectory.",
            fail_message=f"Onset outside observed cycles for {onset_outside[:10]}",
            affected_modules=onset_outside,
            metrics={"n_outside": len(onset_outside)},
        )
    ]

    jump_mods = []
    no_progress = []
    pre_onset_mods = []
    healthy_damage = []
    rate_var: dict[str, Any] = {}
    for mech in (
        Mechanism.BOND_WIRE_INTERCONNECT.value,
        Mechanism.DIE_ATTACH_THERMAL_PATH.value,
        Mechanism.GATE_RELATED.value,
        Mechanism.HEALTHY.value,
    ):
        signal = _signal_for_mechanism(mech) or "RDS_on"
        if signal not in merged.columns:
            continue
        part = merged[merged["degradation_mechanism"].astype(str).eq(mech)]
        mods = part["module_id"].astype(str).unique()
        if mech != Mechanism.HEALTHY.value and "rate_scale" in gt.columns:
            rates = pd.to_numeric(gt.loc[gt["degradation_mechanism"].astype(str).eq(mech), "rate_scale"], errors="coerce")
            rate_var[mech] = {"nunique": int(rates.nunique()), "std": float(rates.std()) if len(rates) else 0.0}
        for mid in mods:
            g = part[part["module_id"].astype(str).eq(mid)].sort_values("cycle_number")
            mask = valid_mask(g, signal)
            g = g.loc[mask]
            if len(g) < 3:
                continue
            values = pd.to_numeric(g[signal], errors="coerce").to_numpy(dtype=float)
            cycles = pd.to_numeric(g["cycle_number"], errors="coerce").to_numpy(dtype=float)
            onset = g["onset_cycle"].iloc[0]
            if mech == Mechanism.HEALTHY.value:
                rel = abs(values[-1] - values[0]) / max(abs(values[0]), 1e-9)
                # Healthy modules should not carry a degradation-sized residual on Rth/IGSS/RDS beyond temperature.
                if signal == "Rth" and rel > 0.25:
                    healthy_damage.append(mid)
                continue
            if pd.isna(onset):
                continue
            onset_f = float(onset)
            pre = values[cycles < onset_f]
            post = values[cycles >= onset_f]
            # Raw RDS_on tracks temperature before onset by design; only check
            # mechanism-primary channels that are not the healthy temperature map.
            if len(pre) >= 2 and signal in {"Rth", "IGSS"}:
                pre_span = abs(pre[-1] - pre[0])
                full_span = abs(values[-1] - values[0])
                scale = max(abs(float(values[0])), 1e-9)
                if full_span > 0.08 * scale and pre_span > 0.90 * full_span:
                    pre_onset_mods.append(mid)
            if len(post) >= 2:
                steps = np.diff(post)
                net = abs(post[-1] - post[0])
                scale = max(abs(float(post[0])), 1e-9)
                max_step = float(np.max(np.abs(steps)))
                # A true one-cycle jump: net change is large and almost entirely one step.
                # max_step > net indicates oscillation/noise, not an abrupt residual.
                if (
                    net > 0.12 * scale
                    and len(post) > 8
                    and max_step <= 1.02 * net
                    and max_step > 0.95 * net
                ):
                    jump_mods.append(mid)
                if net < 0.02 * scale:
                    progressed = True
                elif mech == Mechanism.GATE_RELATED.value:
                    progressed = True
                else:
                    progressed = post[-1] + 0.02 * scale >= post[0]
                if not progressed:
                    no_progress.append(mid)

    checks.append(
        make_check(
            "degradation.pre_onset_and_progression",
            CheckCategory.DEGRADATION,
            CheckSeverity.WARNING if (pre_onset_mods or no_progress) and not jump_mods else CheckSeverity.BLOCKING if jump_mods else CheckSeverity.WARNING,
            failed=bool(pre_onset_mods or no_progress or jump_mods),
            pass_message="Degradation residuals begin after onset and progress over multiple cycles.",
            fail_message=(
                f"Trajectory issues: pre_onset={pre_onset_mods[:8]} no_progress={no_progress[:8]} "
                f"one_cycle_jump={jump_mods[:8]}"
            ),
            metrics={
                "pre_onset": pre_onset_mods[:20],
                "no_progress": no_progress[:20],
                "one_cycle_jump": jump_mods[:20],
            },
            affected_modules=(pre_onset_mods + no_progress + jump_mods)[:25],
        )
    )
    # Refine: one-cycle jump is BLOCKED; pre-onset/no-progress WARNING unless jump.
    if jump_mods:
        checks[-1] = make_check(
            "degradation.pre_onset_and_progression",
            CheckCategory.DEGRADATION,
            CheckSeverity.BLOCKING,
            failed=True,
            pass_message="",
            fail_message=f"Degradation consists of an abrupt one-cycle jump for modules {jump_mods[:8]}.",
            metrics={"one_cycle_jump": jump_mods[:20], "pre_onset": pre_onset_mods[:20], "no_progress": no_progress[:20]},
            affected_modules=jump_mods[:25],
        )

    rate_fail = False
    rate_warn = False
    for mech, info in rate_var.items():
        if info["nunique"] <= 1 and info.get("std", 0) == 0 and loaded.generation_config:
            sigma = float(((loaded.generation_config.get("degradation") or {}).get("rate_scale_lognormal_sigma") or 0))
            n = int((gt["degradation_mechanism"].astype(str).eq(mech)).sum())
            if sigma > 0 and n >= 3:
                rate_warn = True
    checks.append(
        make_check(
            "degradation.rate_heterogeneity",
            CheckCategory.DEGRADATION,
            CheckSeverity.WARNING,
            failed=rate_warn or rate_fail,
            pass_message="Module-specific rate_scale varies where the lognormal model is configured.",
            fail_message=f"rate_scale is identical across degrading modules despite configured sigma: {rate_var}",
            metrics=rate_var,
        )
    )
    checks.append(
        make_check(
            "degradation.healthy_without_injected_residual",
            CheckCategory.DEGRADATION,
            CheckSeverity.WARNING,
            failed=bool(healthy_damage),
            pass_message="Healthy modules do not show large Rth residuals characteristic of die-attach injection.",
            fail_message=f"Healthy modules show large Rth change: {healthy_damage[:8]}",
            affected_modules=healthy_damage,
        )
    )
    _ = first, last
    return checks


def check_mechanism_diagnostics(loaded: LoadedDataset) -> list[CheckResult]:
    tel = loaded.telemetry
    gt = loaded.ground_truth
    if tel is None or gt is None:
        return [
            make_check(
                "mechanism.prerequisites",
                CheckCategory.MECHANISM,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="Cannot run mechanism diagnostics without telemetry and ground truth.",
            )
        ]
    last = attach_ground_truth(
        last_per_module(tel),
        gt,
        ["degradation_mechanism", "onset_cycle", "rate_scale", "degradation_stage"],
    )
    features = [c for c in ("RDS_on", "VTH", "IGSS", "Rth", "Tj") if c in last.columns]
    group_stats: dict[str, Any] = {}
    for mech, part in last.groupby("degradation_mechanism"):
        entry = {"n": int(len(part))}
        for feat in features:
            vals = pd.to_numeric(part[feat], errors="coerce").to_numpy(dtype=float)
            entry[feat] = {"mean": float(np.nanmean(vals)), "median": float(np.nanmedian(vals))}
        group_stats[str(mech)] = entry

    indistinguishable = False
    if len(group_stats) >= 2:
        for feat in features:
            means = [group_stats[m][feat]["mean"] for m in group_stats if feat in group_stats[m]]
            if len(means) >= 2 and float(np.std(means)) == 0.0:
                indistinguishable = True

    std_diffs: dict[str, Any] = {}
    mechs = [m for m in group_stats if m != Mechanism.HEALTHY.value]
    for mech in mechs:
        if Mechanism.HEALTHY.value not in group_stats:
            continue
        std_diffs[mech] = {}
        for feat in features:
            a = pd.to_numeric(last.loc[last["degradation_mechanism"].astype(str).eq(mech), feat], errors="coerce").to_numpy(dtype=float)
            b = pd.to_numeric(last.loc[last["degradation_mechanism"].astype(str).eq(Mechanism.HEALTHY.value), feat], errors="coerce").to_numpy(dtype=float)
            std_diffs[mech][feat] = cohens_d(a, b)

    trivial = []
    for feat in features:
        if feat == "Tj":
            continue
        series = last[feat]
        mech = last["degradation_mechanism"].astype(str)
        if series.nunique(dropna=True) == mech.nunique():
            per = last.groupby("degradation_mechanism")[feat].nunique()
            if bool((per == 1).all()):
                trivial.append(feat)

    failed = indistinguishable or bool(trivial)
    return [
        make_check(
            "mechanism.separability_diagnostic",
            CheckCategory.MECHANISM,
            CheckSeverity.WARNING,
            failed=failed,
            pass_message=(
                "Mechanism groups show simulated differences on last-cycle summaries. "
                "This is not a classifier and does not declare identification success."
            ),
            fail_message=(
                f"Mechanisms look indistinguishable or trivially separated by one column "
                f"(indistinguishable={indistinguishable}, trivial={trivial})."
            ),
            metrics={"group_stats": group_stats, "standardized_differences": std_diffs, "trivial_columns": trivial},
        )
    ]

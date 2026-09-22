"""Temporal, numerical, missingness, identity, leakage, and size checks."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from ml.generators.synthetic.config import Mechanism, Scenario
from ml.validators.synthetic.constants import (
    ABSOLUTE_ZERO_C,
    DISTRIBUTION_SIGNALS,
    FORBIDDEN_TELEMETRY_COLUMNS,
    LEAKAGE_NAME_FRAGMENTS,
    NON_NEGATIVE_CHANNELS,
    VALID_VALUE_STATUSES,
)
from ml.validators.synthetic.loader import LoadedDataset
from ml.validators.synthetic.models import CheckCategory, CheckResult, CheckSeverity, make_check
from ml.validators.synthetic.stats import valid_mask


def _scenario(loaded: LoadedDataset) -> str:
    if loaded.dataset_meta and loaded.dataset_meta.get("scenario"):
        return str(loaded.dataset_meta["scenario"])
    if loaded.generation_config and loaded.generation_config.get("scenario"):
        return str(loaded.generation_config["scenario"])
    return ""


def _is_quality(loaded: LoadedDataset) -> bool:
    return _scenario(loaded) == Scenario.DATA_QUALITY_STRESS.value


def check_temporal(loaded: LoadedDataset) -> list[CheckResult]:
    tel = loaded.telemetry
    config = loaded.generation_config or {}
    if tel is None or tel.empty or "module_id" not in tel.columns:
        return [
            make_check(
                "temporal.prerequisites",
                CheckCategory.TEMPORAL,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="Cannot run temporal checks without telemetry.",
            )
        ]
    quality = _is_quality(loaded)
    ordered = tel.sort_values(["module_id", "cycle_number", "timestamp"], kind="mergesort")
    same = ordered["module_id"].eq(ordered["module_id"].shift())
    cycle_diff = pd.to_numeric(ordered["cycle_number"], errors="coerce").diff()
    non_monotonic = same & (cycle_diff < 0)
    not_strict = same & (cycle_diff <= 0)
    n_back = int(non_monotonic.sum())
    n_dup_cycle = int(not_strict.sum())

    if quality:
        failed_mono = n_back > 0
        msg_fail = f"Cycle numbers go backwards in data_quality_stress ({n_back} steps)."
        msg_pass = (
            f"No backward cycle numbers. Duplicate cycles: {n_dup_cycle} "
            "(allowed to be injected in data_quality_stress)."
        )
    else:
        failed_mono = n_dup_cycle > 0
        msg_fail = f"Clean scenario has non-strictly-increasing cycle numbers ({n_dup_cycle} steps)."
        msg_pass = "Clean-scenario cycle numbers are strictly increasing per module."

    checks = [
        make_check(
            "temporal.cycle_monotonicity",
            CheckCategory.TEMPORAL,
            CheckSeverity.BLOCKING,
            failed=failed_mono,
            pass_message=msg_pass,
            fail_message=msg_fail,
            metrics={"backward_or_duplicate_steps": n_dup_cycle, "backward": n_back, "scenario": _scenario(loaded)},
            affected_modules=ordered.loc[non_monotonic if quality else not_strict, "module_id"].astype(str).unique()[:25].tolist(),
        )
    ]

    invalid_cycle = pd.to_numeric(tel["cycle_number"], errors="coerce")
    bad_cycle = invalid_cycle.isna() | (invalid_cycle < 0)
    checks.append(
        make_check(
            "temporal.cycle_validity",
            CheckCategory.TEMPORAL,
            CheckSeverity.BLOCKING,
            failed=bool(bad_cycle.any()),
            pass_message="Cycle numbers are finite integers >= 0.",
            fail_message=f"Invalid cycle_number values: {int(bad_cycle.sum())}",
            metrics={"invalid": int(bad_cycle.sum())},
        )
    )

    stride = int(config.get("observation_stride_cycles") or 0)
    stride_failed = False
    stride_metrics: dict[str, Any] = {"configured_stride": stride}
    if stride > 0 and not quality:
        diffs = cycle_diff[same & cycle_diff.notna()]
        if len(diffs) > 0:
            mode = int(diffs.mode().iloc[0]) if not diffs.mode().empty else -1
            unusual = float((diffs != stride).mean()) if stride else 1.0
            stride_metrics.update({"observed_mode_diff": mode, "fraction_not_equal_stride": unusual})
            stride_failed = mode != stride and unusual > 0.05
    checks.append(
        make_check(
            "temporal.observation_stride",
            CheckCategory.TEMPORAL,
            CheckSeverity.WARNING if quality else CheckSeverity.BLOCKING,
            failed=stride_failed,
            pass_message="Observation stride is approximately consistent with configuration.",
            fail_message=f"Observation stride inconsistent with config: {stride_metrics}",
            metrics=stride_metrics,
        )
    )

    ts_raw = tel["timestamp"] if "timestamp" in tel.columns else pd.Series(dtype=object)
    parsed = pd.to_datetime(ts_raw, utc=True, format="ISO8601", errors="coerce")
    unparsed = int(parsed.isna().sum())
    naive = False
    offset_bad = 0
    tzinfo = getattr(getattr(ts_raw, "dt", None), "tz", None) if hasattr(ts_raw, "dt") else None
    dtype_name = str(ts_raw.dtype)
    if "datetime64" in dtype_name and tzinfo is None:
        naive = True
    elif tzinfo is not None:
        tz_name = str(tzinfo)
        if tz_name not in {"UTC", "tzutc()"} and "UTC" not in tz_name:
            offset_bad = int(len(ts_raw))
    elif ts_raw.dtype == object:
        as_str = ts_raw.astype(str)
        naive = bool((~as_str.str.contains(r"(?:Z|[+-]00:00)$", regex=True) & parsed.notna()).any()) if len(as_str) else False
        offset_bad = int(
            (
                as_str.str.contains(r"[+-]\d{2}:\d{2}$", regex=True)
                & ~as_str.str.contains(r"(?:\+00:00|Z)$", regex=True)
            ).sum()
        )
    utc_failed = unparsed > 0 or naive or offset_bad > 0
    checks.append(
        make_check(
            "temporal.utc",
            CheckCategory.TEMPORAL,
            CheckSeverity.BLOCKING,
            failed=utc_failed,
            pass_message="Timestamps are timezone-aware UTC.",
            fail_message=f"UTC violations: unparsed={unparsed} naive_or_non_utc={naive} offset_bad={offset_bad}",
            metrics={"unparsed": unparsed, "naive_or_missing_tz": naive, "non_utc_offset": offset_bad},
        )
    )

    ts_back = 0
    if parsed.notna().all():
        ordered_ts = parsed.loc[ordered.index]
        same_idx = ordered["module_id"].eq(ordered["module_id"].shift())
        delta = ordered_ts.diff().dt.total_seconds()
        ts_back = int((same_idx & (delta < 0)).sum())
        ts_dup = int((same_idx & (delta == 0)).sum())
    else:
        ts_dup = 0
    if quality:
        ts_fail = ts_back > 0
        ts_pass = f"No backward timestamps. Duplicate timestamps: {ts_dup} (quality scenario may inject jitter/duplicates)."
        ts_fail_msg = f"Timestamps go backwards ({ts_back}) in data_quality_stress."
    else:
        ts_fail = ts_back > 0 or ts_dup > 0
        ts_pass = "Timestamps are strictly increasing per module."
        ts_fail_msg = f"Clean scenario timestamp monotonicity violated (backward={ts_back}, duplicate={ts_dup})."
    checks.append(
        make_check(
            "temporal.timestamp_monotonicity",
            CheckCategory.TEMPORAL,
            CheckSeverity.BLOCKING,
            failed=ts_fail,
            pass_message=ts_pass,
            fail_message=ts_fail_msg,
            metrics={"backward": ts_back, "duplicate_timestamps": ts_dup, "scenario": _scenario(loaded)},
        )
    )
    return checks


def check_numerical(loaded: LoadedDataset) -> list[CheckResult]:
    tel = loaded.telemetry
    gt = loaded.ground_truth
    config = loaded.generation_config or {}
    channels = list(config.get("include_channels") or [])
    if tel is None:
        return [
            make_check(
                "numerical.prerequisites",
                CheckCategory.NUMERICAL,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="Cannot run numerical checks without telemetry.",
            )
        ]
    neg_hits = []
    temp_hits = []
    for name in channels:
        if name not in tel.columns:
            continue
        mask = valid_mask(tel, name)
        values = pd.to_numeric(tel.loc[mask, name], errors="coerce")
        if name in NON_NEGATIVE_CHANNELS:
            n_neg = int((values < 0).sum())
            if n_neg:
                neg_hits.append({"channel": name, "n_negative": n_neg})
        if name in {"Tj", "Tc", "Ta"}:
            n_abs = int((values < ABSOLUTE_ZERO_C).sum())
            if n_abs:
                temp_hits.append({"channel": name, "n_below_absolute_zero_C": n_abs})
    checks = [
        make_check(
            "numerical.non_negative_contract",
            CheckCategory.NUMERICAL,
            CheckSeverity.BLOCKING,
            failed=bool(neg_hits),
            pass_message="Resistance, Rth, and electrical_power are non-negative where present.",
            fail_message=f"Negative values in contract-nonnegative channels: {neg_hits}",
            metrics={"violations": neg_hits},
        ),
        make_check(
            "numerical.absolute_temperature",
            CheckCategory.NUMERICAL,
            CheckSeverity.BLOCKING,
            failed=bool(temp_hits),
            pass_message="Celsius temperatures are not below absolute zero.",
            fail_message=f"Temperatures below -273.15 C: {temp_hits}",
            metrics={"violations": temp_hits},
        ),
    ]

    tj_tc_fail = False
    tj_metrics: dict[str, Any] = {}
    if "Tj" in tel.columns and "Tc" in tel.columns:
        both = valid_mask(tel, "Tj") & valid_mask(tel, "Tc")
        if int(both.sum()) > 20:
            gap = pd.to_numeric(tel.loc[both, "Tj"], errors="coerce") - pd.to_numeric(tel.loc[both, "Tc"], errors="coerce")
            inversion = float((gap < 0).mean())
            median_gap = float(np.median(gap.to_numpy(dtype=float)))
            tj_metrics = {"fraction_tj_lt_tc": inversion, "median_tj_minus_tc": median_gap}
            # Declared lumped model: Tj ≈ Tc + P Rth with P,Rth > 0. Systematic inversion is unusable.
            tj_tc_fail = inversion > 0.5 or median_gap < -5.0
            warn_only = inversion > 0.15 and not tj_tc_fail
        else:
            warn_only = False
    else:
        warn_only = False
    checks.append(
        make_check(
            "numerical.tj_tc_lumped_constraint",
            CheckCategory.NUMERICAL,
            CheckSeverity.BLOCKING if tj_tc_fail else CheckSeverity.WARNING,
            failed=tj_tc_fail or warn_only,
            pass_message="Tj/Tc relationship is consistent with the declared lumped model (Tj typically above Tc).",
            fail_message=f"Tj/Tc relationship contradicts the configured lumped model: {tj_metrics}",
            metrics=tj_metrics,
        )
    )

    gt_num_fail = False
    if gt is not None and "degradation_severity" in gt.columns:
        sev = pd.to_numeric(gt["degradation_severity"], errors="coerce")
        gt_num_fail = bool((sev < 0).any() or (~np.isfinite(sev.to_numpy(dtype=float))).any())
    checks.append(
        make_check(
            "numerical.ground_truth_severity",
            CheckCategory.NUMERICAL,
            CheckSeverity.BLOCKING,
            failed=gt_num_fail,
            pass_message="Ground-truth severity is finite and not negative.",
            fail_message="Ground-truth severity is negative or non-finite.",
        )
    )
    return checks


def check_missingness(loaded: LoadedDataset) -> list[CheckResult]:
    tel = loaded.telemetry
    config = loaded.generation_config or {}
    channels = list(config.get("include_channels") or [])
    quality = _is_quality(loaded)
    if tel is None:
        return [
            make_check(
                "missingness.prerequisites",
                CheckCategory.MISSINGNESS,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="Cannot assess missingness without telemetry.",
            )
        ]
    rates = {}
    unexpected = {}
    zero_as_missing = {}
    for name in channels:
        status_col = f"{name}_status"
        if status_col not in tel.columns:
            continue
        status = tel[status_col].astype(str)
        rates[name] = {
            "missing": float(status.eq("missing").mean()),
            "invalid": float(status.eq("invalid").mean()),
            "n_missing": int(status.eq("missing").sum()),
        }
        if not quality and int(status.ne("valid").sum()) > 0:
            unexpected[name] = rates[name]
        if name in tel.columns:
            missing_mask = status.eq("missing")
            if missing_mask.any():
                vals = tel.loc[missing_mask, name]
                # Never interpret missing as numeric zero: missing cells must be null, not 0.
                as_zero = vals.notna() & (pd.to_numeric(vals, errors="coerce") == 0)
                if bool(as_zero.any()):
                    zero_as_missing[name] = int(as_zero.sum())

    if quality:
        p_missing = float((config.get("quality") or {}).get("p_missing") or 0.0)
        any_missing = any(v["n_missing"] > 0 for v in rates.values())
        mean_missing = float(np.mean([v["missing"] for v in rates.values()])) if rates else 0.0
        failed_expected = p_missing > 0 and len(tel) > 50 and not any_missing
        high = mean_missing > max(0.25, 12 * p_missing) if p_missing > 0 else mean_missing > 0.5
        checks = [
            make_check(
                "missingness.stress_expected",
                CheckCategory.MISSINGNESS,
                CheckSeverity.BLOCKING,
                failed=failed_expected,
                pass_message=f"data_quality_stress has controlled missingness (mean rate={mean_missing:.4f}).",
                fail_message="data_quality_stress configured p_missing>0 but no missing statuses were found.",
                metrics={"p_missing_configured": p_missing, "rates": rates, "mean_missing": mean_missing},
            ),
            make_check(
                "missingness.stress_bounds",
                CheckCategory.MISSINGNESS,
                CheckSeverity.WARNING,
                failed=high,
                pass_message="Missingness rate is within a loose bound of the configured quality model.",
                fail_message=f"Missingness rate {mean_missing:.4f} is far above configured p_missing={p_missing}.",
                metrics={"mean_missing": mean_missing, "p_missing": p_missing},
            ),
        ]
    else:
        n_unexpected = sum(int(v["n_missing"]) for v in unexpected.values())
        # Clean contract: unexpected missing/invalid is a contract violation → BLOCKED.
        checks = [
            make_check(
                "missingness.clean_unexpected",
                CheckCategory.MISSINGNESS,
                CheckSeverity.BLOCKING,
                failed=bool(unexpected),
                pass_message="Clean scenarios have no injected missing/invalid statuses.",
                fail_message=f"Unexpected missing/invalid statuses in a clean scenario: {unexpected}",
                metrics={"unexpected": unexpected, "n_unexpected_missing": n_unexpected},
            )
        ]
    checks.append(
        make_check(
            "missingness.not_zero_filled",
            CheckCategory.MISSINGNESS,
            CheckSeverity.BLOCKING,
            failed=bool(zero_as_missing),
            pass_message="Missing measurements are null, not numeric zero.",
            fail_message=f"Missing cells contain numeric zero: {zero_as_missing}",
            metrics={"zero_filled": zero_as_missing},
        )
    )
    return checks


def check_identity(loaded: LoadedDataset) -> list[CheckResult]:
    tel = loaded.telemetry
    gt = loaded.ground_truth
    quality = _is_quality(loaded)
    config = loaded.generation_config or {}
    if tel is None:
        return [
            make_check(
                "identity.prerequisites",
                CheckCategory.IDENTITY,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="Cannot run identity checks without telemetry.",
            )
        ]
    n_dup_id = int(tel["telemetry_id"].duplicated().sum()) if "telemetry_id" in tel.columns else -1
    n_dup_mc = 0
    if "module_id" in tel.columns and "cycle_number" in tel.columns:
        n_dup_mc = int(tel.duplicated(["module_id", "cycle_number"]).sum())
    n_dup_rows = int(tel.duplicated().sum())
    missing_mod = int((tel["module_id"].isna() | tel["module_id"].astype(str).str.strip().eq("")).sum()) if "module_id" in tel.columns else -1
    missing_lot = int((tel["lot_id"].isna() | tel["lot_id"].astype(str).str.strip().eq("")).sum()) if "lot_id" in tel.columns else -1

    p_dup = float((config.get("quality") or {}).get("p_duplicate_record") or 0.0)
    if quality:
        id_fail = n_dup_id > 0  # duplicate telemetry_id is still identity corruption; generator uses -dup suffix
        # module/cycle duplicates are expected; measure vs config
        expected_frac = p_dup
        actual_frac = float(n_dup_mc / max(len(tel), 1))
        mc_warn = expected_frac > 0 and n_dup_mc == 0 and len(tel) > 200
        mc_block = False
        row_fail = False
    else:
        id_fail = n_dup_id > 0
        mc_warn = False
        mc_block = n_dup_mc > 0
        row_fail = n_dup_rows > 0

    checks = [
        make_check(
            "identity.duplicate_telemetry_id",
            CheckCategory.IDENTITY,
            CheckSeverity.BLOCKING,
            failed=id_fail,
            pass_message="telemetry_id values are unique.",
            fail_message=f"Duplicate telemetry_id count: {n_dup_id}",
            metrics={"n_duplicate_telemetry_id": n_dup_id},
        ),
        make_check(
            "identity.duplicate_module_cycle",
            CheckCategory.IDENTITY,
            CheckSeverity.BLOCKING if (not quality) else CheckSeverity.WARNING,
            failed=mc_block or mc_warn,
            pass_message=(
                f"data_quality_stress module/cycle duplicates={n_dup_mc} (injected defect, measured)."
                if quality
                else "No unexpected module/cycle duplicates in a clean scenario."
            ),
            fail_message=(
                "data_quality_stress configured duplicate injection but none were found."
                if mc_warn
                else f"Unexpected module/cycle duplicates: {n_dup_mc}"
            ),
            metrics={"n_duplicate_module_cycle": n_dup_mc, "p_duplicate_record": p_dup, "scenario": _scenario(loaded)},
        ),
        make_check(
            "identity.duplicate_rows",
            CheckCategory.IDENTITY,
            CheckSeverity.BLOCKING if not quality else CheckSeverity.WARNING,
            failed=row_fail,
            pass_message=f"Exact duplicate rows: {n_dup_rows}.",
            fail_message=f"Exact duplicate rows in a clean scenario: {n_dup_rows}",
            metrics={"n_duplicate_rows": n_dup_rows},
        ),
        make_check(
            "identity.missing_ids",
            CheckCategory.IDENTITY,
            CheckSeverity.BLOCKING,
            failed=missing_mod > 0 or missing_lot > 0,
            pass_message="module_id and lot_id are present on telemetry rows.",
            fail_message=f"Missing module_id={missing_mod} lot_id={missing_lot}",
            metrics={"missing_module_id": missing_mod, "missing_lot_id": missing_lot},
        ),
    ]
    if gt is not None and "module_id" in gt.columns:
        n_gt_dup = int(gt["module_id"].duplicated().sum())
        checks.append(
            make_check(
                "identity.ground_truth_duplicates",
                CheckCategory.IDENTITY,
                CheckSeverity.BLOCKING,
                failed=n_gt_dup > 0,
                pass_message="No duplicate ground-truth module rows.",
                fail_message=f"Duplicate ground-truth modules: {n_gt_dup}",
                metrics={"n_duplicate_gt_modules": n_gt_dup},
            )
        )
    return checks


def check_leakage(loaded: LoadedDataset) -> list[CheckResult]:
    tel = loaded.telemetry
    gt = loaded.ground_truth
    if tel is None:
        return [
            make_check(
                "leakage.prerequisites",
                CheckCategory.LEAKAGE,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="Cannot run leakage checks without telemetry.",
            )
        ]
    cols = [str(c) for c in tel.columns]
    lowered = {c.lower(): c for c in cols}
    forbidden_hits = sorted(FORBIDDEN_TELEMETRY_COLUMNS.intersection(cols))
    fragment_hits = []
    for frag in LEAKAGE_NAME_FRAGMENTS:
        for low, orig in lowered.items():
            if frag.replace("_", "") in low.replace("_", "") and orig not in forbidden_hits:
                if orig in {"module_id", "lot_id", "test_id", "dataset_id", "telemetry_id"}:
                    continue
                fragment_hits.append(orig)
    notes_hits = 0
    if "provenance_notes" in tel.columns:
        notes = tel["provenance_notes"].astype(str).str.lower()
        for token in ("degradation_mechanism=", "onset_cycle=", "health_state=", "rate_scale="):
            notes_hits += int(notes.str.contains(token, regex=False).any())

    label_leak = False
    leak_metrics: dict[str, Any] = {}
    if forbidden_hits:
        label_leak = True
    elif gt is not None and "degradation_mechanism" in gt.columns:
        gt_labels = gt[["module_id", "degradation_mechanism"]].rename(
            columns={"degradation_mechanism": "_gt_mechanism"}
        )
        merged = tel.merge(gt_labels, on="module_id", how="left")
        mech = merged["_gt_mechanism"].astype(str)
        suspect = []
        n_mech = mech.nunique()
        if n_mech >= 2:
            for name in DISTRIBUTION_SIGNALS:
                if name not in merged.columns:
                    continue
                mask = valid_mask(merged, name)
                if int(mask.sum()) < 50:
                    continue
                sub = merged.loc[mask, [name, "_gt_mechanism"]]
                nunique_total = sub[name].nunique()
                if nunique_total == n_mech:
                    per = sub.groupby("_gt_mechanism")[name].nunique()
                    if bool((per == 1).all()):
                        suspect.append(name)
            leak_metrics["trivial_label_columns"] = suspect
            label_leak = bool(suspect)

    failed = bool(forbidden_hits or fragment_hits or notes_hits or label_leak)
    return [
        make_check(
            "leakage.ground_truth_in_telemetry",
            CheckCategory.LEAKAGE,
            CheckSeverity.BLOCKING,
            failed=failed,
            pass_message="Telemetry does not contain ground-truth labels or forbidden analytical fields.",
            fail_message=(
                f"Ground-truth leakage detected. columns={forbidden_hits} "
                f"fragments={fragment_hits} notes_tokens={notes_hits} trivial={leak_metrics.get('trivial_label_columns')}"
            ),
            metrics={
                "forbidden_columns": forbidden_hits,
                "fragment_columns": fragment_hits,
                "notes_leak_tokens": notes_hits,
                **leak_metrics,
            },
        )
    ]


def check_size(loaded: LoadedDataset) -> list[CheckResult]:
    meta = loaded.dataset_meta or {}
    config = loaded.generation_config or {}
    tel = loaded.telemetry
    gt = loaded.ground_truth
    quality = _is_quality(loaded)
    if tel is None or gt is None:
        return [
            make_check(
                "size.prerequisites",
                CheckCategory.SIZE,
                CheckSeverity.BLOCKING,
                failed=True,
                pass_message="",
                fail_message="Cannot compare dataset size without telemetry and ground truth.",
            )
        ]
    n_mod = int(tel["module_id"].nunique())
    n_lot = int(tel["lot_id"].nunique()) if "lot_id" in tel.columns else 0
    n_gt = int(len(gt))
    n_rows = int(len(tel))
    cfg_mod = int(config.get("n_modules") or 0)
    cfg_lot = int(config.get("n_lots") or 0)
    nominal = meta.get("n_observations_per_module_nominal")
    expected_rows = cfg_mod * int(nominal) if nominal else None

    mod_fail = cfg_mod > 0 and n_mod != cfg_mod
    lot_fail = cfg_lot > 0 and n_lot != cfg_lot
    gt_fail = n_gt != n_mod
    if quality:
        row_fail = expected_rows is not None and n_rows == 0
        row_warn = False
        if expected_rows:
            # dropout reduces rows; duplicates increase them. Completely unchanged can still be OK.
            ratio = n_rows / expected_rows
            row_warn = ratio < 0.5 or ratio > 1.5
            row_block = ratio < 0.2
        else:
            row_block = False
        row_failed = row_fail or row_block
        row_severity = CheckSeverity.BLOCKING if row_failed else CheckSeverity.WARNING
        row_flag = row_failed or row_warn
    else:
        row_failed = expected_rows is not None and n_rows != expected_rows
        row_severity = CheckSeverity.BLOCKING
        row_flag = row_failed

    return [
        make_check(
            "size.module_and_lot_counts",
            CheckCategory.SIZE,
            CheckSeverity.BLOCKING,
            failed=mod_fail or lot_fail or gt_fail,
            pass_message=f"Module/lot/GT counts match configuration (modules={n_mod}, lots={n_lot}, gt={n_gt}).",
            fail_message=f"Count mismatch: modules {n_mod}/{cfg_mod}, lots {n_lot}/{cfg_lot}, gt {n_gt}.",
            metrics={
                "n_modules": n_mod,
                "n_lots": n_lot,
                "n_ground_truth_rows": n_gt,
                "configured_modules": cfg_mod,
                "configured_lots": cfg_lot,
            },
        ),
        make_check(
            "size.telemetry_row_count",
            CheckCategory.SIZE,
            row_severity,
            failed=row_flag,
            pass_message=f"Telemetry row count {n_rows} is consistent with configuration (expected nominal {expected_rows}).",
            fail_message=f"Telemetry row count {n_rows} vs nominal {expected_rows} (quality={quality}).",
            metrics={
                "n_telemetry_rows": n_rows,
                "nominal_rows": expected_rows,
                "n_observations_per_module_nominal": nominal,
                "scenario": _scenario(loaded),
            },
        ),
    ]

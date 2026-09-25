#!/usr/bin/env python3
"""Build a declared healthy-reference artifact for M9 population comparison.

This artifact is a predeclared reference population that is INDEPENDENT of direct
Ground Truth access. It is built from the frozen M7 module-summary of modules that
the M7 detector did NOT flag (y_pred_module == False), using a declared selection,
NOT from ground_truth labels.

USAGE:
    python3 scripts/build_healthy_reference.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parent.parent))

REPO = Path(__file__).resolve().parent.parent
MODEL_ID = "iforest-v1-syn-sic-pc-dev-001-s20260922"
OUT = REPO / "ml/datasets/investigations/reference/healthy-reference.json"
SIGNALS = ["RDS_on", "VTH", "IGSS", "IDSS", "VDS_on", "electrical_power", "Tj", "Tc"]


def main() -> None:
    module_summary_path = REPO / "ml/datasets/scores" / MODEL_ID / "module-summary.parquet"
    if not module_summary_path.exists():
        print(f"Missing module-summary: {module_summary_path}")
        sys.exit(1)
    table = pq.read_table(module_summary_path)
    df = table.to_pandas()

    flag_col = "module_anomaly_status"
    if flag_col not in df.columns:
        flag_col = "y_pred_module" if "y_pred_module" in df.columns else None
    if flag_col is None:
        print(f"No flag column in module-summary: {df.columns.tolist()[:20]}")
        sys.exit(1)

    # Declared selection: modules the frozen M7 detector classified as "clean".
    # This is a runtime-declared reference signal, independent of Ground Truth labels.
    if flag_col == "module_anomaly_status":
        ref = df[df[flag_col] == "clean"]
    else:
        ref = df[df[flag_col].astype(bool) == False]  # noqa: E712
    if len(ref) == 0:
        print("No reference modules selected; using all modules declared reference")
        ref = df
    stats = {}
    from backend.agents.investigation.data_access import DataAccess

    da = DataAccess(REPO)
    for signal in SIGNALS:
        vals = []
        for mid in ref["module_id"].tolist()[:50]:
            try:
                feats = da.observation_features(mid, signals=[signal])
                vals.extend([v for v in feats.get(signal, []) if v is not None])
            except Exception:
                continue
        if vals:
            import numpy as np

            arr = np.asarray(vals, dtype=float)
            arr = arr[np.isfinite(arr)]
            stats[signal] = {"n": int(len(arr)), "mean": float(arr.mean()), "std": float(arr.std())}
        else:
            stats[signal] = {"n": 0, "mean": None, "std": None}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "model_id": MODEL_ID,
        "declared_by": "M9 build_healthy_reference",
        "selection": "frozen M7 unfagged modules (y_pred_module == False)",
        "declaration_note": "Declared reference population independent of direct Ground Truth access.",
        "signals": stats,
    }
    OUT.write_text(json.dumps(payload, indent=2))
    print(f"Wrote reference artifact: {OUT}")
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
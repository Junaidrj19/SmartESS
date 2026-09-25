from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from backend.agents.investigation.tools.models import ToolError, ToolResult

TOOL_NAME = "compare_population"
TOOL_VERSION = "1.0.0"

DEFAULT_REFERENCE_ARTIFACT = "ml/datasets/investigations/reference/healthy-reference.json"


def _mean_std(values: List[float]) -> Dict[str, float]:
    arr = np.asarray([float(v) for v in values], dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        raise ToolError(TOOL_NAME, "no finite values")
    return {"n": int(len(arr)), "mean": float(arr.mean()), "std": float(arr.std())}


def compare_population(
    values: List[float],
    reference: Dict[str, Any] | None = None,
    reference_artifact: str = "",
    **_: Any,
) -> ToolResult:
    stat = _mean_std(values)
    if reference is None:
        raise ToolError(TOOL_NAME, "no reference population supplied; compare cannot run")
    ref_mean = reference.get("mean")
    ref_std = reference.get("std")
    if ref_mean is None:
        raise ToolError(TOOL_NAME, "reference missing mean")
    if not ref_std or ref_std == 0:
        z = float(stat["mean"]) - float(ref_mean)
        zscore = float("nan")
    else:
        z = (float(stat["mean"]) - float(ref_mean)) / float(ref_std)
        zscore = z
    deviation_pct = (float(stat["mean"]) - float(ref_mean)) / abs(float(ref_mean)) * 100.0 if ref_mean != 0 else float("nan")
    return ToolResult(
        tool_name=TOOL_NAME,
        tool_version=TOOL_VERSION,
        input_summary={"n": stat["n"], "reference_n": reference.get("n")},
        output={
            "module_mean": stat["mean"],
            "module_std": stat["std"],
            "reference_mean": float(ref_mean),
            "reference_std": float(ref_std) if ref_std else None,
            "z_score": zscore,
            "deviation_pct": deviation_pct,
        },
        provenance={"reference_artifact": reference_artifact or DEFAULT_REFERENCE_ARTIFACT},
    )


class HealthyReferenceSelector:
    def __init__(self, reference_artifact: str = DEFAULT_REFERENCE_ARTIFACT):
        self.reference_artifact = reference_artifact

    def load(self) -> Dict[str, Any] | None:
        from pathlib import Path

        p = Path(self.reference_artifact)
        if not p.exists():
            return None
        import json

        return json.loads(p.read_text())
from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from backend.agents.investigation.tools.models import ToolError, ToolResult

TOOL_NAME = "calculate_drift"
TOOL_VERSION = "1.0.0"


def _clean(values: List[float]) -> List[float]:
    return [float(v) for v in values if v is not None and not (isinstance(v, float) and np.isnan(v))]


def calculate_drift(values: List[float], baseline: float | None = None, **_: Any) -> ToolResult:
    clean = _clean(values)
    if len(clean) < 2:
        raise ToolError(TOOL_NAME, "need at least 2 non-null values")
    first = float(clean[0])
    last = float(clean[-1])
    base = first if baseline is None else float(baseline)
    if base == 0:
        raise ToolError(TOOL_NAME, "baseline is zero; percent drift undefined")
    abs_drift = last - base
    pct_drift = (last - base) / abs(base) * 100.0
    return ToolResult(
        tool_name=TOOL_NAME,
        tool_version=TOOL_VERSION,
        input_summary={"n": len(clean), "baseline": base},
        output={
            "first": first,
            "last": last,
            "absolute_drift": float(abs_drift),
            "percent_drift": float(pct_drift),
        },
        provenance={
            "method": "first_vs_last",
            "signal": "values",
        },
    )
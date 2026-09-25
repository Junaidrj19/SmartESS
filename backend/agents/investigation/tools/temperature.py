from __future__ import annotations

from typing import Any, List

import numpy as np

from backend.agents.investigation.tools.models import ToolError, ToolResult

TOOL_NAME = "analyze_temperature_dependence"
TOOL_VERSION = "1.0.0"


def _finite_signal(values: List[float]) -> np.ndarray:
    arr = np.asarray([float(v) for v in values], dtype=float)
    arr = arr[np.isfinite(arr)]
    return arr


def analyze_temperature_dependence(
    values: List[float],
    temperature: List[float] | None = None,
    **_: Any,
) -> ToolResult:
    y = _finite_signal(values)
    if temperature is None:
        temperature = []
    t = np.asarray([float(v) for v in temperature], dtype=float)
    if len(t) == 0 or len(y) == 0:
        raise ToolError(TOOL_NAME, "need both signal and temperature series")
    valid = np.isfinite(t) & np.isfinite(y)
    if valid.sum() < 2:
        raise ToolError(TOOL_NAME, "need at least 2 finite (signal, temperature) pairs")
    tv = t[valid]
    yv = y[valid]
    corr = float(np.corrcoef(tv, yv)[0, 1]) if len(tv) >= 2 else float("nan")
    return ToolResult(
        tool_name=TOOL_NAME,
        tool_version=TOOL_VERSION,
        input_summary={"n": int(valid.sum())},
        output={"temperature_correlation": corr},
        provenance={"method": "pearson_correlation_signal_vs_temperature"},
    )
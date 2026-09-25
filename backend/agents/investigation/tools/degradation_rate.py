from __future__ import annotations

from typing import Any, List

import numpy as np

from backend.agents.investigation.tools.models import ToolError, ToolResult

TOOL_NAME = "calculate_degradation_rate"
TOOL_VERSION = "1.0.0"


def _clean(values: List[float]) -> List[float]:
    return [float(v) for v in values if v is not None and not (isinstance(v, float) and np.isnan(v))]


def calculate_degradation_rate(
    values: List[float],
    cycles: List[int] | None = None,
    **_: Any,
) -> ToolResult:
    clean = _clean(values)
    if len(clean) < 2:
        raise ToolError(TOOL_NAME, "need at least 2 non-null values")
    if cycles and len(cycles) == len(values):
        x = np.asarray([float(c) for c in cycles], dtype=float)
    else:
        x = np.arange(len(values), dtype=float)
    y = np.asarray(clean, dtype=float)
    slope = float(np.polyfit(x, y, 1)[0])
    return ToolResult(
        tool_name=TOOL_NAME,
        tool_version=TOOL_VERSION,
        input_summary={"n": len(clean)},
        output={"degradation_rate": slope, "units": "value_per_cycle"},
        provenance={"method": "linear_regression_value_vs_cycle"},
    )
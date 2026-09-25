from __future__ import annotations

from typing import Any, List

import numpy as np

from backend.agents.investigation.tools.models import ToolError, ToolResult

TOOL_NAME = "calculate_slope"
TOOL_VERSION = "1.0.0"


def find_slope(values: List[float]) -> float:
    y = np.asarray([float(v) for v in values])
    x = np.arange(len(y), dtype=float)
    if len(y) < 2:
        raise ToolError(TOOL_NAME, "need at least 2 values")
    cnt = np.isfinite(y)
    if cnt.sum() < 2:
        raise ToolError(TOOL_NAME, "need at least 2 finite values")
    x = x[cnt]
    y = y[cnt]
    slope = np.polyfit(x, y, 1)[0]
    return float(slope)


def calculate_slope(values: List[float], **_: Any) -> ToolResult:
    slope = find_slope(values)
    return ToolResult(
        tool_name=TOOL_NAME,
        tool_version=TOOL_VERSION,
        input_summary={"n": len(values)},
        output={"slope": slope, "units": "value_per_observation"},
        provenance={"method": "linear_regression_polyfit_degree_1"},
    )
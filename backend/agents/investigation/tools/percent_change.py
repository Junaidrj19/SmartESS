from __future__ import annotations

from typing import Any, List

import numpy as np

from backend.agents.investigation.tools.models import ToolError, ToolResult

TOOL_NAME = "calculate_percent_change"
TOOL_VERSION = "1.0.0"


def percent_change(values: List[float]) -> float:
    clean = [float(v) for v in values if v is not None and not (isinstance(v, float) and np.isnan(v))]
    if len(clean) < 2:
        raise ToolError(TOOL_NAME, "need at least 2 non-null values")
    if clean[0] == 0:
        raise ToolError(TOOL_NAME, "starting value is zero")
    return (clean[-1] - clean[0]) / abs(clean[0]) * 100.0


def calculate_percent_change(values: List[float], **_: Any) -> ToolResult:
    pct = percent_change(values)
    return ToolResult(
        tool_name=TOOL_NAME,
        tool_version=TOOL_VERSION,
        input_summary={"n": len(values)},
        output={"percent_change": float(pct)},
        provenance={"method": "endpoint_percent_change"},
    )
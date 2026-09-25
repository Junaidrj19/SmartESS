from __future__ import annotations

from typing import Any, List, Optional

import numpy as np

from backend.agents.investigation.tools.models import ToolError, ToolResult

TOOL_NAME = "calculate_correlation"
TOOL_VERSION = "1.0.0"


def pearson(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        raise ToolError(TOOL_NAME, "series lengths differ")
    x = np.asarray([float(v) for v in a], dtype=float)
    y = np.asarray([float(v) for v in b], dtype=float)
    valid = np.isfinite(x) & np.isfinite(y)
    if valid.sum() < 2:
        raise ToolError(TOOL_NAME, "need at least 2 finite pairs")
    x = x[valid]
    y = y[valid]
    if x.std() == 0 or y.std() == 0:
        raise ToolError(TOOL_NAME, "zero variance series")
    return float(np.corrcoef(x, y)[0, 1])


def calculate_correlation(
    a: List[float],
    b: List[float],
    label_a: str = "a",
    label_b: str = "b",
    **_: Any,
) -> ToolResult:
    r = pearson(a, b)
    return ToolResult(
        tool_name=TOOL_NAME,
        tool_version=TOOL_VERSION,
        input_summary={"n": len(a)},
        output={"correlation": r, "series_a": label_a, "series_b": label_b},
        provenance={"method": "pearson_correlation"},
    )
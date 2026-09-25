from __future__ import annotations

from typing import Any, List

import numpy as np

from backend.agents.investigation.tools.models import ToolError, ToolResult

TOOL_NAME = "detect_change_point"
TOOL_VERSION = "1.0.0"


def _clean(values: List[float]) -> List[float]:
    out: List[float] = []
    for v in values:
        if v is not None and not (isinstance(v, float) and np.isnan(v)):
            out.append(float(v))
    return out


def detect_change_point(values: List[float], window: int = 5, **_: Any) -> ToolResult:
    clean = _clean(values)
    if len(clean) < 2 * window + 1:
        raise ToolError(TOOL_NAME, "series too short for change-point analysis")
    arr = np.asarray(clean)
    best_idx = 0
    best_score = -1.0
    for i in range(window, len(arr) - window):
        left = arr[i - window : i]
        right = arr[i : i + window]
        left_mean = left.mean()
        right_mean = right.mean()
        pooled = np.concatenate([left, right])
        if pooled.std() == 0:
            continue
        score = abs(left_mean - right_mean) / pooled.std()
        if score > best_score:
            best_score = score
            best_idx = i
    return ToolResult(
        tool_name=TOOL_NAME,
        tool_version=TOOL_VERSION,
        input_summary={"n": len(clean), "window": window},
        output={
            "change_point_index": int(best_idx) if best_score >= 0 else None,
            "change_point_score": float(best_score) if best_score >= 0 else None,
            "left_mean": float(arr[:best_idx].mean()) if best_score >= 0 else None,
            "right_mean": float(arr[best_idx:].mean()) if best_score >= 0 else None,
        },
        provenance={"method": "sliding_window_mean_difference"},
    )
from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.agents.investigation.tools.models import ToolError, ToolResult

TOOL_NAME = "check_acceptance_limits"
TOOL_VERSION = "1.0.0"


def check_acceptance_limits(
    values: List[float],
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
    **_: Any,
) -> ToolResult:
    if min_value is None and max_value is None:
        raise ToolError(TOOL_NAME, "must supply at least one of min_value or max_value")
    if min_value is not None and max_value is not None and min_value > max_value:
        raise ToolError(TOOL_NAME, "min_value > max_value")
    violations = []
    for i, v in enumerate(values):
        if v is None:
            continue
        finite_ok = True
        try:
            import math

            if isinstance(v, float) and math.isnan(v):
                finite_ok = False
        except Exception:
            pass
        if not finite_ok:
            continue
        if min_value is not None and v < min_value:
            violations.append({"index": i, "value": float(v), "bound": "min"})
        if max_value is not None and v > max_value:
            violations.append({"index": i, "value": float(v), "bound": "max"})
    return ToolResult(
        tool_name=TOOL_NAME,
        tool_version=TOOL_VERSION,
        input_summary={"n": len(values), "min_value": min_value, "max_value": max_value},
        output={
            "n_violations": len(violations),
            "violations": violations[:50],
        },
        provenance={"source": "module_profile_acceptance_limits"},
    )
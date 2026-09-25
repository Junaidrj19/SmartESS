from __future__ import annotations

from typing import Any, Callable, Dict, List

from backend.agents.investigation.tools.correlation import calculate_correlation
from backend.agents.investigation.tools.drift import calculate_drift
from backend.agents.investigation.tools.limits import check_acceptance_limits
from backend.agents.investigation.tools.percent_change import calculate_percent_change
from backend.agents.investigation.tools.population import compare_population
from backend.agents.investigation.tools.slope import calculate_slope
from backend.agents.investigation.tools.changepoint import detect_change_point
from backend.agents.investigation.tools.degradation_rate import calculate_degradation_rate
from backend.agents.investigation.tools.temperature import analyze_temperature_dependence
from backend.agents.investigation.tools.models import ToolResult


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}

    def register(self, name: str, fn: Callable) -> None:
        self._tools[name] = fn

    def get(self, name: str) -> Callable:
        if name not in self._tools:
            raise KeyError(f"Unknown tool: {name}")
        return self._tools[name]

    def list(self) -> List[str]:
        return sorted(self._tools.keys())

    def call(self, name: str, **kwargs: Any) -> ToolResult:
        fn = self.get(name)
        return fn(**kwargs)


_default_registry: ToolRegistry | None = None


def get_default_registry() -> ToolRegistry:
    global _default_registry
    if _default_registry is None:
        r = ToolRegistry()
        r.register("calculate_drift", calculate_drift)
        r.register("calculate_slope", calculate_slope)
        r.register("calculate_percent_change", calculate_percent_change)
        r.register("compare_population", compare_population)
        r.register("analyze_temperature_dependence", analyze_temperature_dependence)
        r.register("detect_change_point", detect_change_point)
        r.register("calculate_correlation", calculate_correlation)
        r.register("check_acceptance_limits", check_acceptance_limits)
        r.register("calculate_degradation_rate", calculate_degradation_rate)
        _default_registry = r
    return _default_registry
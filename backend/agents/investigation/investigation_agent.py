from __future__ import annotations

from typing import Any, Dict, List

from backend.agents.investigation.data_access import DataAccess
from backend.agents.investigation.models.investigation import (
    DeterministicResult,
    InvestigationRecord,
)
from backend.agents.investigation.models.evidence import EvidenceRecord
from backend.agents.investigation.tools.registry import ToolRegistry, get_default_registry
from backend.agents.investigation.tools.population import HealthyReferenceSelector


class InvestigationAgent:
    def __init__(self, data_access: DataAccess | None = None, registry: ToolRegistry | None = None):
        self.da = data_access or DataAccess()
        self.registry = registry or get_default_registry()
        self.ref_selector = HealthyReferenceSelector()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        module_id = state["module_id"]
        model_id = state["model_id"]

        trajectory = self.da.load_module_trajectory(model_id, module_id)
        module_summary = self.da.module_summary(model_id, module_id)
        module_eval = self.da.module_evaluation(model_id, module_id)
        timing = self.da.timing_analysis(model_id, module_id)
        baseline = self.da.baseline_comparison(model_id, module_id)
        model_record = self.da.model_record(model_id)

        results = self._run_deterministic_tools(trajectory.signals, trajectory.cycle_numbers)

        ref = self.ref_selector.load()
        limitations = list(state.get("limitations", []) or [])
        if ref is None:
            limitations.append(
                "population_comparison_skipped: no healthy reference artifact at "
                "ml/datasets/investigations/reference/healthy-reference.json"
            )
        else:
            results.extend(self._run_population_comparison(trajectory.signals, ref))

        return {
            "module_trajectory": trajectory,
            "m7_module_summary": module_summary,
            "m8_module_evaluation": module_eval,
            "m8_timing": timing,
            "m8_baseline": baseline,
            "deterministic_results": results,
            "module_profile": self._build_module_profile(module_summary, model_record),
            "test_profile": self._build_test_profile(model_record),
            "limitations": limitations,
        }

    def _run_population_comparison(
        self, signals: Dict[str, List[float]], reference: Dict[str, Any]
    ) -> List[DeterministicResult]:
        results = []
        ref_signals = reference.get("signals", {})
        for signal_name, values in signals.items():
            if not values:
                continue
            ref = ref_signals.get(signal_name)
            if ref is None or ref.get("mean") is None:
                continue
            try:
                r = self.registry.call(
                    "compare_population",
                    values=values,
                    reference=ref,
                )
                results.append(DeterministicResult(
                    tool_name=r.tool_name,
                    tool_version=r.tool_version,
                    input_summary={"signal": signal_name, **r.input_summary},
                    output=r.output,
                    provenance={**r.provenance, "signal": signal_name},
                ))
            except Exception:
                continue
        return results

    def _run_deterministic_tools(self, signals: Dict[str, List[float]], cycles: List[int]) -> List[DeterministicResult]:
        results = []
        for signal_name, values in signals.items():
            if not values or all(v is None or (isinstance(v, float) and v != v) for v in values):
                continue
            attempts = [
                "calculate_drift",
                "calculate_slope",
                "calculate_percent_change",
                "calculate_degradation_rate",
            ]
            for tool in attempts:
                try:
                    if tool == "calculate_degradation_rate":
                        r = self.registry.call(tool, values=values, cycles=cycles)
                    else:
                        r = self.registry.call(tool, values=values)
                    results.append(DeterministicResult(
                        tool_name=r.tool_name,
                        tool_version=r.tool_version,
                        input_summary={"signal": signal_name, **r.input_summary},
                        output=r.output,
                        provenance={**r.provenance, "signal": signal_name},
                    ))
                except Exception:
                    continue
        return results

    def _get_signal_values(self, record: InvestigationRecord, signal: str) -> List[float]:
        if record.module_trajectory is None:
            return []
        return record.module_trajectory.signals.get(signal, [])

    def _build_module_profile(self, module_summary: Dict[str, Any], model_record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "module_id": module_summary.get("module_id"),
            "feature_version": model_record.get("feature_version"),
        }

    def _build_test_profile(self, model_record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "split_type": (model_record.get("split") or {}).get("type"),
            "test_lots": (model_record.get("split") or {}).get("test_lots"),
        }
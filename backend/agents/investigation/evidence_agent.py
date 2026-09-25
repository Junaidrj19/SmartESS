from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.agents.investigation.models.evidence import EvidenceRecord
from backend.knowledge.retrieval import ChromaRetriever

# A signal is treated as "showing change" when any deterministic tool reported a
# magnitude of this many percent or more. This only decides which engineering
# query to run next; it is never used as a diagnostic conclusion.
MIN_CHANGE_PERCENT = 1.0
MAX_QUERIES = 8

SIGNAL_QUERIES: Dict[str, str] = {
    "RDS_on": "temperature compensated RDS(on) degradation monitoring SiC MOSFET",
    "VTH": "SiC MOSFET threshold voltage drift gate oxide stress",
    "IGSS": "SiC MOSFET gate leakage IGSS degradation gate oxide reliability",
    "IDSS": "SiC MOSFET drain leakage IDSS degradation",
    "VDS_on": "power module on-state voltage VDS(on) degradation",
    "electrical_power": "electrical power degradation monitoring power cycling SiC MOSFET",
    "Tj": "SiC MOSFET junction temperature rise thermal path degradation",
    "Tc": "case temperature thermal resistance degradation power module",
    "thermal_resistance": "SiC MOSFET thermal resistance increase package degradation",
}

# Mechanism-level queries added when a group of signals is changing together.
SIGNAL_GROUPS = (
    ({"RDS_on", "electrical_power", "VDS_on"}, "SiC MOSFET bond wire interconnect degradation during power cycling"),
    ({"Tj", "Tc", "thermal_resistance"}, "SiC MOSFET die attach solder degradation thermal cycling"),
    ({"VTH", "IGSS", "IDSS"}, "SiC MOSFET gate oxide degradation under gate bias stress"),
)

TOOL_QUERIES: Dict[str, str] = {
    "calculate_drift": "electrical parameter drift degradation SiC MOSFET",
    "calculate_slope": "degradation trend slope power cycling SiC MOSFET",
    "calculate_percent_change": "percent change electrical parameter degradation",
    "calculate_degradation_rate": "degradation rate per cycle power cycling",
    "compare_population": "population comparison healthy reference degradation threshold",
    "analyze_temperature_dependence": "temperature dependence electrical parameter RDS(on)",
    "detect_change_point": "change point degradation onset power cycling",
    "calculate_correlation": "correlated degradation parameters temperature",
    "check_acceptance_limits": "acceptance limit datasheet violation reliability",
}

FALLBACK_QUERY = "SiC MOSFET reliability degradation mechanisms power cycling"


class EvidenceAgent:
    """Builds knowledge-base queries from the deterministic findings and returns
    provenance-preserving evidence records. It never invents a source: every
    record comes from a ChromaDB chunk of a verified corpus document.
    """

    def __init__(self, retriever: Optional[ChromaRetriever] = None, max_evidence: int = 5):
        self.retriever = retriever or ChromaRetriever()
        self.max_evidence = max_evidence

    @staticmethod
    def _magnitudes(deterministic_results: List[Any]) -> Dict[str, float]:
        magnitudes: Dict[str, float] = {}
        for r in deterministic_results or []:
            signal = (getattr(r, "input_summary", None) or {}).get("signal")
            if not signal:
                continue
            output = getattr(r, "output", None) or {}
            value = output.get("percent_drift", output.get("percent_change"))
            if value is None:
                continue
            try:
                magnitude = abs(float(value))
            except (TypeError, ValueError):
                continue
            if magnitude > magnitudes.get(signal, 0.0):
                magnitudes[signal] = magnitude
        return magnitudes

    def changed_signals(self, deterministic_results: List[Any]) -> List[str]:
        """Signals whose deterministic results show a non-trivial change."""
        magnitudes = self._magnitudes(deterministic_results)
        ranked = sorted(magnitudes.items(), key=lambda kv: -kv[1])
        return [signal for signal, magnitude in ranked if magnitude >= MIN_CHANGE_PERCENT]

    def build_queries(self, deterministic_results: List[Any]) -> List[str]:
        queries: List[str] = []
        seen = set()

        def add(query: str) -> None:
            if query and query not in seen:
                queries.append(query)
                seen.add(query)

        signals = self.changed_signals(deterministic_results)
        for signal in signals:
            add(SIGNAL_QUERIES.get(signal, f"SiC MOSFET {signal} degradation reliability"))
        for group, query in SIGNAL_GROUPS:
            if group.intersection(signals):
                add(query)
        for r in deterministic_results or []:
            query = TOOL_QUERIES.get(getattr(r, "tool_name", ""))
            if query:
                add(query)
        if not queries:
            add(FALLBACK_QUERY)
        return queries[:MAX_QUERIES]

    def retrieve_for_result(self, query: str, all_records: List[EvidenceRecord]) -> List[EvidenceRecord]:
        records = self.retriever.retrieve(query, k=self.max_evidence)
        known_ids = {r.evidence_id for r in all_records}
        return [r for r in records if r.evidence_id not in known_ids]

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        deterministic_results = state.get("deterministic_results", [])
        queries = self.build_queries(deterministic_results)
        records: List[EvidenceRecord] = list(state.get("evidence_records", []))
        for query in queries:
            try:
                found = self.retrieve_for_result(query, records)
                records.extend(found)
            except Exception:
                continue
            if len(records) >= self.max_evidence:
                break

        limitations = list(state.get("limitations", []))
        evidence_status = "available"
        if self.retriever.count() == 0:
            evidence_status = "unavailable"
            if "knowledge_base_empty" not in limitations:
                limitations.append("knowledge_base_empty: no ingested evidence; returning no evidence records")

        return {
            "evidence_records": records[: self.max_evidence],
            "evidence_queries": queries,
            "evidence_status": evidence_status,
            "limitations": limitations,
        }

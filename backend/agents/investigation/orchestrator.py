from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import END, START, StateGraph

from backend.agents.investigation.data_access import DataAccess
from backend.agents.investigation.evidence_agent import EvidenceAgent
from backend.agents.investigation.hypothesis_agent import HypothesisAgent, validate_hypothesis
from backend.agents.investigation.investigation_agent import InvestigationAgent
from backend.agents.investigation.models.investigation import InvestigationStatus, ProvenanceEntry
from backend.agents.investigation.report_agent import ReportAgent, validate_report
from backend.agents.investigation.state import (
    MAX_EVIDENCE_ROUNDS,
    MAX_HYPOTHESIS_RETRIES,
    MAX_REPORT_RETRIES,
)
from backend.llm.factory import create_llm_client
from backend.llm.interface import LLMClient
from backend.llm.settings import LLMSettings


class InvestigationState(TypedDict, total=False):
    investigation_id: str
    module_id: str
    model_id: str
    dataset_id: str
    status: str
    module_trajectory: Any
    m7_module_summary: Dict[str, Any]
    m8_module_evaluation: Dict[str, Any]
    m8_timing: Dict[str, Any]
    m8_baseline: Dict[str, Any]
    module_profile: Dict[str, Any]
    test_profile: Dict[str, Any]
    deterministic_results: list
    evidence_records: list
    evidence_queries: list
    hypothesis: Any
    report: Any
    provenance: list
    agent_messages: Dict[str, str]
    retry_counts: Dict[str, int]
    errors: Dict[str, str]
    limitations: list
    messages: list
    evidence_status: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class InvestigationGraph:
    """LangGraph supervision of the four M9 agents.

    Topology:

        START → load_investigation → investigation_agent → evidence_agent
              → hypothesis_agent → hypothesis_validation
              → (retry: evidence_agent / hypothesis_agent, bounded)
              → report_agent → report_validation → END

    The HypothesisAgent is the LLM-backed agent. It receives the client built
    from the runtime LLM configuration (OpenRouter by default) unless one is
    injected explicitly.
    """

    def __init__(
        self,
        investigation_agent: Optional[InvestigationAgent] = None,
        evidence_agent: Optional[EvidenceAgent] = None,
        hypothesis_agent: Optional[HypothesisAgent] = None,
        report_agent: Optional[ReportAgent] = None,
        data_access: Optional[DataAccess] = None,
        llm: Optional[LLMClient] = None,
        llm_settings: Optional[LLMSettings] = None,
    ):
        self.data_access = data_access or DataAccess()
        self.llm_settings = llm_settings or LLMSettings()
        self.llm = llm if llm is not None else create_llm_client(self.llm_settings)
        self.investigation_agent = investigation_agent or InvestigationAgent(self.data_access)
        self.evidence_agent = evidence_agent or EvidenceAgent()
        self.hypothesis_agent = hypothesis_agent or HypothesisAgent(llm=self.llm, settings=self.llm_settings)
        self.report_agent = report_agent or ReportAgent()
        self.graph = self._build()

    # ------------------------------------------------------------------ graph
    def _build(self):
        g = StateGraph(InvestigationState)

        g.add_node("load_investigation", self._load_investigation)
        g.add_node("investigation_agent", self._investigation_node)
        g.add_node("evidence_agent", self._evidence_node)
        g.add_node("hypothesis_agent", self._hypothesis_node)
        g.add_node("hypothesis_validation", self._hypothesis_validation_node)
        g.add_node("report_agent", self._report_node)
        g.add_node("report_validation", self._report_validation_node)

        g.add_edge(START, "load_investigation")
        g.add_edge("load_investigation", "investigation_agent")
        g.add_edge("investigation_agent", "evidence_agent")
        g.add_edge("evidence_agent", "hypothesis_agent")
        g.add_edge("hypothesis_agent", "hypothesis_validation")
        g.add_conditional_edges(
            "hypothesis_validation",
            self._route_after_hypothesis_validation,
            {
                "report_agent": "report_agent",
                "evidence_agent": "evidence_agent",
                "hypothesis_agent": "hypothesis_agent",
            },
        )
        g.add_edge("report_agent", "report_validation")
        g.add_conditional_edges(
            "report_validation",
            self._route_after_report_validation,
            {"report_agent": "report_agent", "end": END},
        )
        self._graph = g
        return g.compile()

    # ------------------------------------------------------------------ nodes
    def _load_investigation(self, state: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": InvestigationStatus.LOADING.value,
            "provenance": self._append_provenance(
                state,
                step="load_investigation",
                source="orchestrator",
                description=f"request accepted for module_id={state.get('module_id')} model_id={state.get('model_id')}",
            ),
        }

    def _investigation_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        result = self.investigation_agent.run(state)
        result["status"] = InvestigationStatus.INVESTIGATING.value
        result["provenance"] = self._append_provenance(
            state,
            step="investigation_agent",
            source="deterministic_tools",
            description=(
                f"{len(result.get('deterministic_results', []))} deterministic result(s) "
                f"from {self.data_access.root}"
            ),
        )
        return result

    def _evidence_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        result = self.evidence_agent.run(state)
        result["status"] = InvestigationStatus.RETRIEVING_EVIDENCE.value
        retry_counts = dict(state.get("retry_counts", {}))
        retry_counts["evidence_round"] = retry_counts.get("evidence_round", 0) + 1
        result["retry_counts"] = retry_counts
        result["provenance"] = self._append_provenance(
            state,
            step="evidence_agent",
            source="chromadb_evidence_collection",
            description=(
                f"round {retry_counts['evidence_round']}: {len(result.get('evidence_records', []))} evidence record(s) "
                f"from queries {result.get('evidence_queries', [])}"
            ),
        )
        return result

    def _hypothesis_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        result = self.hypothesis_agent.run(state)
        result["status"] = InvestigationStatus.ANALYZING.value
        hypothesis = result.get("hypothesis")
        n_candidates = len(hypothesis.candidates) if hypothesis is not None else 0
        self._stamp_hypothesis_ids(hypothesis, state.get("investigation_id", ""))
        result["provenance"] = self._append_provenance(
            state,
            step="hypothesis_agent",
            source=f"llm:{self.llm.provider_name}/{self.llm.model_name}",
            description=f"{n_candidates} candidate mechanism(s) proposed",
        )
        return result

    def _hypothesis_validation_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        hypothesis = state.get("hypothesis")
        evidence = state.get("evidence_records", [])
        errors: List[str] = []
        if hypothesis is None:
            errors.append("no hypothesis produced by hypothesis_agent")
        elif not hypothesis.candidates:
            # A hypothesis with no candidates carries no reusable engineering
            # content; the agent is asked to retry rather than accepted silently.
            errors.append(
                "hypothesis_agent produced no candidate mechanisms"
                + (f" (note={hypothesis.note})" if hypothesis.note else "")
            )
            errors.extend(validate_hypothesis(hypothesis, evidence))
        else:
            errors.extend(validate_hypothesis(hypothesis, evidence))

        error_map = dict(state.get("errors", {}))
        retry_counts = dict(state.get("retry_counts", {}))
        if errors:
            error_map["hypothesis_validation"] = "; ".join(errors)[:2000]
            retry_counts["hypothesis_retries"] = retry_counts.get("hypothesis_retries", 0) + 1
            description = f"REJECTED ({len(errors)} issue(s)): {errors[0]}"
        else:
            error_map.pop("hypothesis_validation", None)
            description = "PASSED: every cited evidence id resolves to a retrieved record"

        return {
            "status": InvestigationStatus.VALIDATING.value,
            "errors": error_map,
            "retry_counts": retry_counts,
            "provenance": self._append_provenance(
                state,
                step="hypothesis_validation",
                source="hypothesis_validation_gate",
                description=description,
            ),
        }

    def _report_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        result = self.report_agent.run(state)
        result["status"] = InvestigationStatus.REPORTING.value
        result["provenance"] = self._append_provenance(
            state,
            step="report_agent",
            source="report_agent",
            description="report assembled from deterministic results, evidence and hypotheses",
        )
        return result

    def _report_validation_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        report = state.get("report")
        evidence = state.get("evidence_records", [])
        errors = validate_report(report, evidence)
        error_map = dict(state.get("errors", {}))
        retry_counts = dict(state.get("retry_counts", {}))
        if errors:
            error_map["report_validation"] = "; ".join(errors)[:2000]
            retry_counts["report_retries"] = retry_counts.get("report_retries", 0) + 1
            description = f"REJECTED ({len(errors)} issue(s)): {errors[0]}"
        else:
            error_map.pop("report_validation", None)
            description = "PASSED: provenance complete and no unconfirmed mechanism asserted as confirmed"
        return {
            "status": InvestigationStatus.VALIDATING.value,
            "errors": error_map,
            "retry_counts": retry_counts,
            "provenance": self._append_provenance(
                state,
                step="report_validation",
                source="report_validation_gate",
                description=description,
            ),
        }

    # -------------------------------------------------------------- routing
    def _route_after_hypothesis_validation(self, state: Dict[str, Any]) -> str:
        issue = state.get("errors", {}).get("hypothesis_validation", "")
        if not issue:
            return "report_agent"
        retry_counts = dict(state.get("retry_counts", {}))
        # An unresolvable citation means the evidence context was too thin:
        # widen it before asking the model again.
        if "unknown evidence id" in issue and retry_counts.get("evidence_round", 0) < MAX_EVIDENCE_ROUNDS:
            return "evidence_agent"
        if retry_counts.get("hypothesis_retries", 0) < MAX_HYPOTHESIS_RETRIES:
            return "hypothesis_agent"
        return "report_agent"

    def _route_after_report_validation(self, state: Dict[str, Any]) -> str:
        issue = state.get("errors", {}).get("report_validation", "")
        retry_counts = dict(state.get("retry_counts", {}))
        if not issue:
            return "end"
        if state.get("report") is None and retry_counts.get("report_retries", 0) < MAX_REPORT_RETRIES:
            return "report_agent"
        return "end"

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _stamp_hypothesis_ids(hypothesis: Any, investigation_id: str) -> None:
        """Give the hypothesis and each candidate a deterministic, traceable id.

        The ids are assigned here, overwriting anything the model may have echoed,
        so they never depend on model behaviour: the same investigation and
        candidate order always produce the same ids.
        """
        if hypothesis is None:
            return
        hypothesis.hypothesis_id = f"{investigation_id or 'inv'}-hyp"
        for index, candidate in enumerate(hypothesis.candidates, start=1):
            candidate.candidate_id = f"{hypothesis.hypothesis_id}-c{index}"

    @staticmethod
    def _append_provenance(
        state: Dict[str, Any], step: str, source: str, description: str
    ) -> List[ProvenanceEntry]:
        entries = list(state.get("provenance", []) or [])
        entries.append(
            ProvenanceEntry(step=step, source=source, description=description, timestamp=_now())
        )
        return entries

    def run(self, initial_state: Dict[str, Any]) -> Dict[str, Any]:
        return self.graph.invoke(initial_state)

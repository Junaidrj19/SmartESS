"""M9 multi-agent investigation tests: LangGraph, agents, hypothesis validation, report,
LLM failure handling, reproducibility, and end-to-end investigation."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.agents.investigation.models.hypothesis import (
    CandidateMechanism,
    Hypothesis,
    HypothesisStatus,
    MechanismType,
)
from backend.agents.investigation.models.evidence import EvidenceRecord
from backend.agents.investigation.hypothesis_agent import validate_hypothesis
from backend.agents.investigation.tools.registry import get_default_registry
from backend.llm.providers.experiential import MockLLMClient

REPO = Path(__file__).resolve().parents[2]
MODEL_ID = "iforest-v1-syn-sic-pc-dev-001-s20260922"


def _evidence(eid: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=eid,
        source_type="paper",
        title=f"Title {eid}",
        source_identifier=eid,
        retrieved_text="evidence text",
    )


class TestGraphConstruction:
    def test_graph_compiles(self):
        from backend.agents.investigation.orchestrator import InvestigationGraph

        g = InvestigationGraph()
        assert g.graph is not None

    def test_graph_nodes_present(self):
        from backend.agents.investigation.orchestrator import InvestigationGraph

        g = InvestigationGraph()
        nodes = g.graph.get_graph().nodes
        assert "investigation_agent" in nodes
        assert "evidence_agent" in nodes
        assert "hypothesis_agent" in nodes
        assert "report_agent" in nodes
        assert "load_investigation" in nodes


class TestHypothesisValidation:
    def _base_state(self, evidence, hypothesis):
        return {"evidence_records": evidence, "hypothesis": hypothesis, "retry_counts": {"hypothesis_retries": 0}}

    def test_supported_requires_evidence(self):
        hyp = Hypothesis(
            module_id="m1",
            candidates=[
                CandidateMechanism(
                    mechanism=MechanismType.bond_wire_interconnect,
                    status=HypothesisStatus.SUPPORTED,
                    confidence=0.8,
                    reasoning="no evidence cited",
                )
            ],
        )
        errors = validate_hypothesis(hyp, [_evidence("ev-1")])
        assert errors

    def test_valid_supported(self):
        hyp = Hypothesis(
            module_id="m1",
            candidates=[
                CandidateMechanism(
                    mechanism=MechanismType.bond_wire_interconnect,
                    status=HypothesisStatus.SUPPORTED,
                    confidence=0.8,
                    supporting_evidence_ids=["ev-1"],
                    reasoning="RDS_on increase reported",
                )
            ],
        )
        errors = validate_hypothesis(hyp, [_evidence("ev-1")])
        assert errors == []

    def test_missing_evidence_id(self):
        hyp = Hypothesis(
            module_id="m1",
            candidates=[
                CandidateMechanism(
                    mechanism=MechanismType.gate_related,
                    status=HypothesisStatus.SUPPORTED,
                    confidence=0.7,
                    supporting_evidence_ids=["ev-999"],
                    reasoning="x",
                )
            ],
        )
        errors = validate_hypothesis(hyp, [_evidence("ev-1")])
        assert any("unknown evidence" in e or "999" in e for e in errors)

    def test_invalid_confidence(self):
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CandidateMechanism(
                mechanism=MechanismType.gate_related,
                status=HypothesisStatus.CANDIDATE,
                confidence=99.0,
                supporting_evidence_ids=["ev-1"],
                reasoning="confidence test",
            )

    def test_insufficient_evidence_requires_reason(self):
        hyp = Hypothesis(
            module_id="m1",
            candidates=[
                CandidateMechanism(
                    mechanism=MechanismType.other,
                    status=HypothesisStatus.INSUFFICIENT_EVIDENCE,
                    confidence=0.2,
                    reasoning="",
                )
            ],
        )
        errors = validate_hypothesis(hyp, [])
        assert errors


class TestHypothesisAgentMockedLLM:
    def test_valid_structured_response(self):
        from backend.agents.investigation.hypothesis_agent import HypothesisAgent

        llm = MockLLMClient()
        llm.enqueue(
            Hypothesis(
                module_id="m1",
                candidates=[
                    CandidateMechanism(
                        mechanism=MechanismType.bond_wire_interconnect,
                        status=HypothesisStatus.SUPPORTED,
                        confidence=0.8,
                        supporting_evidence_ids=["ev-1"],
                        reasoning="RDS_on increase",
                    )
                ],
            )
        )
        agent = HypothesisAgent(llm=llm)
        state = {"module_id": "m1", "deterministic_results": [], "evidence_records": [_evidence("ev-1")]}
        out = agent.run(state)
        assert out["hypothesis"].module_id == "m1"
        assert out["hypothesis"].candidates[0].confidence == pytest.approx(0.8)

    def test_llm_failure_degrades(self):
        from backend.agents.investigation.hypothesis_agent import HypothesisAgent

        class _FailLLM(MockLLMClient):
            def structured_completion(self, messages=None, response_model=None, system="", **kw):
                raise RuntimeError("API unavailable")

        agent = HypothesisAgent(llm=_FailLLM())
        out = agent.run({"module_id": "m1", "deterministic_results": [], "evidence_records": []})
        assert out["hypothesis"].candidates == []
        assert "llm" in out.get("errors", {}) or out["hypothesis"].note == "llm_failed"


class TestReportAgent:
    def test_required_sections(self):
        from backend.agents.investigation.report_agent import ReportAgent

        agent = ReportAgent()
        state = {
            "investigation_id": "inv-1",
            "module_id": "m1",
            "model_id": MODEL_ID,
            "status": "COMPLETED",
            "module_trajectory": None,
            "deterministic_results": [],
            "evidence_records": [],
            "hypothesis": None,
            "limitations": [],
            "provenance": [],
        }
        out = agent.run(state)
        titles = [s["title"] for s in out["report"].sections]
        for req in [
            "Component Information",
            "Test Configuration",
            "Data Quality",
            "Observed Degradation",
            "Anomaly Analysis",
            "Model Results",
            "Candidate Failure Mechanisms",
            "Supporting Evidence",
            "Recommended Investigation",
            "Limitations",
            "Provenance",
        ]:
            assert req in titles, req
        assert out["report"].full_text


class TestGraphTopology:
    REQUIRED_NODES = [
        "load_investigation",
        "investigation_agent",
        "evidence_agent",
        "hypothesis_agent",
        "hypothesis_validation",
        "report_agent",
        "report_validation",
    ]

    def _graph(self):
        from backend.agents.investigation.orchestrator import InvestigationGraph

        return InvestigationGraph().graph.get_graph()

    def test_all_agent_and_validation_nodes_present(self):
        nodes = self._graph().nodes
        for required in self.REQUIRED_NODES:
            assert required in nodes, required

    def test_forward_edges(self):
        edges = {(e.source, e.target) for e in self._graph().edges}
        for edge in [
            ("load_investigation", "investigation_agent"),
            ("investigation_agent", "evidence_agent"),
            ("evidence_agent", "hypothesis_agent"),
            ("hypothesis_agent", "hypothesis_validation"),
            ("report_agent", "report_validation"),
        ]:
            assert edge in edges, edge

    def test_hypothesis_validation_is_a_conditional_gate(self):
        g = self._graph()
        conditional = [e.target for e in g.edges if e.source == "hypothesis_validation" and e.conditional]
        assert "report_agent" in conditional
        assert "hypothesis_agent" in conditional

    def test_report_validation_can_end(self):
        g = self._graph()
        targets = {e.target for e in g.edges if e.source == "report_validation"}
        assert "__end__" in targets


class _StubEvidenceAgent:
    """Evidence agent returning fixed records, so retry behaviour is testable
    without depending on the contents of the production corpus."""

    def __init__(self, records):
        self.records = records

    def run(self, state):
        return {
            "evidence_records": list(self.records),
            "evidence_queries": ["stub evidence query"],
            "evidence_status": "available",
            "limitations": list(state.get("limitations", []) or []),
        }


class TestHypothesisValidationRouting:
    def _graph(self):
        from backend.agents.investigation.orchestrator import InvestigationGraph

        return InvestigationGraph()

    def _state(self, issue="", evidence_round=0, hypothesis_retries=0):
        errors = {"hypothesis_validation": issue} if issue else {}
        return {
            "errors": errors,
            "retry_counts": {"evidence_round": evidence_round, "hypothesis_retries": hypothesis_retries},
        }

    def test_passing_hypothesis_routes_to_report(self):
        assert self._graph()._route_after_hypothesis_validation(self._state()) == "report_agent"

    def test_fabricated_citation_requests_more_evidence_first(self):
        state = self._state("candidate gate_related references unknown evidence id: ev-fake")
        assert self._graph()._route_after_hypothesis_validation(state) == "evidence_agent"

    def test_retries_are_bounded_then_report_is_produced(self):
        from backend.agents.investigation.state import MAX_EVIDENCE_ROUNDS, MAX_HYPOTHESIS_RETRIES

        g = self._graph()
        issue = "candidate gate_related references unknown evidence id: ev-fake"
        exhausted = self._state(issue, evidence_round=MAX_EVIDENCE_ROUNDS, hypothesis_retries=MAX_HYPOTHESIS_RETRIES)
        assert g._route_after_hypothesis_validation(exhausted) == "report_agent"

    def test_non_citation_failure_retries_hypothesis(self):
        issue = "candidate bond_wire_interconnect status SUPPORTED requires at least one supporting evidence id"
        assert self._graph()._route_after_hypothesis_validation(self._state(issue)) == "hypothesis_agent"

    def test_empty_hypothesis_is_rejected_by_the_gate(self):
        out = self._graph()._hypothesis_validation_node({
            "hypothesis": Hypothesis(module_id="syn-mod-0042", candidates=[], note="llm_failed"),
            "evidence_records": [],
            "retry_counts": {"evidence_round": 0, "hypothesis_retries": 0},
            "errors": {},
            "provenance": [],
        })
        assert "no candidate mechanisms" in out["errors"]["hypothesis_validation"]
        assert out["retry_counts"]["hypothesis_retries"] == 1

    def test_missing_hypothesis_is_rejected_by_the_gate(self):
        out = self._graph()._hypothesis_validation_node({
            "hypothesis": None,
            "evidence_records": [],
            "retry_counts": {"evidence_round": 0, "hypothesis_retries": 1},
            "errors": {},
            "provenance": [],
        })
        assert "no hypothesis produced" in out["errors"]["hypothesis_validation"]


class TestReportValidation:
    def _report_for(self, hypothesis):
        from backend.agents.investigation.models.investigation import ProvenanceEntry
        from backend.agents.investigation.report_agent import ReportAgent

        state = {
            "investigation_id": "inv-1",
            "module_id": "syn-mod-0042",
            "model_id": MODEL_ID,
            "status": "VALIDATING",
            "module_trajectory": None,
            "deterministic_results": [],
            "evidence_records": [_evidence("ev-1")],
            "hypothesis": hypothesis,
            "limitations": [],
            "provenance": [
                ProvenanceEntry(step="investigation_agent", source="deterministic_tools", description="stub")
            ],
        }
        return ReportAgent().run(state)["report"]

    def _hypothesis(self, evidence_ids, status=HypothesisStatus.SUPPORTED):
        return Hypothesis(
            module_id="syn-mod-0042",
            candidates=[
                CandidateMechanism(
                    mechanism=MechanismType.bond_wire_interconnect,
                    status=status,
                    confidence=0.6,
                    supporting_evidence_ids=list(evidence_ids),
                    reasoning="candidate mechanism, consistent with the retrieved evidence",
                )
            ],
        )

    def test_generated_report_passes_validation(self):
        from backend.agents.investigation.report_agent import validate_report

        report = self._report_for(self._hypothesis(["ev-1"]))
        assert validate_report(report, [_evidence("ev-1")]) == []

    def test_fabricated_citation_is_rejected(self):
        from backend.agents.investigation.report_agent import validate_report

        report = self._report_for(self._hypothesis(["ev-1"]))
        errors = validate_report(report, [])  # no evidence records at all
        assert any("unknown evidence id: ev-1" in e for e in errors)

    def test_confirmed_mechanism_is_rejected(self):
        from backend.agents.investigation.report_agent import ReportAgent, validate_report

        report = self._report_for(self._hypothesis(["ev-1"]))
        for section in report.sections:
            if section["title"] == "Candidate Failure Mechanisms":
                section["findings"][0]["classification"] = "CONFIRMED"
        errors = validate_report(report, [_evidence("ev-1")])
        assert any("CONFIRMED" in e for e in errors)

    def test_missing_section_is_rejected(self):
        from backend.agents.investigation.report_agent import validate_report

        report = self._report_for(self._hypothesis(["ev-1"]))
        report.sections = [s for s in report.sections if s["title"] != "Human Review"]
        errors = validate_report(report, [_evidence("ev-1")])
        assert any("Human Review" in e for e in errors)

    def test_unwarranted_certainty_is_rejected(self):
        from backend.agents.investigation.report_agent import validate_report

        report = self._report_for(self._hypothesis(["ev-1"]))
        report.full_text += "\nThe anomaly is a confirmed physical failure of the gate oxide."
        errors = validate_report(report, [_evidence("ev-1")])
        assert any("certainty" in e for e in errors)

    def test_human_review_and_interpretation_sections_present(self):
        report = self._report_for(self._hypothesis(["ev-1"]))
        titles = [s["title"] for s in report.sections]
        for expected in ["Contradictory Evidence", "Uncertainty", "Engineering Interpretation", "Human Review"]:
            assert expected in titles
        human_review = [s for s in report.sections if s["title"] == "Human Review"][0]
        assert "human engineer" in human_review["findings"][0]["detail"]


class TestValidationGatesEndToEnd:
    def test_fabricated_citation_triggers_retry_and_is_corrected(self):
        from backend.agents.investigation.hypothesis_agent import HypothesisAgent
        from backend.agents.investigation.orchestrator import InvestigationGraph
        from backend.agents.investigation.pipeline import run_investigation

        llm = MockLLMClient()
        llm.enqueue(
            Hypothesis(
                module_id="syn-mod-0042",
                candidates=[
                    CandidateMechanism(
                        mechanism=MechanismType.gate_related,
                        status=HypothesisStatus.SUPPORTED,
                        confidence=0.7,
                        supporting_evidence_ids=["ev-does-not-exist"],
                        reasoning="cites a fabricated evidence id",
                    )
                ],
            )
        )
        llm.enqueue(
            Hypothesis(
                module_id="syn-mod-0042",
                candidates=[
                    CandidateMechanism(
                        mechanism=MechanismType.gate_related,
                        status=HypothesisStatus.CANDIDATE,
                        confidence=0.4,
                        supporting_evidence_ids=["ev-1"],
                        reasoning="candidate mechanism supported by real retrieved evidence",
                    )
                ],
            )
        )
        graph = InvestigationGraph(
            evidence_agent=_StubEvidenceAgent([_evidence("ev-1")]),
            hypothesis_agent=HypothesisAgent(llm=llm),
        )
        record = run_investigation("syn-mod-0042", MODEL_ID, graph=graph)

        steps = [p.step for p in record.provenance]
        assert steps.count("hypothesis_validation") >= 2, steps
        assert steps.index("hypothesis_validation") < steps.index("report_validation")
        assert "hypothesis_validation" not in record.errors
        assert "report_validation" not in record.errors
        assert record.hypothesis.candidates[0].supporting_evidence_ids == ["ev-1"]
        assert llm.call_count >= 2
        assert record.evidence_queries
        # Deterministic, traceable ids stamped by the orchestrator.
        assert record.hypothesis.hypothesis_id == f"{record.investigation_id}-hyp"
        assert record.hypothesis.candidates[0].candidate_id.endswith("-c1")


class TestEndToEnd:
    def test_reproducible_deterministic_results(self):
        from backend.agents.investigation.data_access import DataAccess
        from backend.agents.investigation.investigation_agent import InvestigationAgent

        da = DataAccess(REPO)
        a = InvestigationAgent(da)
        b = InvestigationAgent(da)
        sa = a.run({"module_id": "syn-mod-0042", "model_id": MODEL_ID})
        sb = b.run({"module_id": "syn-mod-0042", "model_id": MODEL_ID})
        assert len(sa["deterministic_results"]) > 0
        assert len(sa["deterministic_results"]) == len(sb["deterministic_results"])
        assert [r.tool_name for r in sa["deterministic_results"]] == [r.tool_name for r in sb["deterministic_results"]]

    def test_full_investigation_runs(self, tmp_path):
        from backend.agents.investigation.pipeline import run_investigation

        llm = MockLLMClient()
        from backend.agents.investigation.orchestrator import InvestigationGraph
        from backend.agents.investigation.hypothesis_agent import HypothesisAgent

        llm.enqueue(
            Hypothesis(
                module_id="syn-mod-0042",
                candidates=[
                    CandidateMechanism(
                        mechanism=MechanismType.bond_wire_interconnect,
                        status=HypothesisStatus.CANDIDATE,
                        confidence=0.6,
                        reasoning="initial candidate",
                    )
                ],
            )
        )
        agent = HypothesisAgent(llm=llm)
        g = InvestigationGraph(hypothesis_agent=agent)
        record = run_investigation(
            "syn-mod-0042", MODEL_ID, graph=g
        )
        assert record.status.value in ("COMPLETED", "PARTIAL")
        assert len(record.deterministic_results) > 0
        assert record.investigation_id
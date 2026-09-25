from __future__ import annotations

import json
from typing import Any, Dict, List

from backend.agents.investigation.models.evidence import EvidenceRecord
from backend.agents.investigation.models.hypothesis import (
    CandidateMechanism,
    Hypothesis,
    HypothesisStatus,
    MechanismType,
)
from backend.llm.factory import create_mock_client
from backend.llm.interface import LLMClient, LLMMessage
from backend.llm.settings import LLMSettings

MAX_EVIDENCE_CHARS = 1200
MAX_DETERMINISTIC_RESULTS = 40
MAX_CONTEXT_CHARS = 24000

SYSTEM_PROMPT = """You are the hypothesis agent of a SiC MOSFET reliability investigation.

You receive deterministic degradation calculations computed by fixed engineering tools, and
retrieved passages from an engineering knowledge base. Propose CANDIDATE degradation mechanisms.

Epistemic rules (non-negotiable):
1. Never assert a physical failure as confirmed. Every mechanism is a candidate that requires
   engineering confirmation.
2. Never claim a one-to-one diagnostic mapping. RDS_on, VTH, IGSS, IDSS, Tj and related signals
   can each be affected by several mechanisms (temperature, channel/device degradation, package and
   interconnect degradation, measurement conditions/hysteresis), so state the ambiguity explicitly.
3. Only cite evidence ids that appear verbatim in the evidence_records provided. Never invent,
   renumber or paraphrase an evidence id.
4. Status semantics: SUPPORTED = the provided evidence actively argues for the candidate;
   CONTRADICTED = the provided evidence argues against it; CANDIDATE = plausible but
   incompletely supported; AMBIGUOUS = the evidence fits several mechanisms equally;
   INSUFFICIENT_EVIDENCE = the evidence cannot discriminate. Prefer INSUFFICIENT_EVIDENCE over
   speculation, and always give a reasoning string explaining the status.
5. Put evidence that argues against a candidate in contradictory_evidence_ids, and describe the
   residual uncertainty and measurement limitations in reasoning.
6. distinguishing_measurements lists the measurements that would separate this candidate from the
   alternatives.
7. Do not invent numerical values: quote only numbers that appear in the deterministic results.

Mechanism must be one of: bond_wire_interconnect, die_attach_thermal_path, gate_related,
thermal_path, package_interconnect, other."""


class HypothesisValidationError(ValueError):
    pass


class HypothesisAgent:
    def __init__(self, llm: LLMClient | None = None, settings: LLMSettings | None = None):
        self.settings = settings or LLMSettings()
        self.llm = llm or create_mock_client()

    def _build_context(self, state: Dict[str, Any]) -> str:
        parts = [f"module_id: {state.get('module_id')}", f"model_id: {state.get('model_id')}"]

        deterministic = state.get("deterministic_results", []) or []
        parts.append(f"deterministic_results ({len(deterministic)} total):")
        for r in deterministic[:MAX_DETERMINISTIC_RESULTS]:
            parts.append(json.dumps({
                "tool": r.tool_name,
                "input": r.input_summary,
                "output": r.output,
            }))

        evidence = state.get("evidence_records", []) or []
        parts.append(f"evidence_records ({len(evidence)} total):")
        for e in evidence:
            parts.append(json.dumps({
                "evidence_id": e.evidence_id,
                "document_id": e.document_id,
                "title": e.title,
                "source_type": e.source_type,
                "citation": e.citation,
                "page_start": e.page_start,
                "page_end": e.page_end,
                "mechanisms": e.mechanisms,
                "observables": e.observables,
                "test_conditions": e.test_conditions,
                "text": (e.retrieved_text or "")[:MAX_EVIDENCE_CHARS],
            }))

        validation_errors = (state.get("errors") or {}).get("hypothesis_validation")
        if validation_errors:
            parts.append(
                "previous_attempt_rejected_by_validation: " + str(validation_errors)[:1500]
                + "\nFix the rejection: cite only evidence ids listed above."
            )

        return "\n".join(parts)[:MAX_CONTEXT_CHARS]

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        if self.llm is None:
            hypothesis = Hypothesis(
                module_id=state.get("module_id", ""),
                candidates=[],
                note="llm_unavailable",
            )
            return {"hypothesis": hypothesis, "errors": {"hypothesis": "LLM unavailable; no hypothesis generated"}}

        context = self._build_context(state)
        messages = [LLMMessage(role="user", content=context)]
        try:
            hypothesis = self.llm.structured_completion(
                messages,
                system=SYSTEM_PROMPT,
                response_model=Hypothesis,
                temperature=0.1,
                max_tokens=6000,
            )
        except Exception as e:
            return {
                "hypothesis": Hypothesis(
                    module_id=state.get("module_id", ""),
                    candidates=[],
                    note="llm_failed",
                ),
                "errors": {"hypothesis": f"LLM failure ({self.llm.provider_name}): {e}"},
                "limitations": ["llm_reasoning_unavailable"],
            }
        return {"hypothesis": hypothesis}


def validate_hypothesis(hypothesis: Hypothesis, evidence_records: List[EvidenceRecord]) -> List[str]:
    errors = []
    known_ids = {e.evidence_id for e in evidence_records}
    for c in hypothesis.candidates:
        if c.confidence < 0.0 or c.confidence > 1.0:
            errors.append(f"candidate {c.mechanism} confidence out of range: {c.confidence}")
        if c.status in (HypothesisStatus.CANDIDATE, HypothesisStatus.SUPPORTED, HypothesisStatus.CONTRADICTED):
            if not c.supporting_evidence_ids:
                errors.append(f"candidate {c.mechanism} status {c.status} requires at least one supporting evidence id")
        for eid in c.supporting_evidence_ids + c.contradictory_evidence_ids:
            if eid not in known_ids:
                errors.append(f"candidate {c.mechanism} references unknown evidence id: {eid}")
        if c.status in (HypothesisStatus.INSUFFICIENT_EVIDENCE, HypothesisStatus.AMBIGUOUS):
            if not c.supporting_evidence_ids and not c.reasoning:
                errors.append(f"candidate {c.mechanism} {c.status} must explain the explicit reason")
    return errors

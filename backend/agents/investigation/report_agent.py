from __future__ import annotations

from typing import Any, Dict, List

from backend.agents.investigation.models.evidence import EvidenceRecord
from backend.agents.investigation.models.investigation import (
    InvestigationReport,
)
from backend.agents.investigation.models.report import (
    Finding,
    FindingClassification,
    ReportSection,
    ReportSections,
)

REQUIRED_REPORT_SECTIONS = [
    "Component Information",
    "Test Configuration",
    "Data Quality",
    "Observed Degradation",
    "Anomaly Analysis",
    "Model Results",
    "Candidate Failure Mechanisms",
    "Supporting Evidence",
    "Contradictory Evidence",
    "Uncertainty",
    "Engineering Interpretation",
    "Recommended Investigation",
    "Limitations",
    "Provenance",
    "Human Review",
]

# Phrases that would assert a physical failure as established fact. The report
# must keep every mechanism at candidate/epistemic status.
CERTAINTY_PATTERNS = (
    "confirmed physical failure",
    "confirmed the failure",
    "conclusively diagnosed",
    "definitively confirmed",
    "is proven",
)


class ReportAgent:
    """Deterministic report synthesis.

    The report is composed only from values already present in the investigation
    state (deterministic tool output, retrieved evidence, validated hypotheses).
    It recalculates nothing, invents nothing, and adds no measurement that the
    deterministic layer did not produce.
    """

    def __init__(self, llm: Any | None = None):
        # Reserved for future narrative generation; synthesis is deterministic today.
        self.llm = llm

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        sections = self._build_sections(state)
        narrative = self._build_narrative(sections)
        report = InvestigationReport(
            investigation_id=state.get("investigation_id", ""),
            module_id=state.get("module_id", ""),
            model_id=state.get("model_id", ""),
            sections=[s.model_dump() for s in sections],
            full_text=narrative,
        )
        return {"report": report}

    def _build_sections(self, state: Dict[str, Any]) -> List[ReportSection]:
        module_id = state.get("module_id", "")
        model_id = state.get("model_id", "")
        tr = state.get("module_trajectory")
        hypothesis = state.get("hypothesis")
        candidates = list(hypothesis.candidates) if hypothesis is not None else []
        evidence_records: List[EvidenceRecord] = list(state.get("evidence_records", []) or [])

        def finding(label, classification, detail, source="", evidence_ids=None):
            return Finding(
                label=label,
                classification=classification,
                detail=detail,
                source=source,
                evidence_ids=evidence_ids or [],
            )

        sections = ReportSections()
        sections.component_information.findings = [
            finding("module_id", FindingClassification.OBSERVED, module_id, source="m6/m7"),
        ]
        sections.test_configuration.findings = [
            finding("model_id", FindingClassification.OBSERVED, model_id, source="m7"),
        ]
        sections.data_quality.findings = [
            finding(
                "n_observations",
                FindingClassification.OBSERVED,
                str((tr.n_observations if tr else "n/a")),
                source="m6",
            )
        ]
        sections.observed_degradation.findings = [
            finding(
                r.tool_name,
                FindingClassification.CALCULATED,
                str(r.output),
                source="deterministic_tool",
            )
            for r in (state.get("deterministic_results", []) or [])[:10]
        ]
        sections.anomaly_analysis.findings = [
            finding(
                "max_anomaly_score",
                FindingClassification.OBSERVED,
                str((tr.max_score if tr else "n/a")),
                source="m7",
            ),
            finding(
                "mean_anomaly_score",
                FindingClassification.OBSERVED,
                str((tr.mean_score if tr else "n/a")),
                source="m7",
            ),
        ]
        sections.model_results.findings = [
            finding("status", FindingClassification.OBSERVED, str(state.get("status", "")), source="m9"),
            finding(
                "evidence_documents_retrieved",
                FindingClassification.OBSERVED,
                str(len({e.document_id for e in evidence_records if e.document_id})),
                source="chromadb_evidence_collection",
            ),
        ]
        sections.candidate_failure_mechanisms.findings = [
            finding(
                c.mechanism.value,
                FindingClassification.HYPOTHESIZED,
                f"{c.candidate_id or c.mechanism.value}: {c.status.value} "
                f"confidence={c.confidence:.2f}; {c.reasoning}",
                source="hypothesis_agent",
                evidence_ids=c.supporting_evidence_ids,
            )
            for c in candidates
        ]
        sections.supporting_evidence.findings = [
            finding(
                e.evidence_id,
                FindingClassification.OBSERVED,
                f"{e.title} ({e.source_type}); citation: {e.citation or 'n/a'}; "
                f"page range: {e.page_start or 'n/a'}-{e.page_end or 'n/a'}",
                source=e.source_type,
                evidence_ids=[e.evidence_id],
            )
            for e in evidence_records
        ]
        contradictory = [
            finding(
                c.mechanism.value,
                FindingClassification.OBSERVED,
                "contradictory evidence cited against this candidate",
                source="hypothesis_agent",
                evidence_ids=c.contradictory_evidence_ids,
            )
            for c in candidates
            if c.contradictory_evidence_ids
        ] or [
            finding(
                "contradictory_evidence",
                FindingClassification.OBSERVED,
                "none of the candidate mechanisms was contradicted by the retrieved corpus",
                source="report_agent",
            )
        ]
        sections.contradictory_evidence.findings = contradictory
        sections.uncertainty.findings = [
            finding(
                f"{c.mechanism.value}_uncertainty",
                FindingClassification.OBSERVED,
                f"status={c.status.value}, confidence={c.confidence:.2f}",
                source="hypothesis_agent",
                evidence_ids=c.supporting_evidence_ids + c.contradictory_evidence_ids,
            )
            for c in candidates
        ] + [
            finding(
                "signal_to_mechanism_ambiguity",
                FindingClassification.OBSERVED,
                "An anomaly score or degradation trend is suggestive of, but does not establish, a "
                "specific physical mechanism: the same observable can respond to temperature, "
                "channel/device degradation, package degradation and measurement conditions.",
                source="report_agent",
            )
        ]
        sections.engineering_interpretation.findings = [
            finding(
                c.mechanism.value,
                FindingClassification.HYPOTHESIZED,
                self._interpretation(c),
                source="hypothesis_agent",
                evidence_ids=c.supporting_evidence_ids,
            )
            for c in candidates
        ] + [
            finding(
                "interpretation_scope",
                FindingClassification.OBSERVED,
                "Interpretation is based on deterministic calculations over frozen M6/M7/M8 "
                "artifacts plus retrieved engineering literature. Confirming any candidate "
                "mechanism requires engineering confirmation on the physical hardware.",
                source="report_agent",
            )
        ]
        sections.recommended_investigation.findings = [
            finding(
                "distinguishing_measurements",
                FindingClassification.RECOMMENDED,
                ", ".join(m for c in candidates for m in c.distinguishing_measurements)
                or "no distinguishing measurement proposed",
                source="hypothesis_agent",
            )
        ]
        limitations = list(state.get("limitations", []) or [])
        report_validation_error = (state.get("errors") or {}).get("report_validation")
        if report_validation_error:
            limitations.append(f"report_validation_failed: {report_validation_error}")
        sections.limitations.findings = [
            finding("limitation", FindingClassification.OBSERVED, lim)
            for lim in limitations
        ] or [
            finding("limitation", FindingClassification.OBSERVED, "none recorded", source="m9")
        ]
        sections.provenance.findings = [
            finding("provenance", FindingClassification.OBSERVED, f"{p.step}: {p.source} — {p.description}")
            for p in (state.get("provenance", []) or [])
        ]
        sections.human_review.findings = [
            finding(
                "final_decision",
                FindingClassification.RECOMMENDED,
                "The final engineering decision remains with the human engineer. This report "
                "presents candidate mechanisms that are consistent with the evidence retrieved; it "
                "does not confirm a physical hardware failure and requires engineering confirmation.",
                source="m9",
            )
        ]
        return [
            sections.component_information,
            sections.test_configuration,
            sections.data_quality,
            sections.observed_degradation,
            sections.anomaly_analysis,
            sections.model_results,
            sections.candidate_failure_mechanisms,
            sections.supporting_evidence,
            sections.contradictory_evidence,
            sections.uncertainty,
            sections.engineering_interpretation,
            sections.recommended_investigation,
            sections.limitations,
            sections.provenance,
            sections.human_review,
        ]

    @staticmethod
    def _interpretation(candidate) -> str:
        wording = {
            "SUPPORTED": "evidence-supported hypothesis, consistent with",
            "CANDIDATE": "candidate mechanism, suggestive of",
            "CONTRADICTED": "candidate mechanism contradicted by the retrieved evidence",
            "AMBIGUOUS": "ambiguous candidate mechanism; the evidence fits several mechanisms",
            "INSUFFICIENT_EVIDENCE": "insufficient evidence to associate the observed behaviour with",
        }.get(candidate.status.value, "candidate mechanism involving")
        return (
            f"{wording} {candidate.mechanism.value} (confidence={candidate.confidence:.2f}). "
            f"{candidate.reasoning}"
        )

    def _build_narrative(self, sections: List[ReportSection]) -> str:
        lines = []
        for section in sections:
            lines.append(f"## {section.title}")
            for f in section.findings:
                lines.append(f"- [{f.classification.value}] {f.label}: {f.detail}")
        return "\n".join(lines)


def validate_report(report: Any, evidence_records: List[EvidenceRecord]) -> List[str]:
    """Validate a generated report before it is accepted as the investigation output.

    Checks that the report is complete, that every citation resolves to a
    retrieved evidence record, that no candidate mechanism is asserted as
    confirmed, and that the narrative avoids unwarranted certainty.
    """
    if report is None:
        return ["no report produced by report_agent"]

    errors: List[str] = []
    known_ids = {e.evidence_id for e in evidence_records}
    sections = list(getattr(report, "sections", []) or [])
    titles = [s.get("title", "") for s in sections]

    for required in REQUIRED_REPORT_SECTIONS:
        if required not in titles:
            errors.append(f"missing required report section: {required}")

    for section in sections:
        title = section.get("title", "")
        for finding in section.get("findings", []) or []:
            for evidence_id in finding.get("evidence_ids", []) or []:
                if evidence_id not in known_ids:
                    errors.append(
                        f"finding '{finding.get('label')}' cites unknown evidence id: {evidence_id}"
                    )
            if title == "Candidate Failure Mechanisms" and (
                finding.get("classification") == FindingClassification.CONFIRMED.value
            ):
                errors.append(
                    f"mechanism finding '{finding.get('label')}' asserted as CONFIRMED; "
                    "candidate mechanisms must remain unconfirmed"
                )

    narrative = (getattr(report, "full_text", "") or "").strip()
    if not narrative:
        errors.append("report narrative is empty")
    lowered = narrative.lower()
    for pattern in CERTAINTY_PATTERNS:
        if pattern in lowered:
            errors.append(f"report asserts unwarranted certainty with phrase: {pattern!r}")

    if not any(s.get("title") == "Provenance" and s.get("findings") for s in sections):
        errors.append("report carries no provenance entries")

    return errors

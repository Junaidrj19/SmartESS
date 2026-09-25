from __future__ import annotations

from typing import Annotated, Any, Dict, List, Optional

from langgraph.graph import add_messages
from typing_extensions import TypedDict

from backend.agents.investigation.models.evidence import EvidenceRecord
from backend.agents.investigation.models.hypothesis import Hypothesis
from backend.agents.investigation.models.investigation import (
    DeterministicResult,
    InvestigationRecord,
    InvestigationReport,
    InvestigationStatus,
    ModuleTrajectory,
    ProvenanceEntry,
)


class InvestigationState(TypedDict):
    investigation_id: str
    module_id: str
    model_id: str
    dataset_id: str
    status: str

    module_trajectory: Optional[ModuleTrajectory]
    m7_module_summary: Dict[str, Any]
    m8_module_evaluation: Dict[str, Any]
    m8_timing: Dict[str, Any]
    m8_baseline: Dict[str, Any]

    module_profile: Dict[str, Any]
    test_profile: Dict[str, Any]

    deterministic_results: List[DeterministicResult]
    evidence_records: List[EvidenceRecord]
    evidence_queries: List[str]

    hypothesis: Optional[Hypothesis]
    report: Optional[InvestigationReport]

    provenance: List[ProvenanceEntry]
    agent_messages: Dict[str, str]
    retry_counts: Dict[str, int]
    errors: Dict[str, str]
    limitations: List[str]

    messages: Annotated[List[str], add_messages]


INITIAL_STATE: InvestigationState = {
    "investigation_id": "",
    "module_id": "",
    "model_id": "",
    "dataset_id": "",
    "status": InvestigationStatus.PENDING.value,
    "module_trajectory": None,
    "m7_module_summary": {},
    "m8_module_evaluation": {},
    "m8_timing": {},
    "m8_baseline": {},
    "module_profile": {},
    "test_profile": {},
    "deterministic_results": [],
    "evidence_records": [],
    "evidence_queries": [],
    "hypothesis": None,
    "report": None,
    "provenance": [],
    "agent_messages": {},
    "retry_counts": {"evidence_round": 0, "hypothesis_retries": 0, "report_retries": 0},
    "errors": {},
    "limitations": [],
    "messages": [],
}


MAX_EVIDENCE_ROUNDS = 2
MAX_HYPOTHESIS_RETRIES = 2
MAX_REPORT_RETRIES = 2
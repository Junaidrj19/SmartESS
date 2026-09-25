from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.agents.investigation.models.evidence import EvidenceRecord
from backend.agents.investigation.models.hypothesis import Hypothesis


class InvestigationStatus(str, Enum):
    PENDING = "PENDING"
    LOADING = "LOADING"
    INVESTIGATING = "INVESTIGATING"
    RETRIEVING_EVIDENCE = "RETRIEVING_EVIDENCE"
    ANALYZING = "ANALYZING"
    REPORTING = "REPORTING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PARTIAL = "PARTIAL"


class ModuleTrajectory(BaseModel):
    module_id: str
    n_observations: int = 0
    n_cycles: int = 0
    signals: Dict[str, List[float]] = {}
    cycle_numbers: List[int] = []
    min_score: float = 0.0
    max_score: float = 0.0
    mean_score: float = 0.0


class DeterministicResult(BaseModel):
    tool_name: str
    tool_version: str
    input_summary: Dict[str, Any] = {}
    output: Dict[str, Any] = {}
    provenance: Dict[str, Any] = {}


class ProvenanceEntry(BaseModel):
    step: str
    source: str
    description: str
    timestamp: str = ""


class InvestigationRecord(BaseModel):
    investigation_id: str = Field(default_factory=lambda: f"inv-{uuid4().hex[:12]}")
    module_id: str
    model_id: str
    dataset_id: str = ""
    status: InvestigationStatus = InvestigationStatus.PENDING
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    module_trajectory: Optional[ModuleTrajectory] = None
    m7_module_summary: Dict[str, Any] = {}
    m8_module_evaluation: Dict[str, Any] = {}
    m8_timing: Dict[str, Any] = {}
    m8_baseline: Dict[str, Any] = {}
    deterministic_results: List[DeterministicResult] = []
    evidence_records: List[EvidenceRecord] = []
    evidence_queries: List[str] = []
    hypothesis: Optional[Hypothesis] = None
    report: Optional[InvestigationReport] = None
    provenance: List[ProvenanceEntry] = []
    agent_messages: Dict[str, str] = {}
    retry_counts: Dict[str, int] = {}
    errors: Dict[str, str] = {}
    limitations: List[str] = []


class InvestigationReport(BaseModel):
    investigation_id: str
    module_id: str
    model_id: str
    sections: List[Dict[str, Any]] = []
    full_text: str = ""
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
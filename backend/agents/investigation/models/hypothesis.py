from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class MechanismType(str, Enum):
    bond_wire_interconnect = "bond_wire_interconnect"
    die_attach_thermal_path = "die_attach_thermal_path"
    gate_related = "gate_related"
    thermal_path = "thermal_path"
    package_interconnect = "package_interconnect"
    other = "other"


class HypothesisStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    AMBIGUOUS = "AMBIGUOUS"


class CandidateMechanism(BaseModel):
    mechanism: MechanismType
    status: HypothesisStatus
    confidence: float = Field(ge=0.0, le=1.0)
    candidate_id: str = ""
    supporting_evidence_ids: List[str] = []
    contradictory_evidence_ids: List[str] = []
    reasoning: str
    distinguishing_measurements: List[str] = []


class Hypothesis(BaseModel):
    module_id: str
    hypothesis_id: str = ""
    candidates: List[CandidateMechanism] = []
    primary_mechanism: Optional[MechanismType] = None
    note: str = ""
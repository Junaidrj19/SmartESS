from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class FindingClassification(str, Enum):
    OBSERVED = "OBSERVED"
    CALCULATED = "CALCULATED"
    PREDICTED = "PREDICTED"
    HYPOTHESIZED = "HYPOTHESIZED"
    CONFIRMED = "CONFIRMED"
    RECOMMENDED = "RECOMMENDED"


class Finding(BaseModel):
    label: str
    classification: FindingClassification
    detail: str
    source: str = ""
    evidence_ids: List[str] = []


class ReportSection(BaseModel):
    title: str
    findings: List[Finding] = []
    narrative: str = ""


class ReportSections(BaseModel):
    component_information: ReportSection = ReportSection(title="Component Information")
    test_configuration: ReportSection = ReportSection(title="Test Configuration")
    data_quality: ReportSection = ReportSection(title="Data Quality")
    observed_degradation: ReportSection = ReportSection(title="Observed Degradation")
    anomaly_analysis: ReportSection = ReportSection(title="Anomaly Analysis")
    model_results: ReportSection = ReportSection(title="Model Results")
    candidate_failure_mechanisms: ReportSection = ReportSection(title="Candidate Failure Mechanisms")
    supporting_evidence: ReportSection = ReportSection(title="Supporting Evidence")
    contradictory_evidence: ReportSection = ReportSection(title="Contradictory Evidence")
    uncertainty: ReportSection = ReportSection(title="Uncertainty")
    engineering_interpretation: ReportSection = ReportSection(title="Engineering Interpretation")
    recommended_investigation: ReportSection = ReportSection(title="Recommended Investigation")
    limitations: ReportSection = ReportSection(title="Limitations")
    provenance: ReportSection = ReportSection(title="Provenance")
    human_review: ReportSection = ReportSection(title="Human Review")
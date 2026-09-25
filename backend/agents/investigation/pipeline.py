from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List
from uuid import uuid4

from backend.agents.investigation.models.investigation import (
    InvestigationRecord,
    InvestigationReport,
    InvestigationStatus,
    ProvenanceEntry,
)
from backend.agents.investigation.orchestrator import InvestigationGraph
from backend.agents.investigation.persistence import InvestigationPersistence
from backend.agents.investigation.state import INITIAL_STATE
from backend.agents.investigation.data_access import DataAccess
from backend.llm.settings import LLMSettings


def run_investigation(
    module_id: str,
    model_id: str,
    dataset_id: str = "",
    max_evidence: int = 5,
    graph: InvestigationGraph | None = None,
    llm_settings: LLMSettings | None = None,
) -> InvestigationRecord:
    da = DataAccess()
    settings = llm_settings or LLMSettings()
    graph = graph or InvestigationGraph(data_access=da, llm_settings=settings)

    investigation_id = f"inv-{uuid4().hex[:12]}"
    pre_hashes = da.snapshot_m7_m8(model_id)

    initial_state: dict = {
        **INITIAL_STATE,
        "investigation_id": investigation_id,
        "module_id": module_id,
        "model_id": model_id,
        "dataset_id": dataset_id or f"syn-sic-pc-dev-001",
        "provenance": [
            ProvenanceEntry(
                step="initialization",
                source="run_investigation",
                description=f"module_id={module_id}, model_id={model_id}, dataset_id={dataset_id or 'syn-sic-pc-dev-001'}",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        ],
    }

    result_state = graph.run(initial_state)

    record = InvestigationRecord(
        investigation_id=investigation_id,
        module_id=module_id,
        model_id=model_id,
        dataset_id=dataset_id or "syn-sic-pc-dev-001",
        status=InvestigationStatus.COMPLETED if not result_state.get("errors") else InvestigationStatus.PARTIAL,
        module_trajectory=result_state.get("module_trajectory"),
        m7_module_summary=result_state.get("m7_module_summary", {}),
        m8_module_evaluation=result_state.get("m8_module_evaluation", {}),
        m8_timing=result_state.get("m8_timing", {}),
        m8_baseline=result_state.get("m8_baseline", {}),
        deterministic_results=result_state.get("deterministic_results", []),
        evidence_records=result_state.get("evidence_records", []),
        evidence_queries=result_state.get("evidence_queries", []),
        hypothesis=result_state.get("hypothesis"),
        report=result_state.get("report"),
        provenance=result_state.get("provenance", []),
        agent_messages=result_state.get("agent_messages", {}),
        retry_counts=result_state.get("retry_counts", {}),
        errors=result_state.get("errors", {}),
        limitations=result_state.get("limitations", []),
    )

    persistence = InvestigationPersistence()
    persistence.save_investigation(record)
    if record.report:
        persistence.save_report(record.report)
    persistence.save_deterministic_results(investigation_id, record.deterministic_results)
    persistence.save_provenance(investigation_id, record.provenance)

    post_hashes = da.snapshot_m7_m8(model_id)
    _verify_immutable(pre_hashes, post_hashes)

    return record


def _verify_immutable(before: Dict[str, str], after: Dict[str, str]) -> None:
    for path, h in before.items():
        if after.get(path) != h:
            import warnings
            warnings.warn(f"M9 modified M7/M8 artifact: {path}")
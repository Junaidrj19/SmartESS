"""FastAPI routes for M9 investigations.

For M9 MVP, execution is synchronous within the API process.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.agents.investigation import (
    run_investigation,
    InvestigationPersistence,
)
from backend.agents.investigation.data_access import DataAccess, DataAccessError
from backend.llm.factory import LLMNotConfigured

logger = logging.getLogger("smartess.investigations")

router = APIRouter(prefix="/investigations", tags=["investigations"])
persistence = InvestigationPersistence()


class InvestigationRequest(BaseModel):
    module_id: str
    model_id: str = "iforest-v1-syn-sic-pc-dev-001-s20260922"
    dataset_id: str = "syn-sic-pc-dev-001"
    max_evidence: int = 5


@router.post("")
def create_investigation(req: InvestigationRequest):
    try:
        record = run_investigation(
            module_id=req.module_id,
            model_id=req.model_id,
            dataset_id=req.dataset_id,
            max_evidence=req.max_evidence,
        )
        return {
            "investigation_id": record.investigation_id,
            "status": record.status.value if hasattr(record.status, "value") else record.status,
            "module_id": record.module_id,
            "model_id": record.model_id,
        }
    except DataAccessError as e:
        # An unknown module or a missing frozen artifact is not a server fault:
        # the UI needs to distinguish it from a genuine failure (design.md §10.4).
        raise HTTPException(status_code=404, detail=str(e))
    except LLMNotConfigured as e:
        logger.error("investigation refused: LLM is not configured")
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.exception("investigation failed: %s", type(e).__name__)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("")
def list_investigations(module_id: str | None = None, model_id: str | None = None):
    items = persistence.list_investigations()
    if module_id:
        items = [i for i in items if i["module_id"] == module_id]
    if model_id:
        items = [i for i in items if i["model_id"] == model_id]
    return items


@router.get("/{investigation_id}")
def get_investigation(investigation_id: str):
    record = persistence.load(investigation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return record


@router.get("/{investigation_id}/report")
def get_report(investigation_id: str):
    record = persistence.load(investigation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return record.report


# --- M10 sub-resources -------------------------------------------------
# Additive, read-only projections of the stored record. They exist so the UI
# can fetch one part of an investigation without transferring the whole
# record, which embeds the full signal trajectory (design.md §11.3).


def _load_or_404(investigation_id: str):
    record = persistence.load(investigation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return record


@router.get("/{investigation_id}/provenance")
def get_provenance(investigation_id: str):
    record = _load_or_404(investigation_id)
    return {
        "investigation_id": record.investigation_id,
        "provenance": [p.model_dump() for p in record.provenance],
        "retry_counts": record.retry_counts,
        "errors": record.errors,
        "limitations": record.limitations,
        # Hashes of the frozen M7/M8 inputs, recomputed at read time. They are
        # not persisted on the record, so this is current-artifact identity.
        "artifact_hashes_current": DataAccess().snapshot_m7_m8(record.model_id),
        "artifact_hashes_note": (
            "snapshot_m7_m8 is computed at investigation time but not persisted, so "
            "these hashes describe the artifacts as they are now."
        ),
    }


@router.get("/{investigation_id}/deterministic-results")
def get_deterministic_results(investigation_id: str):
    record = _load_or_404(investigation_id)
    return {
        "investigation_id": record.investigation_id,
        "n_results": len(record.deterministic_results),
        "results": [r.model_dump() for r in record.deterministic_results],
    }


@router.get("/{investigation_id}/evidence")
def get_evidence(investigation_id: str):
    record = _load_or_404(investigation_id)
    return {
        "investigation_id": record.investigation_id,
        "evidence_queries": record.evidence_queries,
        "evidence_records": [e.model_dump() for e in record.evidence_records],
        "n_queries": len(record.evidence_queries),
        "n_records": len(record.evidence_records),
    }


@router.get("/{investigation_id}/hypothesis")
def get_hypothesis(investigation_id: str):
    record = _load_or_404(investigation_id)
    return record.hypothesis
"""M10 system routes: readiness, knowledge-base corpus, LLM configuration.

Additive and read-only. The LLM API key is never returned by any route here
(design.md §15.1): only provider, model, endpoint host and a boolean.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException

from backend.api import projections as proj
from backend.llm.settings import LLMSettings, is_production_env

router = APIRouter(tags=["system"])


@router.get("/readiness")
def readiness(model_id: Optional[str] = None):
    """Artifact presence plus LLM configuration state.

    Never includes the API key — only whether one is configured.
    """
    settings = LLMSettings()
    data = proj.readiness(model_id)
    production = is_production_env()
    if settings.configured:
        inference = "real"
        note = (
            "The hypothesis agent calls the configured provider. "
            "Mock inference is not used."
        )
    elif production:
        inference = "not_configured"
        note = (
            "The provider name and credential are not set. Production refuses "
            "investigation requests instead of using mock inference."
        )
    else:
        inference = "mocked"
        note = (
            "When no provider is configured the hypothesis agent uses a mock client "
            "and produces no model-generated reasoning."
        )
    data["llm"] = {
        "provider": settings.provider or None,
        "model": settings.model or None,
        "endpoint_host": settings.endpoint_host or None,
        "configured": settings.configured,
        "inference": inference,
        "prompt_version": settings.prompt_version,
        "timeout": settings.timeout,
        "embedding_model": settings.embedding_model,
        "status": "READY" if settings.configured else "NOT_CONFIGURED",
        "note": note,
    }
    absent = [item["artifact"] for item in data["artifacts"] if item["status"] != "PRESENT"]
    blockers = list(absent)
    if production and not settings.configured:
        blockers.append("llm_not_configured")
    # Health is process liveness (`GET /health`). This status is dependencies.
    data["status"] = "READY" if not blockers else "NOT_READY"
    data["blockers"] = blockers
    return proj.sanitize(data)


@router.get("/corpus")
def corpus():
    try:
        data = proj.corpus()
    except proj.ArtifactMissing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    data["collection"] = proj.chroma_status()
    return proj.sanitize(data)


@router.get("/corpus/documents/{document_id}")
def corpus_document(document_id: str):
    try:
        return proj.sanitize(proj.corpus_document(document_id))
    except proj.ArtifactMissing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

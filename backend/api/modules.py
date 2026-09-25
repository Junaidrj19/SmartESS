"""M10 read-only routes: models, modules, telemetry, anomaly, evaluation.

Additive M10 surface over existing frozen artifacts (design.md §10.2). These
routes read only; they never retrain, re-score or re-evaluate, and they never
compute an engineering value of their own.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from backend.api import projections as proj
from backend.agents.investigation.persistence import InvestigationPersistence

router = APIRouter(tags=["m10"])
_persistence = InvestigationPersistence()


def _resolve_model(model_id: Optional[str]) -> str:
    resolved = model_id or proj.default_model_id()
    if not resolved:
        raise HTTPException(
            status_code=503,
            detail="No trained model is available. Run scripts/train_anomaly_model.py.",
        )
    return resolved


# -------------------------------------------------------------------- models


@router.get("/models")
def list_models():
    return proj.sanitize(proj.list_models())


@router.get("/models/{model_id}")
def get_model(model_id: str):
    try:
        return proj.sanitize(proj.model_record(model_id))
    except proj.ArtifactMissing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ------------------------------------------------------------------- modules


@router.get("/modules")
def list_modules(
    model_id: Optional[str] = None,
    lot_id: Optional[str] = None,
    anomaly_status: Optional[str] = Query(default=None, pattern="^(clean|sporadic|persistent)$"),
    search: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    mid = _resolve_model(model_id)
    try:
        page = proj.list_modules(
            model_id=mid,
            lot_id=lot_id,
            anomaly_status=anomaly_status,
            search=search,
            limit=limit,
            offset=offset,
        )
    except proj.ArtifactMissing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    page["model_id"] = mid
    return proj.sanitize(page)


@router.get("/modules/population")
def module_population(model_id: Optional[str] = None):
    mid = _resolve_model(model_id)
    try:
        counts = proj.module_status_counts(mid)
    except proj.ArtifactMissing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    counts["model_id"] = mid
    return proj.sanitize(counts)


@router.get("/modules/{module_id}")
def get_module(module_id: str, model_id: Optional[str] = None):
    mid = _resolve_model(model_id)
    try:
        summary = proj.module_summary(mid, module_id)
    except proj.ArtifactMissing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    record = proj.model_record(mid)
    split = record.get("split", {}) or {}
    lot = summary.get("lot_id")

    investigations = [
        i for i in _persistence.list_investigations() if i.get("module_id") == module_id
    ]

    return proj.sanitize({
        "model_id": mid,
        "module_summary": summary,
        "module_evaluation": proj.module_evaluation(mid, module_id),
        "timing_analysis": proj.timing_analysis(mid, module_id),
        "baseline_comparison": proj.baseline_comparison(mid, module_id),
        "model": {
            "model_id": record.get("model_id"),
            "algorithm": record.get("algorithm"),
            "detector_version": record.get("detector_version"),
            "feature_version": record.get("feature_version"),
            "module_profile_id": record.get("module_profile_id"),
            "training_timestamp": record.get("training_timestamp"),
            "n_input_features": record.get("n_input_features"),
            "hyperparameters": record.get("hyperparameters", {}),
            "observation_threshold": record.get("threshold"),
        },
        "split_membership": {
            "lot_id": lot,
            "split_type": split.get("type"),
            "train_lots": split.get("train_lots", []),
            "test_lots": split.get("test_lots", []),
            "in_train_lots": lot in (split.get("train_lots") or []),
            "in_test_lots": lot in (split.get("test_lots") or []),
        },
        "data_origin": "synthetic",
        "investigations": investigations,
    })


@router.get("/modules/{module_id}/telemetry")
def get_telemetry(
    module_id: str,
    model_id: Optional[str] = None,
    signals: Optional[str] = Query(default=None, description="Comma-separated signal names"),
    from_cycle: Optional[int] = None,
    to_cycle: Optional[int] = None,
    max_points: Optional[int] = Query(default=None, ge=10, le=20000),
):
    mid = _resolve_model(model_id)
    selected = [s.strip() for s in signals.split(",") if s.strip()] if signals else None
    try:
        return proj.sanitize(proj.module_telemetry(
            module_id=module_id,
            model_id=mid,
            signals=selected,
            from_cycle=from_cycle,
            to_cycle=to_cycle,
            max_points=max_points,
        ))
    except proj.ArtifactMissing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/modules/{module_id}/anomaly")
def get_anomaly(module_id: str, model_id: Optional[str] = None):
    mid = _resolve_model(model_id)
    try:
        summary = proj.module_summary(mid, module_id)
        record = proj.model_record(mid)
    except proj.ArtifactMissing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    module_threshold = None
    try:
        module_threshold = proj.evaluation_summary(mid).get("module_threshold")
    except proj.ArtifactMissing:
        module_threshold = None

    return proj.sanitize({
        "model_id": mid,
        "module_summary": summary,
        "model": {
            "model_id": record.get("model_id"),
            "algorithm": record.get("algorithm"),
            "detector_version": record.get("detector_version"),
            "feature_version": record.get("feature_version"),
            "n_input_features": record.get("n_input_features"),
            "hyperparameters": record.get("hyperparameters", {}),
        },
        "thresholds": {
            "observation_threshold": record.get("threshold"),
            "module_threshold": module_threshold,
            "note": (
                "observation_threshold is the per-observation decision boundary from "
                "model-record.json; module_threshold is the module-level boundary from "
                "evaluation-summary.json. They are different quantities."
            ),
        },
        "score_semantics": {
            "direction": "higher_is_more_anomalous",
            "statistical_baseline_flag_threshold": 3.0,
        },
        "qualification": "Anomaly summary — not a failure diagnosis.",
    })


# ---------------------------------------------------------------- evaluation


@router.get("/evaluation/{model_id}")
def get_evaluation(model_id: str):
    try:
        return proj.sanitize(proj.evaluation_summary(model_id))
    except proj.ArtifactMissing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/healthy-reference/{model_id}")
def get_healthy_reference(model_id: str):
    try:
        return proj.sanitize(proj.healthy_reference(model_id))
    except proj.ArtifactMissing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

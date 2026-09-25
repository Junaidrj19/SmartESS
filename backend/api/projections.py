"""M10 read-only projections over existing frozen artifacts.

This module is **additive M10 code**. It does not modify M1–M9: it only reads the
artifacts those milestones already produced, and it introduces **no numeric
method of its own**. Every value returned here is read verbatim from a parquet
file or a JSON record.

It complements ``backend.agents.investigation.data_access.DataAccess`` (which is
single-module by design) with the list/population reads the M10 frontend needs,
per ``docs/m10/design.md`` §10.2.

Nothing here writes to disk.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pyarrow.compute as pc
import pyarrow.parquet as pq

REPO = Path(__file__).resolve().parents[2]


class ArtifactMissing(FileNotFoundError):
    """A required frozen artifact is absent from this environment.

    Surfaced to the API as 404/503 so the UI can render an explicit readiness
    state instead of an empty panel (design.md §14.1).
    """

    def __init__(self, path: str):
        self.path = path
        super().__init__(f"Artifact not found: {path}")


# --------------------------------------------------------------------- paths


def _abs(rel: str) -> Path:
    return REPO / rel


def _require(rel: str) -> Path:
    p = _abs(rel)
    if not p.exists():
        raise ArtifactMissing(rel)
    return p


def exists(rel: str) -> bool:
    return _abs(rel).exists()


# ---------------------------------------------------------------- serialisation


def sanitize(value: Any) -> Any:
    """Make a value JSON-compliant without changing its meaning.

    Some frozen artifacts legitimately contain ``NaN`` — for example
    ``evaluation-summary.json`` where a statistic is undefined for an empty
    stratum, or ``first_anomalous_cycle`` for a module with no flagged
    observation. JSON has no ``NaN``, and Starlette refuses to emit it.

    ``NaN`` and infinities therefore become ``null``, which is how the frontend
    already renders an absent value (`not recorded`). Nothing is substituted,
    rounded or invented: a missing number stays missing.
    """
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return value
    if isinstance(value, dict):
        return {k: sanitize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    return value


def scores_dir(model_id: str) -> str:
    return f"ml/datasets/scores/{model_id}"


def evaluation_dir(model_id: str) -> str:
    return f"ml/datasets/evaluation/{model_id}"


def model_dir(model_id: str) -> str:
    return f"ml/models/{model_id}"


# -------------------------------------------------------------------- models


def list_models() -> List[Dict[str, Any]]:
    """Every model that has a ``model-record.json``."""
    root = _abs("ml/models")
    if not root.exists():
        return []
    out: List[Dict[str, Any]] = []
    for d in sorted(root.iterdir()):
        record = d / "model-record.json"
        if not record.is_file():
            continue
        data = json.loads(record.read_text())
        out.append(
            {
                "model_id": data.get("model_id", d.name),
                "status": data.get("status"),
                "algorithm": data.get("algorithm"),
                "detector_version": data.get("detector_version"),
                "feature_version": data.get("feature_version"),
                "source_dataset_id": data.get("source_dataset_id"),
                "module_profile_id": data.get("module_profile_id"),
                "training_timestamp": data.get("training_timestamp"),
                "n_input_features": data.get("n_input_features"),
                "hyperparameters": data.get("hyperparameters", {}),
                "split": data.get("split", {}),
                # Observation-level decision threshold. Distinct from the
                # module-level threshold in evaluation-summary.json.
                "observation_threshold": data.get("threshold"),
            }
        )
    return out


def default_model_id() -> Optional[str]:
    models = list_models()
    return models[0]["model_id"] if models else None


def model_record(model_id: str) -> Dict[str, Any]:
    path = _require(f"{model_dir(model_id)}/model-record.json")
    return json.loads(path.read_text())


# ------------------------------------------------------------------- modules


def _table(rel: str, columns: Optional[List[str]] = None, module_id: Optional[str] = None):
    path = _require(rel)
    filters = [("module_id", "==", module_id)] if module_id else None
    return pq.read_table(path, columns=columns, filters=filters)


def _rows(table) -> List[Dict[str, Any]]:
    return table.to_pylist()


def list_modules(
    model_id: str,
    lot_id: Optional[str] = None,
    anomaly_status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Dict[str, Any]:
    """Paginated projection of ``module-summary.parquet``.

    Filtering and pagination only. No aggregate is recomputed: the per-module
    values are exactly the M7 columns.
    """
    table = _table(f"{scores_dir(model_id)}/module-summary.parquet")

    if lot_id:
        table = table.filter(pc.equal(table.column("lot_id"), lot_id))
    if anomaly_status:
        table = table.filter(pc.equal(table.column("module_anomaly_status"), anomaly_status))
    if search:
        table = table.filter(pc.match_substring(table.column("module_id"), search))

    total = table.num_rows
    window = table.slice(offset, limit)

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "returned": window.num_rows,
        "items": _rows(window),
    }


def module_status_counts(model_id: str) -> Dict[str, Any]:
    """Population counts by lot and by ``module_anomaly_status``.

    These are counts of rows, not derived engineering statistics.
    """
    table = _table(
        f"{scores_dir(model_id)}/module-summary.parquet",
        columns=["module_id", "lot_id", "module_anomaly_status"],
    )
    rows = _rows(table)

    by_status: Dict[str, int] = {}
    by_lot: Dict[str, int] = {}
    by_lot_status: Dict[str, Dict[str, int]] = {}
    for r in rows:
        status = str(r.get("module_anomaly_status"))
        lot = str(r.get("lot_id"))
        by_status[status] = by_status.get(status, 0) + 1
        by_lot[lot] = by_lot.get(lot, 0) + 1
        by_lot_status.setdefault(lot, {})
        by_lot_status[lot][status] = by_lot_status[lot].get(status, 0) + 1

    return {
        "n_modules": len(rows),
        "by_anomaly_status": by_status,
        "by_lot": by_lot,
        "by_lot_and_status": by_lot_status,
        "note": "module_anomaly_status is a descriptive anomaly summary, not a failure diagnosis.",
    }


def module_summary(model_id: str, module_id: str) -> Dict[str, Any]:
    rows = _rows(_table(f"{scores_dir(model_id)}/module-summary.parquet", module_id=module_id))
    if not rows:
        raise ArtifactMissing(f"module_id {module_id} not in module-summary for {model_id}")
    return rows[0]


def module_evaluation(model_id: str, module_id: str) -> Dict[str, Any]:
    rows = _rows(_table(f"{evaluation_dir(model_id)}/module-evaluation.parquet", module_id=module_id))
    return rows[0] if rows else {}


def timing_analysis(model_id: str, module_id: str) -> Dict[str, Any]:
    rows = _rows(_table(f"{evaluation_dir(model_id)}/timing-analysis.parquet", module_id=module_id))
    if not rows:
        # Preserve the exact wording M9 uses for this case.
        return {"note": "module not in timing analysis (healthy or undetected)"}
    return rows[0]


def baseline_comparison(model_id: str, module_id: str) -> Dict[str, Any]:
    rows = _rows(_table(f"{evaluation_dir(model_id)}/baseline-comparison.parquet", module_id=module_id))
    return rows[0] if rows else {}


# ------------------------------------------------------------------ telemetry

BASELINE_SIGNALS = [
    "RDS_on",
    "VTH",
    "IGSS",
    "IDSS",
    "VDS_on",
    "electrical_power",
    "Tj",
    "Tc",
]


def _jsonable(value: Any) -> Any:
    """JSON cannot carry NaN: missing samples become null (design.md §7.1)."""
    if value is None:
        return None
    if isinstance(value, float) and value != value:
        return None
    return value


def module_telemetry(
    module_id: str,
    model_id: str,
    signals: Optional[List[str]] = None,
    from_cycle: Optional[int] = None,
    to_cycle: Optional[int] = None,
    max_points: Optional[int] = None,
) -> Dict[str, Any]:
    """Signal series plus per-observation detector output for one module.

    The two artifacts are joined on ``cycle_number``. Downsampling, when applied,
    **retains every flagged observation** so a reduced view can never hide an
    anomaly (design.md §19.2).
    """
    wanted = [s for s in (signals or BASELINE_SIGNALS) if s in BASELINE_SIGNALS]

    feat_rel = "ml/datasets/features/v1/observation-features.parquet"
    feat = _table(feat_rel, columns=["cycle_number", *wanted], module_id=module_id)
    if feat.num_rows == 0:
        raise ArtifactMissing(f"module_id {module_id} not in observation-features")

    score_rel = f"{scores_dir(model_id)}/observation-scores.parquet"
    scores = _table(
        score_rel,
        columns=[
            "cycle_number",
            "anomaly_score",
            "is_anomaly",
            "statistical_baseline_score",
            "statistical_baseline_flag",
        ],
        module_id=module_id,
    )

    feat_rows = _rows(feat)
    score_by_cycle = {r["cycle_number"]: r for r in _rows(scores)}

    merged: List[Dict[str, Any]] = []
    for fr in feat_rows:
        cycle = fr["cycle_number"]
        if from_cycle is not None and cycle < from_cycle:
            continue
        if to_cycle is not None and cycle > to_cycle:
            continue
        sr = score_by_cycle.get(cycle, {})
        point: Dict[str, Any] = {
            "cycle_number": cycle,
            "anomaly_score": _jsonable(sr.get("anomaly_score")),
            "is_anomaly": bool(sr.get("is_anomaly")) if sr.get("is_anomaly") is not None else None,
            "statistical_baseline_score": _jsonable(sr.get("statistical_baseline_score")),
            "statistical_baseline_flag": (
                bool(sr.get("statistical_baseline_flag"))
                if sr.get("statistical_baseline_flag") is not None
                else None
            ),
        }
        for s in wanted:
            point[s] = _jsonable(fr.get(s))
        merged.append(point)

    source_points = len(merged)
    downsampled = False
    method = None
    if max_points is not None and 0 < max_points < source_points:
        downsampled = True
        method = "uniform_stride_preserving_flagged_observations"
        flagged_idx = {
            i
            for i, p in enumerate(merged)
            if p["is_anomaly"] or p["statistical_baseline_flag"]
        }
        stride = max(1, source_points // max_points)
        keep = {i for i in range(0, source_points, stride)} | flagged_idx
        keep.add(source_points - 1)
        merged = [p for i, p in enumerate(merged) if i in keep]

    return {
        "module_id": module_id,
        "model_id": model_id,
        "signals": wanted,
        "source_points": source_points,
        "returned_points": len(merged),
        "downsampled": downsampled,
        "downsample_method": method,
        "points": merged,
        "score_semantics": {
            "anomaly_score": "inverted isolation forest decision function; higher = more anomalous",
            "statistical_baseline_flag_threshold": 3.0,
        },
        "units_note": (
            "No engineering unit is carried in the M6/M7 artifacts. Units stated in "
            "documentation only: RDS_on in mOhm, Tj/Tc in degrees Celsius."
        ),
    }


# ----------------------------------------------------------------- evaluation


def evaluation_summary(model_id: str) -> Dict[str, Any]:
    path = _require(f"{evaluation_dir(model_id)}/evaluation-summary.json")
    return json.loads(path.read_text())


def healthy_reference(model_id: str) -> Dict[str, Any]:
    path = _abs("ml/datasets/investigations/reference/healthy-reference.json")
    if not path.exists():
        raise ArtifactMissing("ml/datasets/investigations/reference/healthy-reference.json")
    data = json.loads(path.read_text())
    if data.get("model_id") and data["model_id"] != model_id:
        data["_model_mismatch"] = (
            f"reference was declared for {data['model_id']}, requested {model_id}"
        )
    return data


# ------------------------------------------------------------------ knowledge


def corpus() -> Dict[str, Any]:
    path = _require("knowledge_base/metadata/corpus.json")
    data = json.loads(path.read_text())
    documents = data.get("documents", [])

    by_status: Dict[str, int] = {}
    by_type: Dict[str, int] = {}
    for d in documents:
        s = str(d.get("verification_status"))
        t = str(d.get("source_type"))
        by_status[s] = by_status.get(s, 0) + 1
        by_type[t] = by_type.get(t, 0) + 1

    return {
        "corpus_version": data.get("corpus_version"),
        "generated_at": data.get("generated_at"),
        "note": data.get("note"),
        "n_documents": len(documents),
        "counts_by_verification_status": by_status,
        "counts_by_source_type": by_type,
        "documents": documents,
        "production_note": "Only VERIFIED documents enter the production collection.",
    }


def corpus_document(document_id: str) -> Dict[str, Any]:
    for d in corpus()["documents"]:
        if d.get("document_id") == document_id:
            return d
    raise ArtifactMissing(f"document_id {document_id} not in corpus manifest")


def chroma_status(chroma_path: str = "knowledge_base/chroma") -> Dict[str, Any]:
    """Collection reachability and chunk count, without importing the retriever
    at module scope (chromadb is slow to import and optional at runtime)."""
    p = _abs(chroma_path)
    if not p.exists():
        return {"reachable": False, "chunk_count": None, "path": chroma_path}
    try:
        from backend.knowledge.retrieval import ChromaRetriever

        retriever = ChromaRetriever(str(p))
        return {
            "reachable": True,
            "collection": "evidence",
            "chunk_count": retriever.count(),
            "path": chroma_path,
        }
    except Exception as exc:  # pragma: no cover - environment dependent
        return {
            "reachable": False,
            "chunk_count": None,
            "path": chroma_path,
            "detail": f"{type(exc).__name__}: {exc}",
        }


# ------------------------------------------------------------------ readiness

_ARTIFACTS = [
    ("features", "ml/datasets/features/v1/observation-features.parquet", "scripts/build_features.py"),
    ("module_features", "ml/datasets/features/v1/module-features.parquet", "scripts/build_features.py"),
]


def readiness(model_id: Optional[str] = None) -> Dict[str, Any]:
    """Which frozen artifacts exist in this environment, and what produces them."""
    mid = model_id or default_model_id()
    items: List[Dict[str, Any]] = []

    def add(name: str, rel: str, cli: str) -> None:
        items.append(
            {
                "artifact": name,
                "status": "PRESENT" if exists(rel) else "ABSENT",
                "path": rel,
                "produced_by": cli,
            }
        )

    for name, rel, cli in _ARTIFACTS:
        add(name, rel, cli)

    if mid:
        add("model", f"{model_dir(mid)}/model-record.json", "scripts/train_anomaly_model.py")
        add("scores", f"{scores_dir(mid)}/observation-scores.parquet", "scripts/train_anomaly_model.py")
        add("module_summary", f"{scores_dir(mid)}/module-summary.parquet", "scripts/train_anomaly_model.py")
        add("evaluation", f"{evaluation_dir(mid)}/evaluation-summary.json", "scripts/evaluate_anomaly.py")
        add("module_evaluation", f"{evaluation_dir(mid)}/module-evaluation.parquet", "scripts/evaluate_anomaly.py")
        add("timing_analysis", f"{evaluation_dir(mid)}/timing-analysis.parquet", "scripts/evaluate_anomaly.py")
        add("baseline_comparison", f"{evaluation_dir(mid)}/baseline-comparison.parquet", "scripts/evaluate_anomaly.py")
    add(
        "healthy_reference",
        "ml/datasets/investigations/reference/healthy-reference.json",
        "scripts/build_healthy_reference.py",
    )
    add("corpus_manifest", "knowledge_base/metadata/corpus.json", "scripts/ingest_knowledge.py")

    kb = chroma_status()
    items.append(
        {
            "artifact": "knowledge_base",
            "status": "PRESENT" if kb.get("chunk_count") else "ABSENT",
            "path": kb.get("path"),
            "produced_by": "scripts/ingest_knowledge.py",
            "detail": (
                f"collection evidence · {kb.get('chunk_count')} chunks"
                if kb.get("chunk_count")
                else kb.get("detail") or "collection empty or unreachable"
            ),
        }
    )

    return {"model_id": mid, "artifacts": items}

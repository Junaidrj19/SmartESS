"""Model registry records. JSON on disk; no silent reuse across feature versions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import joblib

from .config import DETECTOR_VERSION


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_registry(
    model_dir: Path,
    *,
    record: Dict[str, Any],
    detector,
    imputer,
) -> Dict[str, str]:
    model_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = model_dir / "detector.joblib"
    record_path = model_dir / "model-record.json"
    joblib.dump({"detector": detector, "imputer": imputer}, artifact_path)
    payload = dict(record)
    payload["artifact_location"] = str(artifact_path)
    payload["detector_version"] = DETECTOR_VERSION
    record_path.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    return {"model_record": str(record_path), "artifact": str(artifact_path)}


def load_registry(model_dir: Path) -> tuple[dict, object, object]:
    record = json.loads((model_dir / "model-record.json").read_text(encoding="utf-8"))
    blob = joblib.load(model_dir / "detector.joblib")
    return record, blob["detector"], blob["imputer"]

"""Dataset discovery and loading. Missing artifacts are recorded, never skipped."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ml.validators.synthetic.constants import REQUIRED_ARTIFACTS


@dataclass
class LoadedDataset:
    dataset_dir: Path
    missing_artifacts: list[str] = field(default_factory=list)
    unreadable: dict[str, str] = field(default_factory=dict)
    dataset_meta: Optional[dict[str, Any]] = None
    generation_config: Optional[dict[str, Any]] = None
    assumptions: Optional[dict[str, Any]] = None
    provenance: Optional[dict[str, Any]] = None
    telemetry: Optional[pd.DataFrame] = None
    ground_truth: Optional[pd.DataFrame] = None

    @property
    def dataset_id_guess(self) -> str:
        if isinstance(self.dataset_meta, dict) and self.dataset_meta.get("dataset_id"):
            return str(self.dataset_meta["dataset_id"])
        return self.dataset_dir.name


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("JSON root must be an object")
    return payload


def discover_and_load(dataset_dir: Path) -> LoadedDataset:
    root = Path(dataset_dir).expanduser().resolve()
    loaded = LoadedDataset(dataset_dir=root)
    if not root.is_dir():
        loaded.missing_artifacts = list(REQUIRED_ARTIFACTS)
        loaded.unreadable["dataset_dir"] = f"not a directory: {root}"
        return loaded

    for relative in REQUIRED_ARTIFACTS:
        path = root / relative
        if not path.is_file():
            loaded.missing_artifacts.append(relative)
            continue
        try:
            if relative.endswith(".json"):
                payload = _read_json(path)
                if relative == "metadata/dataset.json":
                    loaded.dataset_meta = payload
                elif relative == "metadata/generation-config.json":
                    loaded.generation_config = payload
                elif relative == "metadata/assumptions.json":
                    loaded.assumptions = payload
                elif relative == "provenance/provenance.json":
                    loaded.provenance = payload
            elif relative.endswith(".parquet"):
                frame = pd.read_parquet(path)
                if relative.endswith("telemetry.parquet"):
                    loaded.telemetry = frame
                else:
                    loaded.ground_truth = frame
        except Exception as exc:  # noqa: BLE001 — surface any parse/IO failure
            loaded.unreadable[relative] = f"{type(exc).__name__}: {exc}"
    return loaded

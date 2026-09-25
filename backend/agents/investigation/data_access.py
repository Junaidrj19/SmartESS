from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pyarrow.parquet as pq

from backend.agents.investigation.models.investigation import ModuleTrajectory

REPO = Path(__file__).resolve().parents[3]


class DataAccessError(RuntimeError):
    pass


class DataAccess:
    def __init__(self, repo_root: str | Path = REPO):
        self.root = Path(repo_root)

    def _path(self, *parts: str) -> Path:
        p = self.root.joinpath(*parts)
        if not p.exists():
            raise DataAccessError(f"Artifact not found: {p}")
        return p

    def _hash_file(self, path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]

    def observation_scores(self, model_id: str, module_id: str) -> Dict[str, Any]:
        path = self._path("ml/datasets/scores", model_id, "observation-scores.parquet")
        tbl = pq.read_table(
            path,
            columns=["module_id", "cycle_number", "anomaly_score", "is_anomaly"],
            filters=[("module_id", "==", module_id)],
        )
        scores = [float(x) for x in tbl.column("anomaly_score").to_pylist()] if len(tbl) else []
        cycles = [int(x) for x in tbl.column("cycle_number").to_pylist()] if len(tbl) else []
        flagged = tbl.column("is_anomaly").to_pylist() if len(tbl) else []
        return {
            "n_observations": len(tbl),
            "n_flagged": int(sum(1 for f in flagged if f)),
            "mean_score": float(sum(scores) / len(scores)) if scores else 0.0,
            "max_score": float(max(scores)) if scores else 0.0,
            "min_score": float(min(scores)) if scores else 0.0,
            "cycle_numbers": cycles,
            "scores": scores,
        }

    def module_summary(self, model_id: str, module_id: str) -> Dict[str, Any]:
        path = self._path("ml/datasets/scores", model_id, "module-summary.parquet")
        tbl = pq.read_table(
            path,
            filters=[("module_id", "==", module_id)],
        )
        if len(tbl) == 0:
            raise DataAccessError(f"module_id {module_id} not in module-summary")
        row = tbl.to_pydict()
        return {k: (v[0] if v else None) for k, v in row.items()}

    def model_record(self, model_id: str) -> Dict[str, Any]:
        path = self._path("ml/models", model_id, "model-record.json")
        data = json.loads(path.read_text())
        data["_source_path"] = str(path)
        data["_hash"] = self._hash_file(path)
        return data

    def module_evaluation(self, model_id: str, module_id: str) -> Dict[str, Any]:
        path = self._path("ml/datasets/evaluation", model_id, "module-evaluation.parquet")
        tbl = pq.read_table(
            path,
            filters=[("module_id", "==", module_id)],
        )
        if len(tbl) == 0:
            raise DataAccessError(f"module_id {module_id} not in module-evaluation")
        row = tbl.to_pydict()
        return {k: (v[0] if v else None) for k, v in row.items()}

    def timing_analysis(self, model_id: str, module_id: str) -> Dict[str, Any]:
        path = self._path("ml/datasets/evaluation", model_id, "timing-analysis.parquet")
        tbl = pq.read_table(
            path,
            filters=[("module_id", "==", module_id)],
        )
        if len(tbl) == 0:
            return {"note": "module not in timing analysis (healthy or undetected)"}
        row = tbl.to_pydict()
        return {k: (v[0] if v else None) for k, v in row.items()}

    def baseline_comparison(self, model_id: str, module_id: str) -> Dict[str, Any]:
        path = self._path("ml/datasets/evaluation", model_id, "baseline-comparison.parquet")
        tbl = pq.read_table(
            path,
            filters=[("module_id", "==", module_id)],
        )
        if len(tbl) == 0:
            return {}
        row = tbl.to_pydict()
        return {k: (v[0] if v else None) for k, v in row.items()}

    def observation_features(self, module_id: str, signals: Optional[List[str]] = None) -> Dict[str, Any]:
        path = self._path("ml/datasets/features/v1/observation-features.parquet")
        core = ["module_id", "cycle_number"]
        if signals:
            cols = core + [s for s in signals if s in pq.ParquetFile(path).schema_arrow.names]
        else:
            cols = None
        tbl = pq.read_table(path, columns=cols, filters=[("module_id", "==", module_id)])
        if len(tbl) == 0:
            raise DataAccessError(f"module_id {module_id} not in observation-features")
        d = tbl.to_pydict()
        d.pop("module_id", None)
        return d

    def module_features(self, module_id: str) -> Dict[str, Any]:
        path = self._path("ml/datasets/features/v1/module-features.parquet")
        tbl = pq.read_table(path, filters=[("module_id", "==", module_id)])
        if len(tbl) == 0:
            raise DataAccessError(f"module_id {module_id} not in module-features")
        row = tbl.to_pydict()
        return {k: (v[0] if v else None) for k, v in row.items()}

    def load_module_trajectory(self, model_id: str, module_id: str) -> ModuleTrajectory:
        obs = self.observation_scores(model_id, module_id)
        feats = self.observation_features(module_id, signals=["RDS_on", "VTH", "IGSS", "IDSS", "VDS_on", "electrical_power", "Tj", "Tc"])
        return ModuleTrajectory(
            module_id=module_id,
            n_observations=obs["n_observations"],
            n_cycles=len(obs["cycle_numbers"]),
            signals={k: [float(x) if x is not None else float("nan") for x in v] for k, v in feats.items() if k != "cycle_number"},
            cycle_numbers=obs["cycle_numbers"],
            min_score=obs.get("min_score", 0.0),
            max_score=obs.get("max_score", 0.0),
            mean_score=obs.get("mean_score", 0.0),
        )

    def snapshot_m7_m8(self, model_id: str) -> Dict[str, str]:
        hashes = {}
        for path in [
            f"ml/datasets/scores/{model_id}/observation-scores.parquet",
            f"ml/datasets/scores/{model_id}/module-summary.parquet",
            f"ml/models/{model_id}/model-record.json",
            f"ml/datasets/evaluation/{model_id}/module-evaluation.parquet",
            f"ml/datasets/evaluation/{model_id}/timing-analysis.parquet",
            f"ml/datasets/evaluation/{model_id}/baseline-comparison.parquet",
        ]:
            p = self.root / path
            if p.exists():
                hashes[path] = self._hash_file(p)
        return hashes
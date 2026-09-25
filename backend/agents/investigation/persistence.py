from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from backend.agents.investigation.models.investigation import (
    InvestigationRecord,
    InvestigationReport,
)

REPO = Path(__file__).resolve().parents[3]

INVESTIGATIONS_ROOT = REPO / "ml/datasets/investigations"


class InvestigationPersistence:
    def __init__(self, root: str | Path = ""):
        self.root = Path(root) if root else INVESTIGATIONS_ROOT

    def save_investigation(self, record: InvestigationRecord) -> Path:
        out = self.root / record.investigation_id
        out.mkdir(parents=True, exist_ok=True)
        (out / "investigation-record.json").write_text(
            record.model_dump_json(indent=2, exclude_none=True) + "\n",
            encoding="utf-8",
        )
        return out

    def save_report(self, report: InvestigationReport) -> Path:
        out = self.root / report.investigation_id
        out.mkdir(parents=True, exist_ok=True)
        (out / "investigation-report.json").write_text(
            report.model_dump_json(indent=2, exclude_none=True) + "\n",
            encoding="utf-8",
        )
        return out

    def save_deterministic_results(self, investigation_id: str, results: list) -> Path:
        out = self.root / investigation_id
        out.mkdir(parents=True, exist_ok=True)
        (out / "deterministic-results.json").write_text(
            json.dumps([r.model_dump() for r in results], indent=2, default=str) + "\n",
            encoding="utf-8",
        )
        return out

    def save_provenance(self, investigation_id: str, provenance: list) -> Path:
        out = self.root / investigation_id
        out.mkdir(parents=True, exist_ok=True)
        (out / "provenance.json").write_text(
            json.dumps([p.model_dump() if hasattr(p, "model_dump") else p for p in provenance], indent=2, default=str) + "\n",
        )
        return out

    def load(self, investigation_id: str) -> InvestigationRecord | None:
        p = self.root / investigation_id / "investigation-record.json"
        if not p.exists():
            return None
        return InvestigationRecord.model_validate_json(p.read_text())

    def list_investigations(self) -> list[Dict[str, Any]]:
        if not self.root.exists():
            return []
        results = []
        for d in sorted(self.root.iterdir()):
            if d.is_dir():
                rec = self.load(d.name)
                if rec:
                    results.append({
                        "investigation_id": rec.investigation_id,
                        "module_id": rec.module_id,
                        "model_id": rec.model_id,
                        "status": rec.status.value if hasattr(rec.status, "value") else str(rec.status),
                        "created_at": rec.created_at,
                    })
        return results
"""Machine-readable and human-readable M5 validation reports."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np

from ml.validators.synthetic.models import CheckStatus, ValidationReport


def _json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.ndarray):
        return [_json_default(item) for item in value.tolist()]
    if hasattr(value, "value"):
        return value.value
    return str(value)


def report_to_markdown(report: ValidationReport) -> str:
    s = report.summary
    lines = [
        "# SmartESS dataset validation report (M5)",
        "",
        f"- Dataset ID: `{report.dataset_id}`",
        f"- Overall status: **{report.overall_status.value}**",
        f"- Validator version: `{report.validator_version}`",
        f"- Validation timestamp: `{report.validation_timestamp}`",
        f"- Runtime: `{s.elapsed_s:.3f}` s",
        f"- Scenario: `{s.scenario}`",
        f"- data_origin: `{s.data_origin}`",
        "",
        "## Check summary",
        "",
        f"- PASS: {s.n_pass}",
        f"- WARNING: {s.n_warning}",
        f"- BLOCKED: {s.n_blocked}",
        f"- Total checks: {s.n_checks}",
        "",
        "## Dataset size",
        "",
        f"- Modules: {s.n_modules}",
        f"- Lots: {s.n_lots}",
        f"- Telemetry rows: {s.n_telemetry_rows}",
        f"- Ground-truth rows: {s.n_ground_truth_rows}",
        f"- Mechanism composition: `{s.mechanism_counts}`",
        f"- Missingness rates: `{s.missingness}`",
        f"- Duplicate counts: `{s.duplicate_counts}`",
        "",
        "## Checks",
        "",
    ]
    for status in (CheckStatus.BLOCKED, CheckStatus.WARNING, CheckStatus.PASS):
        subset = report.checks_by_status(status)
        lines.append(f"### {status.value} ({len(subset)})")
        lines.append("")
        if not subset:
            lines.append("_None._")
            lines.append("")
            continue
        for check in subset:
            lines.append(f"- `{check.check_id}` ({check.category.value}, severity={check.severity.value}): {check.message}")
        lines.append("")
    lines.extend(
        [
            "## Key metrics",
            "",
            f"```json",
            __import__("json").dumps(s.key_metrics, indent=2, default=str),
            "```",
            "",
            "## Limitations",
            "",
        ]
    )
    for item in report.limitations:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_reports(dataset_dir: Path, report: ValidationReport) -> tuple[Path, Path]:
    out_dir = dataset_dir / "validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "validation-report.json"
    md_path = out_dir / "validation-report.md"
    payload = report.model_dump(mode="python")
    json_path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n", encoding="utf-8")
    md_path.write_text(report_to_markdown(report), encoding="utf-8")
    return json_path, md_path

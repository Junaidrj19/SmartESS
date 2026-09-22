"""CLI for the M5 synthetic dataset validation engine."""

from __future__ import annotations

import argparse
from pathlib import Path

from ml.validators.synthetic.engine import validate_dataset
from ml.validators.synthetic.models import CheckStatus

EXIT_BY_STATUS = {
    CheckStatus.PASS: 0,
    CheckStatus.WARNING: 1,
    CheckStatus.BLOCKED: 2,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Independently validate a SmartESS synthetic dataset. "
            "Does not modify source artifacts. Passing does not prove experimental validity."
        )
    )
    parser.add_argument("dataset_path", type=Path, help="Dataset directory (e.g. ml/datasets/synthetic/syn-sic-pc-dev-001)")
    parser.add_argument("--no-write", action="store_true", help="Do not write validation/ reports")
    return parser


def format_report(report) -> str:
    lines = [
        f"Dataset: {report.dataset_id}",
        f"Status: {report.overall_status.value}",
        "",
        "Checks:",
    ]
    for check in report.checks:
        lines.append(f"{check.status.value} {check.check_id} — {check.message}")
    summary = report.summary
    lines.extend(
        [
            "",
            "Summary:",
            f"PASS={summary.n_pass} WARNING={summary.n_warning} BLOCKED={summary.n_blocked} "
            f"runtime_s={summary.elapsed_s:.3f} modules={summary.n_modules} "
            f"telemetry_rows={summary.n_telemetry_rows} scenario={summary.scenario}",
            "",
            report.limitations[0],
        ]
    )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = validate_dataset(args.dataset_path, write_output=not args.no_write)
    print(format_report(report), end="")
    return EXIT_BY_STATUS[report.overall_status]


if __name__ == "__main__":
    raise SystemExit(main())

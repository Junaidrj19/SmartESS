#!/usr/bin/env python3
"""M9 CLI — run an agentic reliability investigation.

Usage:
    python3 scripts/investigate.py --module-id syn-mod-0042 --model-id iforest-v1-syn-sic-pc-dev-001-s20260922

The real LLM provider is used whenever credentials are configured (see
``backend/llm/settings.py``). Only non-sensitive LLM metadata is printed: the
provider, the model, the endpoint host and whether inference was real or mocked.
The API key is never printed, logged or stored.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.agents.investigation import run_investigation
from backend.llm.factory import LLMNotConfigured
from backend.llm.settings import LLMSettings, is_production_env


def _describe_llm(settings: LLMSettings) -> None:
    if settings.configured:
        print(f"LLM provider: {settings.provider}")
        print(f"LLM model: {settings.model}")
        print(f"LLM endpoint host: {settings.endpoint_host}")
        print("LLM inference: real (configured provider)")
    elif is_production_env():
        print("LLM provider: not configured")
        print("LLM inference: NOT_CONFIGURED — production will not run a mock investigation")
    else:
        print("LLM provider: mock (no credentials configured)")
        print("LLM inference: mocked — no model-generated hypothesis")


def main() -> None:
    parser = argparse.ArgumentParser(description="M9 Multi-Agent Reliability Investigation")
    parser.add_argument("--module-id", required=True, help="Module ID to investigate")
    parser.add_argument("--model-id", default="iforest-v1-syn-sic-pc-dev-001-s20260922", help="M7 model ID")
    parser.add_argument("--dataset-id", default="syn-sic-pc-dev-001", help="Dataset ID")
    parser.add_argument("--max-evidence", type=int, default=5, help="Max evidence records")
    parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation")
    args = parser.parse_args()

    settings = LLMSettings()
    _describe_llm(settings)

    try:
        record = run_investigation(
            module_id=args.module_id,
            model_id=args.model_id,
            dataset_id=args.dataset_id,
            max_evidence=args.max_evidence,
            llm_settings=settings,
        )
    except LLMNotConfigured as e:
        print(f"Error: NOT_CONFIGURED: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)

    out = Path(f"ml/datasets/investigations/{record.investigation_id}")

    print("\n=== Execution trace (LangGraph node order) ===")
    print(" → ".join(p.step for p in record.provenance) if record.provenance else "(no provenance)")

    print("\n=== Investigation ===")
    print(f"Investigation ID: {record.investigation_id}")
    print(f"Module: {record.module_id}   Model: {record.model_id}")
    print(f"Status: {record.status.value if hasattr(record.status, 'value') else record.status}")
    print(f"Deterministic results: {len(record.deterministic_results)}")
    if record.deterministic_results:
        tools = sorted({r.tool_name for r in record.deterministic_results})
        print(f"Deterministic tools used: {', '.join(tools)}")

    print("\n=== Evidence ===")
    print(f"Evidence queries: {len(record.evidence_queries)}")
    for q in record.evidence_queries:
        print(f"  - {q}")
    print(f"Evidence records: {len(record.evidence_records)}")
    for e in record.evidence_records:
        print(f"  - {e.evidence_id} | {e.document_id} | {e.source_type} | pages {e.page_start}-{e.page_end}")

    print("\n=== Hypotheses ===")
    if record.hypothesis and record.hypothesis.candidates:
        for c in record.hypothesis.candidates:
            print(f"  - {c.mechanism.value} [{c.status.value}] confidence={c.confidence:.2f}")
            print(f"      evidence: {c.supporting_evidence_ids}")
            if c.contradictory_evidence_ids:
                print(f"      contradictory: {c.contradictory_evidence_ids}")
            print(f"      reasoning: {c.reasoning}")
    else:
        print("  (no candidates)")

    print("\n=== Validation gates ===")
    print(f"Hypothesis validation: {record.errors.get('hypothesis_validation', 'PASSED')}")
    print(f"Report validation: {record.errors.get('report_validation', 'PASSED')}")

    print(f"\nOutput: {out}")
    if record.errors:
        print(f"Errors: {record.errors}")
    if record.limitations:
        print(f"Limitations: {record.limitations}")


if __name__ == "__main__":
    main()

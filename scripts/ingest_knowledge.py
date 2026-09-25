#!/usr/bin/env python3
"""Validate and ingest curated knowledge-base documents.

MODES
    (default)      Ingest local documents into the ChromaDB knowledge base.
    --ingest       Same as the default mode, stated explicitly.
    --validate     Validate the corpus manifest and its local PDFs.
    --stats        Report corpus statistics.
    --coverage     Report EXPLICIT/PARTIAL/NONE coverage across axes.

Only local files are consumed. This tool never downloads, crawls, or scrapes.

EXAMPLES
    python3 scripts/ingest_knowledge.py --validate
    python3 scripts/ingest_knowledge.py --ingest
    python3 scripts/ingest_knowledge.py --stats --json
    python3 scripts/ingest_knowledge.py --coverage
    python3 scripts/ingest_knowledge.py --corpus knowledge_base/metadata/corpus.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from backend.knowledge.corpus import (  # noqa: E402
    DEFAULT_CORPUS_PATH,
    corpus_statistics,
    coverage_report,
    load_corpus,
    validate_corpus,
)
from backend.knowledge.ingestion import (  # noqa: E402
    DEFAULT_DOCUMENTS_DIR,
    build_embedder,
    discover_corpus_documents,
    discover_documents,
    ingest_documents,
)
from backend.knowledge.retrieval import ChromaRetriever  # noqa: E402
from backend.llm.settings import LLMSettings  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate/ingest the knowledge base")
    parser.add_argument("--validate", action="store_true", help="Validate the corpus manifest and local PDFs")
    parser.add_argument("--ingest", action="store_true", help="Ingest local documents (explicit default mode)")
    parser.add_argument("--stats", action="store_true", help="Report corpus statistics")
    parser.add_argument("--coverage", action="store_true", help="Report coverage across mechanisms/observables/conditions")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output")
    parser.add_argument("--corpus", default="", help="Path to corpus.json manifest")
    parser.add_argument("--kb-path", default="", help="Extra document directory for ingestion")
    parser.add_argument("--chunk-size", type=int, default=500, help="Tokens per chunk")
    parser.add_argument("--chunk-overlap", type=int, default=50, help="Token overlap")
    parser.add_argument("--embedding-model", default="", help="Sentence transformer model name")
    parser.add_argument("--chroma-path", default="", help="ChromaDB persist directory")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Drop all existing chunks before ingesting (removes stale/fixture entries)",
    )
    args = parser.parse_args()

    corpus_path = Path(args.corpus) if args.corpus else DEFAULT_CORPUS_PATH

    if args.validate:
        sys.exit(_run_validate(corpus_path, as_json=args.json))
    if args.stats:
        sys.exit(_run_stats(corpus_path, as_json=args.json))
    if args.coverage:
        sys.exit(_run_coverage(corpus_path, as_json=args.json))

    _run_ingest(args, corpus_path)


def _run_validate(corpus_path: Path, as_json: bool) -> int:
    manifest = load_corpus(corpus_path)
    report = validate_corpus(manifest, corpus_path=corpus_path)
    if as_json:
        print(report.model_dump_json(indent=2))
    else:
        print(f"Corpus: {corpus_path}")
        print(f"Documents: {report.n_documents}  verified: {report.n_verified}  production: {report.n_production}")
        print(f"Errors: {len(report.errors)}  Warnings: {len(report.warnings)}")
        for issue in report.errors:
            print(f"  ERROR   [{issue.document_id or '-'}] {issue.code}: {issue.message}")
        for issue in report.warnings:
            print(f"  WARNING [{issue.document_id or '-'}] {issue.code}: {issue.message}")
        if report.duplicate_hashes:
            print("Duplicate content:")
            for digest, ids in report.duplicate_hashes.items():
                print(f"  {digest[:12]}…: {ids}")
        print("RESULT:", "VALID" if report.valid else "INVALID")
    return 0 if report.valid else 1


def _run_stats(corpus_path: Path, as_json: bool) -> int:
    manifest = load_corpus(corpus_path)
    stats = corpus_statistics(manifest)
    if as_json:
        print(stats.model_dump_json(indent=2))
    else:
        print(f"Corpus: {corpus_path}")
        print(f"Total candidates: {stats.n_total}  production (verified): {stats.n_production}")
        print(
            "Status: "
            f"VERIFIED={stats.n_verified} UNVERIFIED={stats.n_unverified} "
            f"REJECTED={stats.n_rejected} DUPLICATE={stats.n_duplicate} "
            f"OCR_REQUIRED={stats.n_ocr_required} "
            f"NEEDS_MANUAL_ACCESS={stats.n_needs_manual_access} "
            f"NEEDS_MANUAL_DOWNLOAD={stats.n_needs_manual_download}"
        )
        print("By source type (production):", stats.by_source_type)
        print("By mechanism (production):", stats.by_mechanism)
        print("By observable (production):", stats.by_observable)
        print("By test condition (production):", stats.by_test_condition)
    return 0


def _run_coverage(corpus_path: Path, as_json: bool) -> int:
    manifest = load_corpus(corpus_path)
    report = coverage_report(manifest)
    if as_json:
        print(report.model_dump_json(indent=2))
    else:
        for axis in ("mechanisms", "observables", "test_conditions"):
            print(f"{axis}:")
            for entry in getattr(report, axis):
                print(f"  {entry.level.value:8s} {entry.key} ({entry.n_documents})")
    return 0


def _run_ingest(args, corpus_path: Path) -> None:
    settings = LLMSettings()
    embed_model = args.embedding_model or settings.embedding_model
    chroma_path = args.chroma_path or settings.chroma_path

    print(f"Embedding model: {embed_model}")
    print(f"ChromaDB path: {chroma_path}")

    files: list[Path] = []
    if args.kb_path:
        files.extend(discover_documents(args.kb_path))
    else:
        files.extend(discover_documents(REPO / DEFAULT_DOCUMENTS_DIR))
    corpus_files = discover_corpus_documents(REPO, corpus_path)
    print(f"Verified corpus documents: {len(corpus_files)}")
    files.extend(corpus_files)
    # De-duplicate while preserving order.
    files = list(dict.fromkeys(files))
    print(f"Found {len(files)} documents")

    if not files:
        print("No documents found. Creating sample fixture corpus...")
        _create_sample_fixtures()
        files = discover_documents(REPO / DEFAULT_DOCUMENTS_DIR)
        print(f"Created {len(files)} sample documents")

    print("Loading embedder...")
    embedder = build_embedder(embed_model)

    print("Initializing ChromaDB...")
    chroma = ChromaRetriever(chroma_path)
    if args.reset:
        removed = chroma.reset()
        print(f"Reset collection: removed {removed} existing chunks")

    print("Ingesting...")
    result = ingest_documents(
        chroma,
        embedder,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
        files=files,
    )
    print(json.dumps(result, indent=2))
    print(f"Total chunks in ChromaDB: {chroma.count()}")


def _create_sample_fixtures() -> None:
    base = REPO / DEFAULT_DOCUMENTS_DIR
    sample_docs = {
        "standards/fixture-sic-power-cycling.md": (
            "## SiC Power Cycling Reliability (FIXTURE)\n\n"
            "Fixture text for pipeline testing only. It is not a verified standard "
            "and must not be cited as engineering evidence.\n\n"
            "Power cycling applies thermomechanical stress at material interfaces. "
            "Temperature swing magnitude and cycle duration influence degradation. "
            "No single observable uniquely identifies a physical mechanism; "
            "corroborating multi-parameter evidence is required.\n"
        ),
        "manufacturer/fixture-sic-bias-temperature-instability.md": (
            "## SiC MOSFET Bias Temperature Instability (FIXTURE)\n\n"
            "Fixture text for pipeline testing only. Threshold-voltage shift under "
            "gate bias is time- and temperature-dependent, and measurements recover. "
            "It is a candidate observation requiring corroborating evidence.\n"
        ),
        "papers/fixture-condition-monitoring-overview.md": (
            "## Condition Monitoring for SiC Power Modules (FIXTURE)\n\n"
            "Fixture text for pipeline testing only. Multiple parameters should be "
            "monitored together. No single observable uniquely identifies a physical "
            "degradation mechanism.\n"
        ),
    }
    for rel, content in sample_docs.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content.strip())


if __name__ == "__main__":
    main()

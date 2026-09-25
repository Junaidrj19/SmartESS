# Reliability Knowledge Base

This directory holds the curated engineering **evidence corpus** for the M9
investigation engine. It provides supporting evidence for hypothesis generation.
It is **not** a root-cause classifier.

## Layout

```text
knowledge_base/
├── corpus/                 # source PDFs (downloaded, not committed)
│   ├── standards/          # standards-body documents        (source_type: standard)
│   ├── manufacturers/      # vendor/application documents    (source_type: manufacturer)
│   ├── papers/             # primary research                (source_type: peer_reviewed)
│   ├── reviews/            # review / survey documents       (source_type: review)
│   └── internal/           # internal documents (if any)     (source_type: internal)
├── metadata/
│   └── corpus.json         # versioned candidate/verified manifest
├── documents/              # small text fixture documents (md/txt)
├── fixtures/               # test-only fixtures (NEVER production corpus)
├── reports/                # generated coverage / gap analysis
├── processed/              # derived/processed artifacts
└── chroma/                 # ChromaDB persist directory (not committed)
```

## Current corpus state

| | |
| --- | --- |
| Corpus version | `1.0.0` |
| Manifest entries | 37 |
| Production (`VERIFIED`) documents | 19 |
| ChromaDB collection | `evidence` |
| ChromaDB chunks | 360 |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Last ingest | 2026-09-24 |

Per-bucket: 1 standard, 12 manufacturer documents, 4 peer-reviewed papers,
2 reviews. Full coverage and gap analysis: `reports/corpus-coverage.md`.

Retrieval re-verified during the M9 freeze (2026-09-24): 360 unique chunk ids
(no duplicates), 19/19 stored documents marked `VERIFIED` in the manifest, no
fixture-only or unverified documents in the collection, and 0 retrieved chunks
with incomplete provenance (`document_id`, `chunk_id`, `citation`, `url`,
`page_start`/`page_end`).

**This corpus is not complete.** Four of five standards candidates and five of
nine peer-reviewed candidates are paywalled or publisher-blocked. Read the gap
analysis before drawing conclusions about coverage.

## Rules

1. **Nothing is fabricated and nothing is inferred from a title.** Documents in
   `corpus/` were downloaded from official publisher, manufacturer or institutional
   hosts, then opened with the project PDF tooling. Metadata in `corpus.json` comes
   from the document itself (title page, document number, revision, author list),
   never from a search-result snippet.
2. **A URL is not verification.** A document is marked `VERIFIED` only when the
   canonical PDF has been obtained locally, inspected, and its identity corroborated
   by the file's own content.
3. **Access controls are never bypassed.** No paywall is circumvented, no
   authentication or DRM is defeated, and no pirated copy is used. Where a document
   cannot be obtained legitimately it is recorded as `NEEDS_MANUAL_ACCESS` with its
   official URL and the reason, and the corpus continues without it. Where an
   equivalent legitimate open-access version of the *same* work exists, that version
   is used and the accessed version is recorded.
4. **Fixtures are test-only.** Anything under `fixtures/` is excluded from the
   production corpus and from production statistics, even if marked `VERIFIED`.
5. **Research notes are not sources.** The condition-monitoring relationships
   (C1–C10), the coverage matrix, the executive summary, and the evidence-gap
   analysis are research notes. They must never be turned into fake PDFs or fake
   knowledge documents. Real evidence must come from the underlying source
   documents.
6. **Coverage is declared from content, never inferred.** `mechanisms`,
   `observables`, and `test_conditions` are populated only where the extracted text
   of the document actually discusses the item. Documents that were not read
   (paywalled, OCR-only, rejected, unresolved) declare **no** coverage.
7. **Provenance is preserved end-to-end.** Every `EvidenceRecord` retrieved from this
   base retains its `document_id`, title, `source_type`, `citation`, `url`, and
   `page_start`/`page_end`, so a report finding can be traced to a specific page of a
   specific document. The manifest metadata is written into the vector store at
   ingestion time rather than re-derived from filenames.
8. **The corpus is versioned.** `corpus.json` carries a `corpus_version`. Model,
   feature, and investigation artifacts should reference the corpus version they
   were produced against.
9. **No single observable identifies a mechanism.** The knowledge base must not
   encode deterministic mappings such as `RDS_on ↑ → bond-wire failure`,
   `VTH shift → permanent gate-oxide failure`, `IGSS ↑ → gate-oxide breakdown`,
   or `Tj ↑ → die-attach failure`. These are candidate relationships that require
   corroborating evidence. Mechanisms, observables, and test conditions are
   independent axes. The corpus literature itself documents that these mappings are
   ambiguous (see the gap analysis, section 9).

## Verification status values

| Status | Meaning |
| --- | --- |
| `UNVERIFIED` | Candidate from research; not confirmed. Either not yet resolved to a real document, or awaiting operator action. Never production corpus. |
| `VERIFIED` | Canonical PDF obtained locally and confirmed from the document's own content. Production corpus. |
| `REJECTED` | Reviewed and excluded. Recorded with the reason so the decision stays traceable. |
| `DUPLICATE` | Same intellectual work or identical content as another document. |
| `NEEDS_MANUAL_ACCESS` | A legitimate canonical document exists but cannot be obtained without a human (paywall, licence acceptance, login-gated distribution, or publisher blocking automated retrieval). Official URL and reason recorded. |
| `OCR_REQUIRED` | The PDF was obtained and its identity confirmed, but it has no text layer. It cannot enter retrieval until OCR is available, and it is never ingested as if it had been processed. |
| `NEEDS_MANUAL_DOWNLOAD` | Retained for backwards compatibility; same meaning as `NEEDS_MANUAL_ACCESS`. |

## Tooling

```bash
# Validate manifest + local PDFs (existence, readability, page count, text
# extraction or OCR_REQUIRED, SHA-256, uniqueness, duplicates, metadata).
python3 scripts/ingest_knowledge.py --validate

# Corpus statistics (verified / unverified / rejected / by axis).
python3 scripts/ingest_knowledge.py --stats

# EXPLICIT / PARTIAL / NONE coverage across mechanisms, observables, and test
# conditions. Coverage requires a VERIFIED document that declares the item; it
# is never inferred from a title.
python3 scripts/ingest_knowledge.py --coverage

# Ingest verified corpus PDFs + text documents into ChromaDB.
python3 scripts/ingest_knowledge.py --ingest

# Same, but drop every existing chunk first. Use after changing the manifest so
# stale or fixture chunks cannot survive in the production collection.
python3 scripts/ingest_knowledge.py --ingest --reset
```

Ingestion is idempotent: chunks carry stable ids derived from the document id and
chunk index, and each document's existing chunks are removed before its new chunks
are written, so running `--ingest` repeatedly never inflates the collection.

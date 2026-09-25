"""Curated reliability-corpus metadata for the M9 engineering knowledge base.

This module models *candidate* source documents for the production evidence
corpus. It does not download, scrape, or fabricate documents. A candidate only
becomes production corpus after a human operator obtains the canonical PDF from
the official/publisher source, places it locally, and marks the entry
``VERIFIED``.

Epistemic rule (binding, from ``agent-rules.md`` and the M9 knowledge-base
charter): **no single observable uniquely identifies a physical degradation
mechanism.** This module must never encode one-to-one mappings such as
``RDS_on -> bond-wire failure`` or ``VTH shift -> gate-oxide failure``.
Mechanisms, observables, and test conditions are treated as independent axes.
Coverage is *declared* on a document, never inferred from a title.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.knowledge.pdf import PdfInspection, inspect_pdf

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS_PATH = REPO / "knowledge_base" / "metadata" / "corpus.json"
CORPUS_ROOT = REPO / "knowledge_base" / "corpus"
FIXTURES_ROOT = REPO / "knowledge_base" / "fixtures"


class SourceType(str, Enum):
    STANDARD = "standard"
    MANUFACTURER = "manufacturer"
    PEER_REVIEWED = "peer_reviewed"
    REVIEW = "review"
    INTERNAL = "internal"


class VerificationStatus(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    DUPLICATE = "DUPLICATE"
    # A legitimate canonical document exists but cannot be obtained without a
    # human: paywall, licence acceptance, login-gated distribution, or automated
    # retrieval being blocked by the publisher. Never bypassed automatically.
    NEEDS_MANUAL_ACCESS = "NEEDS_MANUAL_ACCESS"
    # The PDF was obtained and its identity confirmed, but it carries no text
    # layer. It cannot enter retrieval until OCR is run; it is never ingested as
    # if it had been processed successfully.
    OCR_REQUIRED = "OCR_REQUIRED"
    # Retained for backwards compatibility; same meaning as NEEDS_MANUAL_ACCESS.
    NEEDS_MANUAL_DOWNLOAD = "NEEDS_MANUAL_DOWNLOAD"


class AccessType(str, Enum):
    EXTERNAL = "external"
    INTERNAL = "internal"
    UNKNOWN = "unknown"


class Mechanism(str, Enum):
    BOND_WIRE_INTERCONNECT = "bond_wire_interconnect"
    DIE_ATTACH_THERMAL_PATH = "die_attach_thermal_path"
    GATE_RELATED = "gate_related"
    THERMAL_PATH = "thermal_path"
    PACKAGE_INTERCONNECT = "package_interconnect"
    CROSS_CUTTING = "cross_cutting"


class Observable(str, Enum):
    RDS_ON = "RDS_on"
    VTH = "VTH"
    IGSS = "IGSS"
    IDSS = "IDSS"
    VDS_ON = "VDS_on"
    ELECTRICAL_POWER = "electrical_power"
    TJ = "Tj"
    TC = "Tc"
    THERMAL_RESISTANCE = "thermal_resistance"


class TestCondition(str, Enum):
    POWER_CYCLING = "power_cycling"
    THERMAL_CYCLING = "thermal_cycling"
    GATE_BIAS = "gate_bias"
    HTOL = "HTOL"
    HTRB = "HTRB"
    HTGB = "HTGB"


# Maps a source type to its bucket directory under ``knowledge_base/corpus``.
SOURCE_TYPE_BUCKETS: Dict[SourceType, str] = {
    SourceType.STANDARD: "standards",
    SourceType.MANUFACTURER: "manufacturers",
    SourceType.PEER_REVIEWED: "papers",
    SourceType.REVIEW: "reviews",
    SourceType.INTERNAL: "internal",
}


class CorpusDocument(BaseModel):
    """A candidate or verified source document in the reliability corpus."""

    model_config = ConfigDict(extra="forbid")

    document_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_type: SourceType
    organization: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    publication_year: Optional[int] = None
    publisher: Optional[str] = None
    url: Optional[str] = None
    local_filename: Optional[str] = None
    local_path: Optional[str] = None
    citation: Optional[str] = None
    access_type: AccessType = AccessType.UNKNOWN
    mechanisms: List[Mechanism] = Field(default_factory=list)
    observables: List[Observable] = Field(default_factory=list)
    test_conditions: List[TestCondition] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    description: str = ""
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED

    @field_validator("publication_year")
    @classmethod
    def _year_range(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and not (1900 <= value <= 2100):
            raise ValueError("publication_year must be between 1900 and 2100")
        return value


class CorpusManifest(BaseModel):
    """Versioned collection of candidate and verified corpus documents."""

    model_config = ConfigDict(extra="forbid")

    corpus_version: str = "0.1.0"
    generated_at: str = ""
    note: str = ""
    documents: List[CorpusDocument] = Field(default_factory=list)

    def by_id(self, document_id: str) -> Optional[CorpusDocument]:
        for document in self.documents:
            if document.document_id == document_id:
                return document
        return None

    @property
    def verified(self) -> List[CorpusDocument]:
        return [
            d
            for d in self.documents
            if d.verification_status is VerificationStatus.VERIFIED
        ]


def load_corpus(path: str | Path | None = None) -> CorpusManifest:
    """Load and validate a corpus manifest from disk."""
    manifest_path = Path(path) if path else DEFAULT_CORPUS_PATH
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    return CorpusManifest.model_validate(data)


def resolve_local_path(document: CorpusDocument, repo_root: Path | None = None) -> Optional[Path]:
    """Resolve a document's ``local_path`` relative to the repository root."""
    if not document.local_path:
        return None
    base = repo_root if repo_root is not None else REPO
    candidate = Path(document.local_path)
    if candidate.is_absolute():
        return candidate
    return base / candidate


def is_fixture(document: CorpusDocument, repo_root: Path | None = None) -> bool:
    """True when a document lives under the test-only fixtures tree."""
    resolved = resolve_local_path(document, repo_root)
    if resolved is None:
        return False
    fixtures = (repo_root / "knowledge_base" / "fixtures") if repo_root else FIXTURES_ROOT
    try:
        resolved.resolve().relative_to(fixtures.resolve())
        return True
    except ValueError:
        return False


class Severity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class ValidationIssue(BaseModel):
    document_id: Optional[str] = None
    severity: Severity
    code: str
    message: str


class DocumentInspection(BaseModel):
    document_id: str
    local_path: Optional[str] = None
    exists: bool = False
    readable: bool = False
    is_pdf: bool = False
    page_count: int = 0
    text_extractable: bool = False
    ocr_required: bool = False
    sha256: Optional[str] = None
    size_bytes: int = 0
    error: Optional[str] = None


class CorpusValidationReport(BaseModel):
    corpus_version: str
    corpus_path: str
    n_documents: int
    n_verified: int
    n_production: int
    errors: List[ValidationIssue] = Field(default_factory=list)
    warnings: List[ValidationIssue] = Field(default_factory=list)
    inspections: List[DocumentInspection] = Field(default_factory=list)
    duplicate_hashes: Dict[str, List[str]] = Field(default_factory=dict)

    @property
    def valid(self) -> bool:
        return len(self.errors) == 0

    def issues_for(self, severity: Severity) -> List[ValidationIssue]:
        return self.errors if severity is Severity.ERROR else self.warnings


def _inspection_to_model(inspection: PdfInspection, document_id: str) -> DocumentInspection:
    return DocumentInspection(
        document_id=document_id,
        local_path=inspection.path,
        exists=inspection.exists,
        readable=inspection.readable,
        is_pdf=inspection.is_pdf,
        page_count=inspection.page_count,
        text_extractable=inspection.text_extractable,
        ocr_required=inspection.ocr_required,
        sha256=inspection.sha256,
        size_bytes=inspection.size_bytes,
        error=inspection.error,
    )


def validate_corpus(
    manifest: CorpusManifest,
    repo_root: str | Path | None = None,
    corpus_path: str | Path | None = None,
) -> CorpusValidationReport:
    """Validate a corpus manifest and any local PDFs it references.

    A broken or empty PDF is never silently accepted: it produces an ERROR when
    the document is marked VERIFIED, and a WARNING otherwise.
    """
    root = Path(repo_root) if repo_root is not None else REPO
    report = CorpusValidationReport(
        corpus_version=manifest.corpus_version,
        corpus_path=str(corpus_path if corpus_path is not None else DEFAULT_CORPUS_PATH),
        n_documents=len(manifest.documents),
        n_verified=len(manifest.verified),
        n_production=0,
    )

    seen_ids: Dict[str, int] = {}
    seen_paths: Dict[str, str] = {}
    hash_to_ids: Dict[str, List[str]] = {}
    production = 0

    for document in manifest.documents:
        doc_id = document.document_id

        # --- document_id uniqueness -------------------------------------
        if doc_id in seen_ids:
            report.errors.append(
                ValidationIssue(
                    document_id=doc_id,
                    severity=Severity.ERROR,
                    code="duplicate_document_id",
                    message=f"document_id '{doc_id}' appears more than once",
                )
            )
        seen_ids[doc_id] = seen_ids.get(doc_id, 0) + 1

        # --- title presence ---------------------------------------------
        if not document.title.strip():
            report.errors.append(
                ValidationIssue(
                    document_id=doc_id,
                    severity=Severity.ERROR,
                    code="missing_title",
                    message="title must not be empty",
                )
            )

        # --- URL for external sources -----------------------------------
        if document.access_type is AccessType.EXTERNAL and not document.url:
            if document.verification_status is VerificationStatus.VERIFIED:
                report.errors.append(
                    ValidationIssue(
                        document_id=doc_id,
                        severity=Severity.ERROR,
                        code="missing_url",
                        message="verified external source requires a source URL",
                    )
                )
            else:
                report.warnings.append(
                    ValidationIssue(
                        document_id=doc_id,
                        severity=Severity.WARNING,
                        code="url_pending_verification",
                        message="external candidate has no URL yet (manual verification pending)",
                    )
                )

        # --- at least one locator (metadata exists) ---------------------
        if not document.url and not document.local_path:
            report.errors.append(
                ValidationIssue(
                    document_id=doc_id,
                    severity=Severity.ERROR,
                    code="no_locator",
                    message="document has neither a URL nor a local_path",
                )
            )

        # --- local_path uniqueness --------------------------------------
        if document.local_path:
            if document.local_path in seen_paths:
                report.errors.append(
                    ValidationIssue(
                        document_id=doc_id,
                        severity=Severity.ERROR,
                        code="duplicate_local_path",
                        message=(
                            f"local_path '{document.local_path}' already used by "
                            f"'{seen_paths[document.local_path]}'"
                        ),
                    )
                )
            else:
                seen_paths[document.local_path] = doc_id

        # --- production vs fixture separation ---------------------------
        fixture = is_fixture(document, root)
        if fixture:
            report.warnings.append(
                ValidationIssue(
                    document_id=doc_id,
                    severity=Severity.WARNING,
                    code="fixture_document",
                    message="document lives under fixtures/ and is excluded from production corpus",
                )
            )

        # --- PDF inspection ---------------------------------------------
        resolved = resolve_local_path(document, root)
        if resolved is None:
            continue

        inspection = inspect_pdf(resolved)
        report.inspections.append(_inspection_to_model(inspection, doc_id))

        verified = document.verification_status is VerificationStatus.VERIFIED
        severity = Severity.ERROR if verified else Severity.WARNING

        if not inspection.exists:
            report.issues_for(severity).append(
                ValidationIssue(
                    document_id=doc_id,
                    severity=severity,
                    code="pdf_missing",
                    message=f"local PDF not found: {document.local_path}",
                )
            )
            continue

        if inspection.sha256:
            hash_to_ids.setdefault(inspection.sha256, []).append(doc_id)

        if inspection.size_bytes == 0:
            report.issues_for(severity).append(
                ValidationIssue(
                    document_id=doc_id,
                    severity=severity,
                    code="pdf_empty",
                    message="file is empty (0 bytes)",
                )
            )
            continue

        if not inspection.is_pdf:
            report.issues_for(severity).append(
                ValidationIssue(
                    document_id=doc_id,
                    severity=severity,
                    code="pdf_not_pdf",
                    message=inspection.error or "file is not a valid PDF",
                )
            )
            continue

        if not inspection.readable:
            report.issues_for(severity).append(
                ValidationIssue(
                    document_id=doc_id,
                    severity=severity,
                    code="pdf_unreadable",
                    message=inspection.error or "PDF cannot be parsed",
                )
            )
            continue

        if inspection.page_count <= 0:
            report.issues_for(severity).append(
                ValidationIssue(
                    document_id=doc_id,
                    severity=severity,
                    code="pdf_empty",
                    message="PDF has no pages",
                )
            )
            continue

        if inspection.ocr_required:
            # OCR_REQUIRED is always explicitly reported as a warning: the file is
            # a valid PDF but needs a text layer before it can enter retrieval.
            report.warnings.append(
                ValidationIssue(
                    document_id=doc_id,
                    severity=Severity.WARNING,
                    code="ocr_required",
                    message=inspection.error or "no extractable text; OCR_REQUIRED",
                )
            )

        if verified and not fixture and inspection.usable:
            production += 1

    # --- duplicate content detection ------------------------------------
    for digest, ids in hash_to_ids.items():
        if len(ids) > 1:
            report.duplicate_hashes[digest] = ids
            report.errors.append(
                ValidationIssue(
                    severity=Severity.ERROR,
                    code="duplicate_content",
                    message=f"identical PDF content (sha256 {digest[:12]}…) shared by {ids}",
                )
            )

    report.n_production = production
    return report


def corpus_statistics(manifest: CorpusManifest) -> "CorpusStatistics":
    """Count documents by status and by declared axis over the production corpus.

    Only ``VERIFIED`` documents with a resolvable, usable local PDF (and not
    living under fixtures/) are treated as production. Unverified candidates are
    reported but never counted toward production coverage.
    """
    stats = CorpusStatistics(
        corpus_version=manifest.corpus_version,
        n_total=len(manifest.documents),
    )

    for document in manifest.documents:
        status = document.verification_status
        if status is VerificationStatus.VERIFIED:
            stats.n_verified += 1
        elif status is VerificationStatus.UNVERIFIED:
            stats.n_unverified += 1
        elif status is VerificationStatus.REJECTED:
            stats.n_rejected += 1
        elif status is VerificationStatus.DUPLICATE:
            stats.n_duplicate += 1
        elif status is VerificationStatus.NEEDS_MANUAL_ACCESS:
            stats.n_needs_manual_access += 1
        elif status is VerificationStatus.OCR_REQUIRED:
            stats.n_ocr_required += 1
        elif status is VerificationStatus.NEEDS_MANUAL_DOWNLOAD:
            stats.n_needs_manual_download += 1

    production_docs = [
        d
        for d in manifest.documents
        if d.verification_status is VerificationStatus.VERIFIED
    ]
    stats.n_production = len(production_docs)

    stats.by_source_type = _count(stats.by_source_type, (d.source_type.value for d in production_docs))
    stats.by_mechanism = _count(stats.by_mechanism, (m.value for d in production_docs for m in d.mechanisms))
    stats.by_observable = _count(stats.by_observable, (o.value for d in production_docs for o in d.observables))
    stats.by_test_condition = _count(
        stats.by_test_condition, (t.value for d in production_docs for t in d.test_conditions)
    )
    return stats


class CorpusStatistics(BaseModel):
    corpus_version: str
    n_total: int = 0
    n_production: int = 0
    n_verified: int = 0
    n_unverified: int = 0
    n_rejected: int = 0
    n_duplicate: int = 0
    n_needs_manual_access: int = 0
    n_ocr_required: int = 0
    n_needs_manual_download: int = 0
    by_source_type: Dict[str, int] = Field(default_factory=dict)
    by_mechanism: Dict[str, int] = Field(default_factory=dict)
    by_observable: Dict[str, int] = Field(default_factory=dict)
    by_test_condition: Dict[str, int] = Field(default_factory=dict)


class CoverageLevel(str, Enum):
    EXPLICIT = "EXPLICIT"
    PARTIAL = "PARTIAL"
    NONE = "NONE"


class CoverageEntry(BaseModel):
    key: str
    level: CoverageLevel
    n_documents: int


class CoverageReport(BaseModel):
    mechanisms: List[CoverageEntry] = Field(default_factory=list)
    observables: List[CoverageEntry] = Field(default_factory=list)
    test_conditions: List[CoverageEntry] = Field(default_factory=list)


def _coverage_for(axis: str, manifest: CorpusManifest) -> List[CoverageEntry]:
    explicit: Dict[str, int] = {}
    candidate: Dict[str, int] = {}

    for document in manifest.documents:
        values = getattr(document, axis)
        bucket = explicit if document.verification_status is VerificationStatus.VERIFIED else candidate
        for value in values:
            key = value.value
            bucket[key] = bucket.get(key, 0) + 1

    if axis == "mechanisms":
        universe = [m.value for m in Mechanism]
    elif axis == "observables":
        universe = [o.value for o in Observable]
    else:
        universe = [t.value for t in TestCondition]

    entries: List[CoverageEntry] = []
    for key in universe:
        if explicit.get(key, 0) > 0:
            entries.append(CoverageEntry(key=key, level=CoverageLevel.EXPLICIT, n_documents=explicit[key]))
        elif candidate.get(key, 0) > 0:
            entries.append(CoverageEntry(key=key, level=CoverageLevel.PARTIAL, n_documents=candidate[key]))
        else:
            entries.append(CoverageEntry(key=key, level=CoverageLevel.NONE, n_documents=0))
    return entries


def coverage_report(manifest: CorpusManifest) -> CoverageReport:
    """Report EXPLICIT/PARTIAL/NONE coverage across the three axes.

    EXPlicit coverage requires a VERIFIED document that *declares* the item.
    Items that appear only on unverified candidates are PARTIAL. Coverage is
    never inferred from a document title.
    """
    return CoverageReport(
        mechanisms=_coverage_for("mechanisms", manifest),
        observables=_coverage_for("observables", manifest),
        test_conditions=_coverage_for("test_conditions", manifest),
    )


def _count(accumulator: Dict[str, int], values) -> Dict[str, int]:
    for value in values:
        accumulator[value] = accumulator.get(value, 0) + 1
    return accumulator

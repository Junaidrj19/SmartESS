"""M9 curated-corpus manifest, validation, statistics, and coverage tests.

These tests build their own manifests and PDFs in ``tmp_path`` so they never
depend on the final, manually curated corpus.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.knowledge.corpus import (  # noqa: E402
    AccessType,
    CorpusDocument,
    CorpusManifest,
    CoverageLevel,
    Mechanism,
    Observable,
    SourceType,
    VerificationStatus,
    corpus_statistics,
    coverage_report,
    is_fixture,
    load_corpus,
    validate_corpus,
)
from backend.knowledge.corpus import TestCondition as Condition  # noqa: E402
from backend.knowledge.pdf import inspect_pdf  # noqa: E402

REPO = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _write_text_pdf(path: Path, text: str = "Reliability evidence fixture text for testing purposes.") -> Path:
    """Write a small but genuinely text-extractable PDF."""
    from reportlab.pdfgen import canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path))
    c.drawString(72, 720, text)
    c.save()
    return path


def _write_blank_pdf(path: Path) -> Path:
    """Write a PDF with a page but no text (image-only / OCR territory)."""
    from reportlab.pdfgen import canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path))
    c.showPage()
    c.save()
    return path


def _doc(document_id: str, **overrides) -> CorpusDocument:
    payload = {
        "document_id": document_id,
        "title": f"Title {document_id}",
        "source_type": SourceType.STANDARD,
    }
    payload.update(overrides)
    return CorpusDocument(**payload)


# --------------------------------------------------------------------------- #
# model-level validation
# --------------------------------------------------------------------------- #
class TestCorpusDocument:
    def test_defaults(self):
        d = _doc("d1")
        assert d.verification_status is VerificationStatus.UNVERIFIED
        assert d.access_type is AccessType.UNKNOWN
        assert d.mechanisms == []
        assert d.observables == []
        assert d.test_conditions == []

    def test_invalid_source_type_rejected(self):
        with pytest.raises(ValidationError):
            _doc("d1", source_type="not-a-type")

    def test_unknown_mechanism_rejected(self):
        with pytest.raises(ValidationError):
            _doc("d1", mechanisms=["rds_on_failure"])

    def test_publication_year_range(self):
        with pytest.raises(ValidationError):
            _doc("d1", publication_year=1234)

    def test_extra_field_forbidden(self):
        with pytest.raises(ValidationError):
            _doc("d1", nonsense="x")


# --------------------------------------------------------------------------- #
# committed manifest structure (candidates only; no verified production needed)
# --------------------------------------------------------------------------- #
class TestCommittedManifest:
    def test_manifest_loads(self):
        manifest = load_corpus()
        assert manifest.corpus_version
        assert len(manifest.documents) > 0

    def test_manifest_validates_without_errors(self):
        report = validate_corpus(load_corpus())
        assert report.valid, [i.message for i in report.errors]

    def test_candidate_sources_all_present(self):
        # The candidate list must stay traceable: S1-S5, M1-M9, P1-P6, R1-R3 plus
        # the optional R4/P8/P9/P10/R5. Documents were added and reclassified, but
        # no candidate may silently disappear from the manifest.
        manifest = load_corpus()
        refs = sorted(
            tag.split(":", 1)[1]
            for d in manifest.documents
            for tag in d.tags
            if tag.startswith("source-ref:")
        )
        expected = [f"S{i}" for i in range(1, 6)]
        expected += [f"M{i}" for i in range(1, 10)]
        expected += [f"P{i}" for i in range(1, 7)]
        expected += [f"R{i}" for i in range(1, 4)]
        expected += ["R4", "R5", "P8", "P9", "P10"]
        assert refs == sorted(expected)

    def test_no_placeholder_titles_remain(self):
        # A populated corpus must not still carry research-pass placeholders.
        manifest = load_corpus()
        for d in manifest.documents:
            lowered = d.title.lower()
            assert "unverified" not in lowered, d.document_id
            assert "pending manual verification" not in lowered, d.document_id

    def test_verified_documents_are_grounded(self):
        # Every VERIFIED document must be traceable to a real, readable, local PDF
        # and must carry a citation and a description. Identity is never asserted
        # from a URL alone.
        manifest = load_corpus()
        assert manifest.verified, "expected a populated production corpus"
        for d in manifest.verified:
            assert d.url, f"{d.document_id}: verified document needs a source URL"
            assert d.local_path, f"{d.document_id}: verified document needs a local PDF"
            assert (d.citation or "").strip(), f"{d.document_id}: verified document needs a citation"
            assert (d.description or "").strip(), f"{d.document_id}: verified document needs a description"
            assert not is_fixture(d), f"{d.document_id}: fixtures must never be production"
            resolved = REPO / d.local_path
            assert resolved.exists(), f"{d.document_id}: local PDF missing"
            inspection = inspect_pdf(resolved)
            assert inspection.usable, f"{d.document_id}: unreadable PDF ({inspection.error})"

    def test_unavailable_documents_declare_no_coverage(self):
        # Coverage may only be declared for documents whose text was actually read.
        # A paywalled, OCR-only, rejected or unresolved candidate must stay empty so
        # that coverage is never inferred from a title or a URL.
        manifest = load_corpus()
        for d in manifest.documents:
            if d.verification_status is VerificationStatus.VERIFIED:
                continue
            assert d.mechanisms == [], f"{d.document_id} declares mechanisms without evidence"
            assert d.observables == [], f"{d.document_id} declares observables without evidence"
            assert d.test_conditions == [], f"{d.document_id} declares conditions without evidence"

    def test_coverage_is_explicit_only_for_verified_documents(self):
        manifest = load_corpus()
        report = coverage_report(manifest)
        entries = report.mechanisms + report.observables + report.test_conditions
        assert any(e.level is CoverageLevel.EXPLICIT for e in entries)
        for entry in entries:
            assert entry.level in (CoverageLevel.EXPLICIT, CoverageLevel.NONE), entry.key


# --------------------------------------------------------------------------- #
# verification status
# --------------------------------------------------------------------------- #
class TestVerificationStatus:
    def test_verified_external_requires_url(self):
        doc = _doc(
            "d1",
            source_type=SourceType.STANDARD,
            access_type=AccessType.EXTERNAL,
            verification_status=VerificationStatus.VERIFIED,
            local_path="x.pdf",
        )
        report = validate_corpus(CorpusManifest(documents=[doc]))
        codes = [i.code for i in report.errors]
        assert "missing_url" in codes

    def test_unverified_external_without_url_is_warning(self):
        doc = _doc(
            "d1",
            access_type=AccessType.EXTERNAL,
            local_path="missing.pdf",
        )
        report = validate_corpus(CorpusManifest(documents=[doc]))
        codes = [i.code for i in report.warnings]
        assert "url_pending_verification" in codes
        assert "missing_url" not in [i.code for i in report.errors]

    def test_status_counts(self):
        manifest = CorpusManifest(
            documents=[
                _doc("v", verification_status=VerificationStatus.VERIFIED),
                _doc("u", verification_status=VerificationStatus.UNVERIFIED),
                _doc("r", verification_status=VerificationStatus.REJECTED),
                _doc("d", verification_status=VerificationStatus.DUPLICATE),
                _doc("n", verification_status=VerificationStatus.NEEDS_MANUAL_DOWNLOAD),
            ]
        )
        stats = corpus_statistics(manifest)
        assert stats.n_verified == 1
        assert stats.n_unverified == 1
        assert stats.n_rejected == 1
        assert stats.n_duplicate == 1
        assert stats.n_needs_manual_download == 1
        assert stats.n_total == 5


# --------------------------------------------------------------------------- #
# duplicate detection
# --------------------------------------------------------------------------- #
class TestDuplicateDetection:
    def test_duplicate_document_id(self):
        manifest = CorpusManifest(documents=[_doc("same"), _doc("same")])
        report = validate_corpus(manifest)
        assert "duplicate_document_id" in [i.code for i in report.errors]

    def test_duplicate_local_path(self):
        manifest = CorpusManifest(
            documents=[
                _doc("a", local_path="p.pdf"),
                _doc("b", local_path="p.pdf"),
            ]
        )
        report = validate_corpus(manifest)
        assert "duplicate_local_path" in [i.code for i in report.errors]

    def test_duplicate_content(self, tmp_path):
        pdf_a = _write_text_pdf(tmp_path / "a.pdf")
        pdf_b = tmp_path / "b.pdf"
        pdf_b.write_bytes(pdf_a.read_bytes())  # guarantee identical bytes
        manifest = CorpusManifest(
            documents=[
                _doc("a", local_path="a.pdf"),
                _doc("b", local_path="b.pdf"),
            ]
        )
        report = validate_corpus(manifest, repo_root=tmp_path)
        assert report.duplicate_hashes
        assert "duplicate_content" in [i.code for i in report.errors]

    def test_distinct_content_not_duplicate(self, tmp_path):
        _write_text_pdf(tmp_path / "a.pdf", "First distinct document body for hashing.")
        _write_text_pdf(tmp_path / "b.pdf", "Second distinct document body for hashing.")
        manifest = CorpusManifest(
            documents=[
                _doc("a", local_path="a.pdf"),
                _doc("b", local_path="b.pdf"),
            ]
        )
        report = validate_corpus(manifest, repo_root=tmp_path)
        assert report.duplicate_hashes == {}


# --------------------------------------------------------------------------- #
# source-type classification
# --------------------------------------------------------------------------- #
class TestSourceTypeClassification:
    def test_bucket_mapping(self):
        from backend.knowledge.corpus import SOURCE_TYPE_BUCKETS

        assert SOURCE_TYPE_BUCKETS[SourceType.STANDARD] == "standards"
        assert SOURCE_TYPE_BUCKETS[SourceType.MANUFACTURER] == "manufacturers"
        assert SOURCE_TYPE_BUCKETS[SourceType.PEER_REVIEWED] == "papers"
        assert SOURCE_TYPE_BUCKETS[SourceType.REVIEW] == "reviews"
        assert SOURCE_TYPE_BUCKETS[SourceType.INTERNAL] == "internal"

    def test_infer_source_type_from_path(self):
        from backend.knowledge.ingestion import _infer_source_type

        assert _infer_source_type(Path("knowledge_base/corpus/standards/x.pdf")) == "standards"
        assert _infer_source_type(Path("knowledge_base/corpus/manufacturers/x.pdf")) == "manufacturers"
        assert _infer_source_type(Path("knowledge_base/corpus/papers/x.pdf")) == "papers"
        assert _infer_source_type(Path("knowledge_base/corpus/reviews/x.pdf")) == "reviews"
        assert _infer_source_type(Path("knowledge_base/documents/x.md")) == "other"


# --------------------------------------------------------------------------- #
# missing / broken PDF handling
# --------------------------------------------------------------------------- #
class TestMissingPdfHandling:
    def test_missing_pdf_unverified_is_warning(self):
        doc = _doc("d1", local_path="does-not-exist.pdf")
        report = validate_corpus(CorpusManifest(documents=[doc]))
        assert "pdf_missing" in [i.code for i in report.warnings]
        assert report.valid

    def test_missing_pdf_verified_is_error(self):
        doc = _doc(
            "d1",
            access_type=AccessType.INTERNAL,
            verification_status=VerificationStatus.VERIFIED,
            local_path="does-not-exist.pdf",
        )
        report = validate_corpus(CorpusManifest(documents=[doc]))
        assert "pdf_missing" in [i.code for i in report.errors]
        assert not report.valid

    def test_broken_pdf_is_rejected(self, tmp_path):
        bad = tmp_path / "bad.pdf"
        bad.write_bytes(b"this is not a pdf at all")
        doc = _doc(
            "d1",
            access_type=AccessType.INTERNAL,
            verification_status=VerificationStatus.VERIFIED,
            local_path="bad.pdf",
        )
        report = validate_corpus(CorpusManifest(documents=[doc]), repo_root=tmp_path)
        assert "pdf_not_pdf" in [i.code for i in report.errors]

    def test_empty_file_is_rejected(self, tmp_path):
        empty = tmp_path / "empty.pdf"
        empty.write_bytes(b"")
        doc = _doc(
            "d1",
            access_type=AccessType.INTERNAL,
            verification_status=VerificationStatus.VERIFIED,
            local_path="empty.pdf",
        )
        report = validate_corpus(CorpusManifest(documents=[doc]), repo_root=tmp_path)
        assert "pdf_empty" in [i.code for i in report.errors]

    def test_ocr_required_reported(self, tmp_path):
        _write_blank_pdf(tmp_path / "scan.pdf")
        doc = _doc(
            "d1",
            access_type=AccessType.INTERNAL,
            verification_status=VerificationStatus.VERIFIED,
            local_path="scan.pdf",
        )
        report = validate_corpus(CorpusManifest(documents=[doc]), repo_root=tmp_path)
        assert "ocr_required" in [i.code for i in report.warnings]

    def test_valid_pdf_passes_and_is_production(self, tmp_path):
        _write_text_pdf(tmp_path / "ok.pdf")
        doc = _doc(
            "d1",
            access_type=AccessType.INTERNAL,
            verification_status=VerificationStatus.VERIFIED,
            local_path="ok.pdf",
        )
        report = validate_corpus(CorpusManifest(documents=[doc]), repo_root=tmp_path)
        assert report.valid
        assert report.n_production == 1


# --------------------------------------------------------------------------- #
# metadata / PDF mismatch
# --------------------------------------------------------------------------- #
class TestMetadataPdfMismatch:
    def test_verified_external_missing_url_is_error(self):
        doc = _doc(
            "d1",
            access_type=AccessType.EXTERNAL,
            verification_status=VerificationStatus.VERIFIED,
            local_path="x.pdf",
        )
        report = validate_corpus(CorpusManifest(documents=[doc]))
        assert "missing_url" in [i.code for i in report.errors]

    def test_no_locator_is_error(self):
        doc = _doc("d1")
        report = validate_corpus(CorpusManifest(documents=[doc]))
        assert "no_locator" in [i.code for i in report.errors]

    def test_empty_title_is_error(self):
        with pytest.raises(ValidationError):
            _doc("d1", title="")


# --------------------------------------------------------------------------- #
# production vs fixture separation
# --------------------------------------------------------------------------- #
class TestProductionVsFixture:
    def test_fixture_excluded_from_production(self, tmp_path):
        _write_text_pdf(tmp_path / "knowledge_base/fixtures/f.pdf")
        doc = _doc(
            "fx",
            access_type=AccessType.INTERNAL,
            verification_status=VerificationStatus.VERIFIED,
            local_path="knowledge_base/fixtures/f.pdf",
        )
        assert is_fixture(doc, tmp_path)
        report = validate_corpus(CorpusManifest(documents=[doc]), repo_root=tmp_path)
        assert "fixture_document" in [i.code for i in report.warnings]
        assert report.n_production == 0

    def test_production_document_not_fixture(self, tmp_path):
        _write_text_pdf(tmp_path / "knowledge_base/corpus/standards/p.pdf")
        doc = _doc(
            "p",
            access_type=AccessType.INTERNAL,
            verification_status=VerificationStatus.VERIFIED,
            local_path="knowledge_base/corpus/standards/p.pdf",
        )
        assert not is_fixture(doc, tmp_path)
        report = validate_corpus(CorpusManifest(documents=[doc]), repo_root=tmp_path)
        assert report.n_production == 1

    def test_discover_corpus_excludes_fixtures_and_unverified(self, tmp_path):
        from backend.knowledge.ingestion import discover_corpus_documents

        _write_text_pdf(tmp_path / "knowledge_base/corpus/standards/verified.pdf")
        _write_text_pdf(tmp_path / "knowledge_base/corpus/standards/candidate.pdf")
        _write_text_pdf(tmp_path / "knowledge_base/fixtures/fixture.pdf")

        manifest = CorpusManifest(
            documents=[
                _doc(
                    "verified",
                    access_type=AccessType.INTERNAL,
                    verification_status=VerificationStatus.VERIFIED,
                    local_path="knowledge_base/corpus/standards/verified.pdf",
                ),
                _doc(
                    "candidate",
                    verification_status=VerificationStatus.UNVERIFIED,
                    local_path="knowledge_base/corpus/standards/candidate.pdf",
                ),
                _doc(
                    "fixture",
                    access_type=AccessType.INTERNAL,
                    verification_status=VerificationStatus.VERIFIED,
                    local_path="knowledge_base/fixtures/fixture.pdf",
                ),
            ]
        )
        manifest_path = tmp_path / "corpus.json"
        manifest_path.write_text(manifest.model_dump_json())

        paths = discover_corpus_documents(repo_root=tmp_path, corpus_path=manifest_path)
        names = {p.name for p in paths}
        assert names == {"verified.pdf"}


# --------------------------------------------------------------------------- #
# statistics & coverage
# --------------------------------------------------------------------------- #
class TestStatistics:
    def test_production_only_counts_verified(self):
        manifest = CorpusManifest(
            documents=[
                _doc(
                    "v",
                    source_type=SourceType.STANDARD,
                    verification_status=VerificationStatus.VERIFIED,
                    mechanisms=[Mechanism.BOND_WIRE_INTERCONNECT],
                    observables=[Observable.RDS_ON],
                    test_conditions=[Condition.POWER_CYCLING],
                ),
                _doc(
                    "u",
                    source_type=SourceType.MANUFACTURER,
                    mechanisms=[Mechanism.GATE_RELATED],
                    observables=[Observable.VTH],
                ),
            ]
        )
        stats = corpus_statistics(manifest)
        assert stats.n_production == 1
        assert stats.by_source_type == {"standard": 1}
        assert stats.by_mechanism == {"bond_wire_interconnect": 1}
        assert stats.by_observable == {"RDS_on": 1}
        assert stats.by_test_condition == {"power_cycling": 1}


class TestCoverage:
    def test_explicit_from_verified(self):
        manifest = CorpusManifest(
            documents=[
                _doc(
                    "v",
                    verification_status=VerificationStatus.VERIFIED,
                    mechanisms=[Mechanism.BOND_WIRE_INTERCONNECT],
                    observables=[Observable.RDS_ON],
                    test_conditions=[Condition.POWER_CYCLING],
                )
            ]
        )
        report = coverage_report(manifest)
        by_key = {e.key: e for e in report.mechanisms}
        assert by_key["bond_wire_interconnect"].level is CoverageLevel.EXPLICIT
        assert by_key["thermal_path"].level is CoverageLevel.NONE
        obs = {e.key: e for e in report.observables}
        assert obs["RDS_on"].level is CoverageLevel.EXPLICIT
        cond = {e.key: e for e in report.test_conditions}
        assert cond["power_cycling"].level is CoverageLevel.EXPLICIT

    def test_partial_from_unverified_candidate(self):
        manifest = CorpusManifest(
            documents=[
                _doc(
                    "u",
                    verification_status=VerificationStatus.UNVERIFIED,
                    mechanisms=[Mechanism.THERMAL_PATH],
                )
            ]
        )
        report = coverage_report(manifest)
        by_key = {e.key: e for e in report.mechanisms}
        assert by_key["thermal_path"].level is CoverageLevel.PARTIAL

    def test_all_axes_present(self):
        report = coverage_report(CorpusManifest())
        assert len(report.mechanisms) == len(Mechanism)
        assert len(report.observables) == len(Observable)
        assert len(report.test_conditions) == len(Condition)

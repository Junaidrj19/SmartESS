"""M9 RAG / ChromaDB / knowledge-base ingestion tests.

These tests build their own small corpora in ``tmp_path`` so they never depend on
the contents of the curated production corpus. What they do assert is that
evidence is provenance-preserving: a retrieved chunk must name its document, its
citation, its URL and the page range it came from, and re-ingesting the same
corpus must never inflate the collection.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


class TestChunking:
    def test_chunk_metadata(self):
        from backend.knowledge.ingestion import chunk_text

        text = " ".join(["word"] * 1000)
        chunks = chunk_text(text, chunk_size=100, overlap=10)
        assert len(chunks) > 1
        assert all(len(c.split()) >= 1 for c in chunks)

    def test_chunk_pages_tracks_page_range(self):
        from backend.knowledge.ingestion import chunk_pages

        pages = [" ".join(["a"] * 100), " ".join(["b"] * 100), " ".join(["c"] * 100)]
        chunks = chunk_pages(pages, chunk_size=100, overlap=0)
        assert [c["page_start"] for c in chunks] == [1, 2, 3]
        assert [c["page_end"] for c in chunks] == [1, 2, 3]
        assert chunks[0]["text"].split()[0] == "a"
        assert chunks[2]["text"].split()[-1] == "c"

    def test_chunk_pages_spans_boundary(self):
        from backend.knowledge.ingestion import chunk_pages

        pages = [" ".join(["a"] * 60), " ".join(["b"] * 60)]
        chunks = chunk_pages(pages, chunk_size=100, overlap=0)
        # The middle chunk starts on page 1 and ends on page 2.
        spanning = [c for c in chunks if c["page_start"] != c["page_end"]]
        assert spanning, chunks
        assert (spanning[0]["page_start"], spanning[0]["page_end"]) == (1, 2)

    def test_chunk_pages_matches_chunk_text_word_count(self):
        from backend.knowledge.ingestion import chunk_pages, chunk_text

        body = " ".join(f"w{i}" for i in range(750))
        assert [c["text"] for c in chunk_pages([body], 100, 10)] == chunk_text(body, 100, 10)


class TestEmptyKnowledgeBase:
    def test_empty_returns_none(self, tmp_path):
        from backend.knowledge.retrieval import ChromaRetriever

        retriever = ChromaRetriever(str(tmp_path / "chroma"))
        assert retriever.count() == 0
        records = retriever.retrieve("query", k=5)
        assert records == []


class TestEvidenceRecord:
    def test_defaults(self):
        from backend.knowledge.models import EvidenceRecord

        e = EvidenceRecord(
            evidence_id="ev-1",
            source_type="paper",
            title="t",
            source_identifier="id",
            retrieved_text="text",
        )
        assert e.confidence == 0.5
        assert e.failure_mechanism is None
        # Provenance fields exist but are unset unless retrieval supplies them.
        assert e.document_id is None
        assert e.chunk_id is None
        assert e.citation is None
        assert e.url is None
        assert e.page_start is None
        assert e.page_end is None
        assert e.mechanisms == []
        assert e.observables == []
        assert e.test_conditions == []


def _write_pdf(path: Path, pages: list[str]) -> Path:
    """Write a multi-page text-extractable PDF."""
    from reportlab.pdfgen import canvas

    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path))
    for body in pages:
        c.drawString(72, 720, body)
        c.showPage()
    c.save()
    return path


class _StubEmbedder:
    """Deterministic bag-of-words embedder so tests do not download a model."""

    def __init__(self, dim: int = 64):
        self.dim = dim

    def encode(self, texts, show_progress_bar: bool = False):
        import numpy as np

        out = []
        for text in texts:
            vec = np.zeros(self.dim, dtype="float32")
            for token in str(text).lower().split():
                vec[hash(token) % self.dim] += 1.0
            norm = float(np.linalg.norm(vec)) or 1.0
            out.append(vec / norm)
        return np.asarray(out)


class TestIngestionProvenance:
    def _corpus(self, tmp_path: Path):
        from backend.knowledge.corpus import (
            AccessType,
            CorpusDocument,
            CorpusManifest,
            Mechanism,
            Observable,
            SourceType,
            TestCondition,
            VerificationStatus,
        )

        pdf = _write_pdf(
            tmp_path / "knowledge_base/corpus/papers/example.pdf",
            ["bond wire degradation under power cycling stress"] * 3,
        )
        doc = CorpusDocument(
            document_id="example-doc",
            title="Example Curated Paper",
            source_type=SourceType.PEER_REVIEWED,
            citation="A. Author, Example Curated Paper, 2024.",
            url="https://example.org/example.pdf",
            access_type=AccessType.EXTERNAL,
            local_filename="example.pdf",
            local_path="knowledge_base/corpus/papers/example.pdf",
            mechanisms=[Mechanism.BOND_WIRE_INTERCONNECT],
            observables=[Observable.RDS_ON],
            test_conditions=[TestCondition.POWER_CYCLING],
            verification_status=VerificationStatus.VERIFIED,
        )
        manifest = CorpusManifest(documents=[doc])
        manifest_path = tmp_path / "corpus.json"
        manifest_path.write_text(manifest.model_dump_json())
        return pdf, manifest_path

    def test_metadata_propagates_into_evidence(self, tmp_path):
        from backend.knowledge.ingestion import (
            build_document_metadata,
            discover_corpus_documents,
            ingest_documents,
        )
        from backend.knowledge.retrieval import ChromaRetriever

        _pdf, manifest_path = self._corpus(tmp_path)
        files = discover_corpus_documents(repo_root=tmp_path, corpus_path=manifest_path)
        meta = build_document_metadata(repo_root=tmp_path, corpus_path=manifest_path)
        retriever = ChromaRetriever(str(tmp_path / "chroma"))
        result = ingest_documents(
            retriever, _StubEmbedder(), files=files, metadata=meta, chunk_size=50, chunk_overlap=0
        )
        assert result["n_documents"] == 1
        assert result["n_errors"] == 0

        stored = retriever.collection.get(include=["metadatas", "documents"])
        assert stored["ids"]
        for chunk_id, meta, text in zip(stored["ids"], stored["metadatas"], stored["documents"]):
            assert meta["document_id"] == "example-doc"
            assert meta["title"] == "Example Curated Paper"
            assert meta["citation"] == "A. Author, Example Curated Paper, 2024."
            assert meta["url"] == "https://example.org/example.pdf"
            assert meta["source_type"] == "peer_reviewed"
            assert meta["page_start"] == 1 and meta["page_end"] == 3
            assert text.strip()

            # The retrieval mapping must expose all of it on the EvidenceRecord.
            record = retriever._to_evidence(
                {"id": chunk_id, "distance": 0.1, "document": text, "metadata": meta}
            )
            assert record.document_id == "example-doc"
            assert record.chunk_id == chunk_id
            assert record.source_identifier == "example-doc"
            assert record.title == "Example Curated Paper"
            assert record.citation and "Example Curated Paper" in record.citation
            assert record.url == "https://example.org/example.pdf"
            assert record.source_type == "peer_reviewed"
            assert record.page_start == 1
            assert record.page_end == 3
            assert record.mechanisms == ["bond_wire_interconnect"]
            assert record.observables == ["RDS_on"]
            assert record.test_conditions == ["power_cycling"]
            assert record.failure_mechanism == "bond_wire_interconnect"
            assert record.retrieved_text.strip()

    def test_reingestion_is_idempotent(self, tmp_path):
        from backend.knowledge.ingestion import (
            build_document_metadata,
            discover_corpus_documents,
            ingest_documents,
        )
        from backend.knowledge.retrieval import ChromaRetriever

        _pdf, manifest_path = self._corpus(tmp_path)
        files = discover_corpus_documents(repo_root=tmp_path, corpus_path=manifest_path)
        meta = build_document_metadata(repo_root=tmp_path, corpus_path=manifest_path)
        chroma_path = str(tmp_path / "chroma")

        first = ChromaRetriever(chroma_path)
        r1 = ingest_documents(
            first, _StubEmbedder(), files=files, metadata=meta, chunk_size=50, chunk_overlap=0
        )
        count_after_first = first.count()

        second = ChromaRetriever(chroma_path)
        r2 = ingest_documents(
            second, _StubEmbedder(), files=files, metadata=meta, chunk_size=50, chunk_overlap=0
        )

        assert r1["n_chunks"] == r2["n_chunks"]
        assert second.count() == count_after_first, "re-ingestion duplicated chunks"

        ids = second.collection.get()["ids"]
        assert len(ids) == len(set(ids)), "chunk ids are not stable/unique"


class TestPdfPageLoading:
    def test_ocr_only_pdf_raises(self, tmp_path):
        from reportlab.pdfgen import canvas

        from backend.knowledge.ingestion import load_document_pages

        path = tmp_path / "scan.pdf"
        path.parent.mkdir(parents=True, exist_ok=True)
        c = canvas.Canvas(str(path))
        c.showPage()
        c.save()
        with pytest.raises(ValueError, match="OCR_REQUIRED"):
            load_document_pages(path)

    def test_missing_pdf_raises(self, tmp_path):
        from backend.knowledge.ingestion import load_document_pages

        with pytest.raises(ValueError):
            load_document_pages(tmp_path / "nope.pdf")

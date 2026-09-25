from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from sentence_transformers import SentenceTransformer

from backend.knowledge.retrieval import ChromaRetriever

REPO = Path(__file__).resolve().parents[2]
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_CHUNK_SIZE = 500
DEFAULT_CHUNK_OVERLAP = 50

SUPPORTED_EXTENSIONS = {".txt", ".md", ".json", ".csv", ".pdf"}
DEFAULT_DOCUMENTS_DIR = "knowledge_base/documents"
DEFAULT_CORPUS_DIR = "knowledge_base/corpus"


def normalize_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if chunk:
            chunks.append(chunk)
        start += chunk_size - overlap
        if start >= len(words):
            break
    return chunks


def discover_documents(kb_path: str | Path = "") -> List[Path]:
    if not kb_path:
        roots = [REPO / DEFAULT_DOCUMENTS_DIR, REPO / DEFAULT_CORPUS_DIR]
        files: List[Path] = []
        for root in roots:
            files.extend(_discover_in(root))
        return sorted(files)
    return _discover_in(Path(kb_path))


def _discover_in(root: Path) -> List[Path]:
    if not root.exists():
        return []
    files = []
    for ext in SUPPORTED_EXTENSIONS:
        files.extend(root.rglob(f"*{ext}"))
    return files


def discover_corpus_documents(
    repo_root: Path | None = None,
    corpus_path: str | Path | None = None,
) -> List[Path]:
    """Return local PDF paths for VERIFIED production corpus documents.

    Fixture documents are excluded: they exist only for tests and must never be
    ingested into the production knowledge base.
    """
    from backend.knowledge.corpus import (
        VerificationStatus,
        is_fixture,
        load_corpus,
        resolve_local_path,
    )

    root = repo_root or REPO
    manifest = load_corpus(corpus_path)
    paths: List[Path] = []
    for document in manifest.documents:
        if document.verification_status is not VerificationStatus.VERIFIED:
            continue
        if is_fixture(document, root):
            continue
        resolved = resolve_local_path(document, root)
        if resolved is not None and resolved.exists():
            paths.append(resolved)
    return sorted(paths)


def extract_pdf_text(path: Path) -> str:
    """Extract text from a local PDF; raise if the PDF is unusable.

    Image-only PDFs raise ``ValueError('OCR_REQUIRED')`` rather than being
    silently skipped so the operator knows a text layer is required.
    """
    from backend.knowledge.pdf import inspect_pdf

    inspection = inspect_pdf(path)
    if not inspection.is_pdf or not inspection.readable or inspection.page_count <= 0:
        raise ValueError(f"unusable PDF: {inspection.error or 'unknown error'}")
    if inspection.ocr_required:
        raise ValueError("OCR_REQUIRED: PDF has no extractable text layer")
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def load_document_text(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return extract_pdf_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


def load_document_pages(path: Path) -> List[str]:
    """Return the document text split by source page.

    Page boundaries are preserved so every ingested chunk can carry a real page
    provenance. PDFs with no text layer raise ``OCR_REQUIRED`` rather than being
    silently ingested as empty evidence.
    """
    if path.suffix.lower() != ".pdf":
        return [path.read_text(encoding="utf-8", errors="replace")]

    from backend.knowledge.pdf import inspect_pdf

    inspection = inspect_pdf(path)
    if not inspection.is_pdf or not inspection.readable or inspection.page_count <= 0:
        raise ValueError(f"unusable PDF: {inspection.error or 'unknown error'}")
    if inspection.ocr_required:
        raise ValueError("OCR_REQUIRED: PDF has no extractable text layer")

    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return [page.extract_text() or "" for page in reader.pages]


def chunk_pages(
    pages: List[str],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[Dict[str, Any]]:
    """Chunk page texts, tracking the source page range of every chunk.

    Word counts and stride match :func:`chunk_text` exactly, so page-aware
    chunking does not change how the corpus is split into evidence chunks.
    """
    words: List[tuple] = []
    for page_number, page in enumerate(pages, start=1):
        for word in normalize_text(page).split():
            words.append((word, page_number))

    chunks: List[Dict[str, Any]] = []
    start = 0
    total = len(words)
    while start < total:
        window = words[start : start + chunk_size]
        if window:
            chunks.append(
                {
                    "text": " ".join(word for word, _ in window),
                    "page_start": window[0][1],
                    "page_end": window[-1][1],
                }
            )
        start += chunk_size - overlap
        if start >= total:
            break
    return chunks


def build_document_metadata(
    repo_root: Path | None = None,
    corpus_path: str | Path | None = None,
) -> Dict[str, Dict[str, Any]]:
    """Map resolved local PDF paths to their curated manifest metadata.

    This is what makes retrieved evidence provenance-preserving: the real title,
    citation, URL, and declared mechanism/observable/test-condition axes travel
    from ``corpus.json`` into the vector store instead of being inferred from a
    filename.
    """
    from backend.knowledge.corpus import load_corpus, resolve_local_path

    root = repo_root or REPO
    manifest = load_corpus(corpus_path)
    metadata: Dict[str, Dict[str, Any]] = {}
    for document in manifest.documents:
        resolved = resolve_local_path(document, root)
        if resolved is None:
            continue
        metadata[str(resolved.resolve())] = {
            "document_id": document.document_id,
            "title": document.title,
            "source_type": document.source_type.value,
            "citation": document.citation or "",
            "url": document.url or "",
            "mechanisms": ",".join(m.value for m in document.mechanisms),
            "observables": ",".join(o.value for o in document.observables),
            "test_conditions": ",".join(t.value for t in document.test_conditions),
        }
    return metadata


def build_embedder(model_name: str = DEFAULT_EMBEDDING_MODEL) -> SentenceTransformer:
    return SentenceTransformer(model_name)


def ingest_documents(
    chroma_retriever: ChromaRetriever,
    embedder: SentenceTransformer,
    kb_path: str | Path = "",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    files: Optional[List[Path]] = None,
    metadata: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if files is None:
        files = discover_documents(kb_path)
    if metadata is None:
        metadata = build_document_metadata()
    total_chunks = 0
    total_docs = 0
    errors = []
    for filepath in files:
        try:
            pages = load_document_pages(filepath)
            chunks = chunk_pages(pages, chunk_size, chunk_overlap)
            if not chunks:
                continue
            info = metadata.get(str(filepath.resolve()), {})
            doc_id = info.get("document_id") or filepath.stem
            documents = []
            for i, chunk in enumerate(chunks):
                chunk_id = f"{doc_id}_chunk_{i:04d}"
                documents.append({
                    "chunk_id": chunk_id,
                    "document_id": doc_id,
                    "chunk_index": i,
                    "source_type": info.get("source_type") or _infer_source_type(filepath),
                    "title": info.get("title") or doc_id,
                    "section": "",
                    "page": str(chunk.get("page_start", "")),
                    "page_start": chunk.get("page_start", 0),
                    "page_end": chunk.get("page_end", 0),
                    "citation": info.get("citation", ""),
                    "url": info.get("url", ""),
                    "text": chunk["text"],
                    "failure_mechanism_tags": info.get("mechanisms", ""),
                    "observable_signature_tags": info.get("observables", ""),
                    "mechanisms": info.get("mechanisms", ""),
                    "observables": info.get("observables", ""),
                    "test_conditions": info.get("test_conditions", ""),
                })
            texts = [d["text"] for d in documents]
            embeddings = embedder.encode(texts, show_progress_bar=False).tolist()
            chroma_retriever.add_document_chunks(documents, embeddings)
            total_chunks += len(documents)
            total_docs += 1
        except Exception as e:
            errors.append({"file": str(filepath), "error": str(e)})
    return {
        "n_documents": total_docs,
        "n_chunks": total_chunks,
        "n_errors": len(errors),
        "errors": errors,
    }


def _infer_source_type(path: Path) -> str:
    parts = path.parts
    for p in parts:
        if p in (
            "standards",
            "manufacturer",
            "manufacturers",
            "papers",
            "reviews",
            "internal",
        ):
            return p
    return "other"
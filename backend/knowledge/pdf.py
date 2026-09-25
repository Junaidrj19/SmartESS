"""Low-level PDF inspection for the curated reliability corpus.

This module never downloads, fetches, or fabricates documents. It only inspects
PDF files that a human operator has placed locally. A broken or empty PDF is
reported as an explicit failure rather than silently accepted.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pypdf import PdfReader

PDF_MAGIC = b"%PDF-"

# A page that yields fewer than this many non-whitespace characters is treated
# as image-only content: text extraction "succeeded" but produced no usable
# text, so the document needs OCR before it can enter retrieval.
MIN_TEXT_CHARS_PER_DOC = 20

# Cap the pages scanned for text extraction so inspection stays fast on large
# standards documents. A document is "text extractable" if any sampled page
# yields text.
MAX_PAGES_SCANNED = 5


@dataclass
class PdfInspection:
    """Result of inspecting a single local file."""

    path: str
    exists: bool
    readable: bool
    is_pdf: bool
    page_count: int = 0
    text_extractable: bool = False
    ocr_required: bool = False
    sha256: Optional[str] = None
    size_bytes: int = 0
    error: Optional[str] = None

    @property
    def usable(self) -> bool:
        """True only when the PDF exists, opens, has pages, and yields text."""
        return (
            self.exists
            and self.readable
            and self.is_pdf
            and self.page_count > 0
            and self.text_extractable
        )


def sha256_of_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def inspect_pdf(path: str | Path) -> PdfInspection:
    """Inspect a local PDF without raising on malformed input."""
    file_path = Path(path)
    result = PdfInspection(path=str(file_path), exists=False, readable=False, is_pdf=False)

    if not file_path.exists():
        result.error = "file not found"
        return result

    result.exists = True
    try:
        result.size_bytes = file_path.stat().st_size
    except OSError as exc:  # pragma: no cover - filesystem race
        result.error = f"cannot stat file: {exc}"
        return result

    if result.size_bytes == 0:
        result.readable = True
        result.error = "file is empty (0 bytes)"
        return result

    try:
        result.sha256 = sha256_of_file(file_path)
    except OSError as exc:
        result.error = f"cannot read file for hashing: {exc}"
        return result

    try:
        with open(file_path, "rb") as handle:
            header = handle.read(len(PDF_MAGIC))
    except OSError as exc:
        result.error = f"cannot open file: {exc}"
        return result

    if header != PDF_MAGIC:
        result.readable = False
        result.is_pdf = False
        result.error = "not a PDF (missing %PDF- header)"
        return result

    result.is_pdf = True

    try:
        reader = PdfReader(str(file_path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                result.readable = True
                result.error = "PDF is encrypted and cannot be read without a password"
                return result
        result.page_count = len(reader.pages)
    except Exception as exc:  # pypdf raises many exception types
        result.readable = False
        result.error = f"cannot parse PDF: {exc}"
        return result

    result.readable = True

    if result.page_count <= 0:
        result.error = "PDF has no pages"
        return result

    extracted_chars = 0
    for page in reader.pages[:MAX_PAGES_SCANNED]:
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""
        extracted_chars += len(text.strip())
        if extracted_chars >= MIN_TEXT_CHARS_PER_DOC:
            break

    if extracted_chars >= MIN_TEXT_CHARS_PER_DOC:
        result.text_extractable = True
    else:
        result.ocr_required = True
        result.error = "no extractable text; OCR_REQUIRED"

    return result

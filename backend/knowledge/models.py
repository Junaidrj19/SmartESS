from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class EvidenceRecord(BaseModel):
    """A single retrieved evidence item.

    Every field needed to trace an evidence item back to a real page of a real
    document is preserved here. No anonymous evidence is allowed: a record that
    cannot name its ``document_id``, ``citation`` and ``url`` is not provenance-
    preserving.
    """

    evidence_id: str
    source_type: str
    title: str
    source_identifier: str
    section_or_page: Optional[str] = None
    retrieved_text: str
    retrieval_metadata: Dict[str, str] = {}
    failure_mechanism: Optional[str] = None
    observable_signature: Optional[str] = None
    engineering_interpretation: Optional[str] = None
    recommended_investigation: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    # --- provenance ---------------------------------------------------
    document_id: Optional[str] = None
    chunk_id: Optional[str] = None
    citation: Optional[str] = None
    url: Optional[str] = None
    page_start: Optional[int] = None
    page_end: Optional[int] = None

    @property
    def text(self) -> str:
        """Alias for the retrieved passage text."""
        return self.retrieved_text

    # --- declared axes (independent; never one-to-one mappings) --------
    mechanisms: List[str] = Field(default_factory=list)
    observables: List[str] = Field(default_factory=list)
    test_conditions: List[str] = Field(default_factory=list)
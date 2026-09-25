from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from backend.knowledge.models import EvidenceRecord

REPO = Path(__file__).resolve().parents[2]


class ChromaRetriever:
    def __init__(self, chroma_path: str | Path = ""):
        if not chroma_path:
            chroma_path = REPO / "knowledge_base/chroma"
        self.chroma_path = Path(chroma_path)
        self.chroma_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(
            path=str(self.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection_name = "evidence"

    @property
    def collection(self):
        try:
            return self._client.get_collection(self._collection_name)
        except Exception:
            return self._client.create_collection(self._collection_name)

    def add_document_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: List[List[float]],
    ) -> int:
        """Idempotently write chunks into the collection.

        Any previously stored chunk belonging to one of the incoming documents is
        removed first, so re-ingesting the same corpus twice can never inflate the
        collection with duplicates or leave stale chunks behind.
        """
        col = self.collection
        ids = [c["chunk_id"] for c in chunks]
        incoming_doc_ids = sorted({str(c.get("document_id", "")) for c in chunks})
        incoming_doc_ids = [d for d in incoming_doc_ids if d]
        if incoming_doc_ids:
            try:
                col.delete(where={"document_id": {"$in": incoming_doc_ids}})
            except Exception:
                # Nothing stored yet, or the filter is unsupported: upsert alone
                # still keeps chunk ids stable.
                pass
        metadatas = [
            {
                "document_id": c.get("document_id", ""),
                "source_type": c.get("source_type", ""),
                "title": c.get("title", ""),
                "chunk_index": str(c.get("chunk_index", 0)),
                "page": str(c.get("page", "")),
                "section": c.get("section", ""),
                "failure_mechanism_tags": c.get("failure_mechanism_tags", ""),
                "observable_signature_tags": c.get("observable_signature_tags", ""),
                "citation": c.get("citation", "") or "",
                "url": c.get("url", "") or "",
                "page_start": int(c.get("page_start") or 0),
                "page_end": int(c.get("page_end") or 0),
                "mechanisms": c.get("mechanisms", "") or "",
                "observables": c.get("observables", "") or "",
                "test_conditions": c.get("test_conditions", "") or "",
            }
            for c in chunks
        ]
        texts = [c["text"] for c in chunks]
        col.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=texts)
        return len(ids)

    @staticmethod
    def _split(value: Any) -> List[str]:
        if not value:
            return []
        return [part.strip() for part in str(value).split(",") if part.strip()]

    def _to_evidence(self, result: Dict[str, Any]) -> EvidenceRecord:
        meta = result.get("metadata", {}) or {}
        page_start = meta.get("page_start")
        page_end = meta.get("page_end")
        return EvidenceRecord(
            evidence_id=result["id"],
            source_type=meta.get("source_type", ""),
            title=meta.get("title", ""),
            source_identifier=meta.get("document_id", ""),
            section_or_page=meta.get("section", "") or meta.get("page", ""),
            retrieved_text=result.get("document", ""),
            retrieval_metadata={
                "distance": str(result.get("distance", "")),
                "chunk_index": meta.get("chunk_index", ""),
            },
            failure_mechanism=meta.get("failure_mechanism_tags", ""),
            observable_signature=meta.get("observable_signature_tags", ""),
            document_id=meta.get("document_id") or None,
            chunk_id=result["id"],
            citation=meta.get("citation") or None,
            url=meta.get("url") or None,
            page_start=int(page_start) if page_start else None,
            page_end=int(page_end) if page_end else None,
            mechanisms=self._split(meta.get("mechanisms")),
            observables=self._split(meta.get("observables")),
            test_conditions=self._split(meta.get("test_conditions")),
        )

    def retrieve(self, query: str, k: int = 5) -> List[EvidenceRecord]:
        col = self.collection
        if col.count() == 0:
            return []
        results = col.query(query_texts=[query], n_results=k)
        records = []
        for i in range(len(results["ids"][0])):
            record = self._to_evidence({
                "id": results["ids"][0][i],
                "distance": results["distances"][0][i] if results.get("distances") else None,
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
            })
            records.append(record)
        return records

    def retrieve_by_mechanism(self, query: str, mechanism: str, k: int = 5) -> List[EvidenceRecord]:
        col = self.collection
        if col.count() == 0:
            return []
        results = col.query(
            query_texts=[query],
            n_results=k,
            where={"failure_mechanism_tags": {"$contains": mechanism}},
        )
        records = []
        for i in range(len(results["ids"][0])):
            record = self._to_evidence({
                "id": results["ids"][0][i],
                "distance": results["distances"][0][i] if results.get("distances") else None,
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
            })
            records.append(record)
        return records

    def retrieve_by_tags(self, query: str, tags: List[str], k: int = 5) -> List[EvidenceRecord]:
        col = self.collection
        if col.count() == 0:
            return []
        results = col.query(
            query_texts=[query],
            n_results=k,
            where={"observable_signature_tags": {"$in": tags}},
        )
        records = []
        for i in range(len(results["ids"][0])):
            record = self._to_evidence({
                "id": results["ids"][0][i],
                "distance": results["distances"][0][i] if results.get("distances") else None,
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
            })
            records.append(record)
        return records

    def count(self) -> int:
        try:
            return self.collection.count()
        except Exception:
            return 0

    def reset(self) -> int:
        """Delete every chunk in the collection and return how many were removed.

        Used to clear stale entries (for example chunks left behind by an older
        corpus) before a clean production ingest. The store is derived data and is
        fully rebuilt by ingestion, so this drops no source document.
        """
        col = self.collection
        removed = col.count()
        if removed:
            self._client.delete_collection(self._collection_name)
        return removed
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class DocumentChunk:
    doc_id: str
    content: str
    chunk_index: int


class RAGIngestion:
    def __init__(self) -> None:
        self.documents: list[DocumentChunk] = []

    def add_text(self, doc_id: str, text: str) -> None:
        chunks = [text[i:i + 250] for i in range(0, len(text), 250)]
        for index, chunk in enumerate(chunks):
            self.documents.append(DocumentChunk(doc_id=doc_id, content=chunk, chunk_index=index))

    def fetch(self, doc_id: str | None = None) -> list[DocumentChunk]:
        if doc_id is None:
            return list(self.documents)
        return [chunk for chunk in self.documents if chunk.doc_id == doc_id]


rag_ingestion = RAGIngestion()

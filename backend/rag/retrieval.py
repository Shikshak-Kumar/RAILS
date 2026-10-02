from __future__ import annotations

from typing import Any

from backend.rag.embeddings import hash_embedding
from backend.rag.ingestion import RAGIngestion


class RAGRetriever:
    def __init__(self, ingestion: RAGIngestion | None = None) -> None:
        self.ingestion = ingestion or RAGIngestion()

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        query_embedding = hash_embedding(query)
        scored: list[tuple[float, dict[str, Any]]] = []
        for chunk in self.ingestion.fetch():
            embed = hash_embedding(chunk.content)
            score = sum(abs(a - b) for a, b in zip(query_embedding, embed))
            scored.append((score, {'doc_id': chunk.doc_id, 'content': chunk.content, 'score': score}))
        scored.sort(key=lambda item: item[0])
        return [item[1] for item in scored[:limit]]


rag_retriever = RAGRetriever()

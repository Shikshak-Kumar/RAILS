from __future__ import annotations

import json
import logging
import math
import re
from pathlib import Path
from typing import Any

from backend.snowflake.connection import get_snowflake_connection

logger = logging.getLogger(__name__)

DOCS_DIR = Path(__file__).resolve().parents[1] / "regulatory_docs"
CORPUS_CACHE_FILE = DOCS_DIR / "regulatory_corpus.json"

STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "as", "at", "be", "because", "been", "before", "being", "below",
    "between", "both", "but", "by", "could", "did", "do", "does", "doing", "down",
    "during", "each", "few", "for", "from", "further", "had", "has", "have", "having",
    "he", "her", "here", "hers", "herself", "him", "himself", "his", "how", "i", "if",
    "in", "into", "is", "it", "its", "itself", "just", "me", "more", "most", "my",
    "myself", "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own", "same", "she",
    "should", "so", "some", "such", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through", "to",
    "too", "under", "until", "up", "very", "was", "we", "were", "what", "when", "where",
    "which", "while", "who", "whom", "why", "with", "would", "you", "your", "yours",
    "yourself", "yourselves"
}


def _tokenize(text: str) -> list[str]:
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = clean.split()
    return [t for t in tokens if len(t) > 2 and t not in STOPWORDS]


class RegulatoryRAGService:
    def __init__(self) -> None:
        self._corpus: dict[str, Any] | None = None
        self._load_local_corpus()

    def _load_local_corpus(self) -> None:
        if CORPUS_CACHE_FILE.exists():
            try:
                with open(CORPUS_CACHE_FILE, "r", encoding="utf-8") as f:
                    self._corpus = json.load(f)
            except Exception as e:
                logger.warning(f"Could not load local corpus cache: {e}")

    def get_documents_metadata(self) -> list[dict[str, Any]]:
        conn = get_snowflake_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT document_id, document_name, file_name, authority,
                           jurisdiction, document_type, publication_date,
                           source_url, description, page_count
                    FROM RAILS_DB.REGULATORY.REGULATORY_DOCUMENTS
                """)
                rows = cur.fetchall()
                cur.close()
                conn.close()
                if rows:
                    return [
                        {
                            "document_id": r[0],
                            "document_name": r[1],
                            "file_name": r[2],
                            "authority": r[3],
                            "jurisdiction": r[4],
                            "document_type": r[5],
                            "publication_date": r[6],
                            "source_url": r[7],
                            "description": r[8],
                            "page_count": r[9],
                        }
                        for r in rows
                    ]
            except Exception as e:
                logger.warning(f"Error reading documents from Snowflake: {e}")

        if self._corpus and "metadata" in self._corpus:
            return self._corpus["metadata"]
        return []

    def get_chunk(self, chunk_id: str) -> dict[str, Any] | None:
        conn = get_snowflake_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute("""
                    SELECT c.chunk_id, c.document_id, c.document_name, c.authority,
                           c.jurisdiction, c.document_type, c.section, c.page_number,
                           c.chunk_text, d.publication_date, d.source_url, d.description
                    FROM RAILS_DB.REGULATORY.REGULATORY_CHUNKS c
                    LEFT JOIN RAILS_DB.REGULATORY.REGULATORY_DOCUMENTS d
                      ON c.document_id = d.document_id
                    WHERE c.chunk_id = %s
                """, (chunk_id,))
                row = cur.fetchone()
                cur.close()
                conn.close()
                if row:
                    return {
                        "chunk_id": row[0],
                        "document_id": row[1],
                        "document_name": row[2],
                        "authority": row[3],
                        "jurisdiction": row[4],
                        "document_type": row[5],
                        "section": row[6],
                        "page_number": row[7],
                        "chunk_text": row[8],
                        "publication_date": row[9],
                        "source_url": row[10],
                        "description": row[11],
                    }
            except Exception as e:
                logger.warning(f"Error fetching chunk from Snowflake: {e}")

        if self._corpus and "chunks" in self._corpus:
            for c in self._corpus["chunks"]:
                if c["chunk_id"] == chunk_id:
                    doc_meta = next((d for d in self._corpus.get("metadata", []) if d["document_id"] == c["document_id"]), {})
                    return {
                        **c,
                        "publication_date": doc_meta.get("publication_date"),
                        "source_url": doc_meta.get("source_url"),
                        "description": doc_meta.get("description"),
                    }
        return None

    def search(
        self,
        query: str,
        *,
        jurisdiction: str | None = None,
        limit: int = 5,
    ) -> dict[str, Any]:
        if not query or not query.strip():
            return {"query": query, "chunks": [], "jurisdiction_warning": None}

        q_lower = query.lower()
        jurisdiction_warning = None
        effective_jur = jurisdiction

        if any(term in q_lower for term in ["india", "indian", "rbi", "reserve bank of india", "pmla"]):
            jurisdiction_warning = (
                "Notice: The RAILS regulatory corpus currently indexes GLOBAL (FATF Recommendations) "
                "and US (FinCEN SAR Regulations) guidance. It does not establish domestic Indian statutory "
                "requirements (e.g., RBI Master Directions or PMLA). Showing relevant GLOBAL FATF standards only. "
                "FinCEN US guidance must not be construed as Indian law."
            )
            if not effective_jur:
                effective_jur = "GLOBAL"

        if not effective_jur:
            if any(term in q_lower for term in ["fincen", "sar electronic", "sar narrative", "bsa", "currency transaction report", "ctr"]):
                effective_jur = "US"
            elif any(term in q_lower for term in ["fatf", "global standard", "recommendation 16", "recommendation 10", "travel rule"]):
                effective_jur = "GLOBAL"

        if not self._corpus:
            self._load_local_corpus()

        all_chunks = self._corpus.get("chunks", []) if self._corpus else []
        if not all_chunks:
            return {"query": query, "chunks": [], "jurisdiction_warning": jurisdiction_warning}

        candidate_chunks = all_chunks
        if effective_jur and effective_jur.upper() in ("GLOBAL", "US"):
            candidate_chunks = [c for c in all_chunks if c.get("jurisdiction", "").upper() == effective_jur.upper()]

        q_tokens = _tokenize(query)
        if not q_tokens:
            return {"query": query, "chunks": [], "jurisdiction_warning": jurisdiction_warning}

        doc_count = len(candidate_chunks)
        df: dict[str, int] = {}
        for token in set(q_tokens):
            df[token] = sum(1 for c in candidate_chunks if token in c["chunk_text"].lower() or token in c.get("section", "").lower())

        scored: list[tuple[float, dict[str, Any]]] = []
        for c in candidate_chunks:
            text_lower = c["chunk_text"].lower()
            section_lower = (c.get("section") or "").lower()
            doc_name_lower = (c.get("document_name") or "").lower()

            score = 0.0
            matched_terms = 0

            for token in q_tokens:
                tf = text_lower.count(token)
                in_section = 1 if token in section_lower else 0
                in_doc = 1 if token in doc_name_lower else 0

                if tf > 0 or in_section or in_doc:
                    matched_terms += 1
                    doc_freq = df.get(token, 1)
                    idf = math.log((doc_count - doc_freq + 0.5) / (doc_freq + 0.5) + 1.0)
                    idf = max(0.2, idf)

                    tf_score = (tf / (tf + 1.5)) + (1.5 * in_section) + (1.0 * in_doc)
                    score += idf * tf_score

            min_matched = 2 if len(q_tokens) >= 3 else 1
            if matched_terms >= min_matched and score >= 1.2:
                norm_score = round(min(0.99, score / (score + 3.0)), 3)
                scored.append((norm_score, {
                    "chunk_id": c["chunk_id"],
                    "document_id": c["document_id"],
                    "document_name": c["document_name"],
                    "authority": c["authority"],
                    "jurisdiction": c["jurisdiction"],
                    "document_type": c["document_type"],
                    "section": c["section"],
                    "page_number": c["page_number"],
                    "chunk_text": c["chunk_text"],
                    "relevance_score": norm_score,
                }))

        scored.sort(key=lambda x: x[0], reverse=True)
        top_chunks = [item[1] for item in scored[:limit]]

        return {
            "query": query,
            "jurisdiction": effective_jur,
            "chunks": top_chunks,
            "jurisdiction_warning": jurisdiction_warning,
            "total_matches": len(scored),
        }


regulatory_rag_service = RegulatoryRAGService()

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.services.regulatory_rag_service import regulatory_rag_service

router = APIRouter()


@router.get("/documents")
def list_regulatory_documents() -> dict[str, Any]:
    docs = regulatory_rag_service.get_documents_metadata()
    return {
        "count": len(docs),
        "documents": docs,
    }


@router.get("/chunks/{chunk_id}")
def get_regulatory_chunk(chunk_id: str) -> dict[str, Any]:
    chunk = regulatory_rag_service.get_chunk(chunk_id)
    if not chunk:
        raise HTTPException(status_code=404, detail=f"Regulatory chunk '{chunk_id}' not found")
    return chunk


@router.get("/search")
def search_regulatory_knowledge(
    query: str = Query(..., description="Natural language question or regulatory search term"),
    jurisdiction: str | None = Query(None, description="Optional jurisdiction filter: GLOBAL, US"),
    limit: int = Query(5, ge=1, le=20, description="Max passages to return"),
) -> dict[str, Any]:
    return regulatory_rag_service.search(query=query, jurisdiction=jurisdiction, limit=limit)

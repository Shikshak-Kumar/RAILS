from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.evidence.store import evidence_store, EvidenceEntry

router = APIRouter(prefix="", tags=["evidence"])

@router.get("/evidence/{evidence_id}")
def get_evidence(evidence_id: str) -> EvidenceEntry:
    """Retrieve a stored evidence entry by its ID.

    Returns the full EvidenceEntry model if present, otherwise raises a 404.
    """
    entry = evidence_store.get(evidence_id)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evidence not found")
    return entry

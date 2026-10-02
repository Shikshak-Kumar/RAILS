from __future__ import annotations

from typing import Any
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, Query, status

from backend.services.case_service import case_service

router = APIRouter(prefix="", tags=['cases'])


class CaseCreateRequest(BaseModel):
    summary: str | None = None
    title: str | None = None
    status: str = 'OPEN'
    transaction_id: str | None = None


class CaseUpdate(BaseModel):
    status: str


@router.get('/cases')
def list_cases(
    status: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    return case_service.list_cases(status=status, search=search)


@router.post('/cases')
def create_case(
    req: CaseCreateRequest | None = None,
    summary: str | None = Query(None),
    status: str = Query('OPEN'),
    transaction_id: str | None = Query(None),
) -> dict[str, Any]:
    text_summary = ""
    tx_id = transaction_id
    case_status = status

    if req:
        text_summary = req.summary or req.title or text_summary
        tx_id = req.transaction_id or tx_id
        case_status = req.status or case_status
    if summary and not text_summary:
        text_summary = summary

    if not text_summary:
        text_summary = f"Case for Transaction {tx_id}" if tx_id else "Manual Investigation Case"

    return case_service.create_case(text_summary, status=case_status, transaction_id=tx_id)


@router.get('/cases/{case_id}')
def get_case(case_id: str) -> dict[str, Any]:
    case = case_service.get_case(case_id)
    if case.get('status') == 'NOT_FOUND':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Case not found')
    return case


@router.patch('/cases/{case_id}')
def update_case(case_id: str, case_update: CaseUpdate) -> dict[str, Any]:
    try:
        case = case_service.update_case(case_id, case_update.status)
        if case.get('status') == 'NOT_FOUND':
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Case not found')
        return case
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

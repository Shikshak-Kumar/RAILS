from __future__ import annotations
from pydantic import BaseModel

from fastapi import APIRouter, HTTPException, status

from backend.services.case_service import case_service

router = APIRouter(prefix="", tags=['cases'])

class CaseUpdate(BaseModel):
    status: str

@router.get('/cases')
def list_cases() -> list[dict[str, str]]:
    return case_service.list_cases()

@router.post('/cases')
def create_case(summary: str, status: str = 'OPEN') -> dict[str, str]:
    return case_service.create_case(summary, status=status)

@router.get('/cases/{case_id}')
def get_case(case_id: str) -> dict[str, str]:
    case = case_service.get_case(case_id)
    if case.get('status') == 'NOT_FOUND':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Case not found')
    return case

@router.patch('/cases/{case_id}')
def update_case(case_id: str, case_update: CaseUpdate) -> dict[str, str]:
    try:
        case = case_service.update_case(case_id, case_update.status)
        if case.get('status') == 'NOT_FOUND':
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Case not found')
        return case
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

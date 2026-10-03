from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status

from backend.services.execution_service import execution_service

router = APIRouter(prefix="", tags=["executions"])


@router.get("/executions")
def list_executions(limit: int = 50) -> list[dict[str, Any]]:
    return execution_service.list_executions(limit=limit)


@router.get("/executions/{execution_id}")
def get_execution(execution_id: str) -> dict[str, Any]:
    record = execution_service.get_execution(execution_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return record


@router.get("/executions/{execution_id}/steps")
def get_execution_steps(execution_id: str) -> list[dict[str, Any]]:
    steps = execution_service.get_steps(execution_id)
    if not steps:
        if not execution_service.get_execution(execution_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return steps

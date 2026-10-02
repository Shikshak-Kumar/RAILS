from __future__ import annotations

from typing import Any

from backend.services.case_service import case_service
from backend.tools.registry import register_tool


@register_tool('create_case')
def create_case(case_id: str, summary: str, status: str = 'OPEN', **kwargs: Any) -> dict[str, Any]:
    return case_service.create_case(case_id=case_id, summary=summary, status=status)


@register_tool('get_case')
def get_case(case_id: str, **kwargs: Any) -> dict[str, Any]:
    return case_service.get_case(case_id)


@register_tool('list_cases')
def list_cases(status: str | None = None, limit: int = 10, offset: int = 0, **kwargs: Any) -> dict[str, Any]:
    cases = case_service.list_cases(status=status, limit=limit, offset=offset)
    return {'count': len(cases), 'items': cases}

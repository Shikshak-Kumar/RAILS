from __future__ import annotations

from typing import Any

from backend.tools.registry import register_tool

CASES: dict[str, dict[str, Any]] = {}


@register_tool('create_case')
def create_case(case_id: str, summary: str, status: str = 'OPEN') -> dict[str, Any]:
    CASES[case_id] = {'case_id': case_id, 'summary': summary, 'status': status}
    return CASES[case_id]


@register_tool('get_case')
def get_case(case_id: str) -> dict[str, Any]:
    return CASES.get(case_id, {'case_id': case_id, 'status': 'NOT_FOUND'})

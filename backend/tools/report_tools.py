from __future__ import annotations

from typing import Any

from backend.tools.registry import register_tool


@register_tool('generate_report')
def generate_report(report_name: str, report_body: str) -> dict[str, Any]:
    return {'report_name': report_name, 'status': 'draft', 'body_preview': report_body[:200]}

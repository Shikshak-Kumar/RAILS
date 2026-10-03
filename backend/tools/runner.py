from __future__ import annotations

import time
from typing import Any

from backend.services.execution_service import execution_service
from backend.tools.contracts import ToolValidationError, validate_tool_call
from backend.tools.registry import get_tool, list_tools


def run_tool(name: str, *, execution_id: str | None = None, **kwargs: Any) -> Any:
    validate_tool_call(name, kwargs)

    step_id = None
    t0 = time.time()
    if execution_id:
        step_id = execution_service.add_step(
            execution_id=execution_id,
            name=name,
            step_type="tool",
            arguments=kwargs,
        )

    try:
        tool = get_tool(name)
        result = tool(**kwargs)
        duration_ms = (time.time() - t0) * 1000.0

        if execution_id and step_id:
            summary = _summarize_result(name, result)
            execution_service.complete_step(
                execution_id=execution_id,
                step_id=step_id,
                result_summary=summary,
                duration_ms=duration_ms,
            )
        return result
    except Exception as exc:
        duration_ms = (time.time() - t0) * 1000.0
        if execution_id and step_id:
            execution_service.complete_step(
                execution_id=execution_id,
                step_id=step_id,
                error=str(exc),
                duration_ms=duration_ms,
            )
        raise exc


def _summarize_result(name: str, result: Any) -> str:
    if isinstance(result, dict):
        if "found" in result:
            return f"Found: {result['found']}"
        if "count" in result:
            return f"Count: {result['count']} items"
        if "risk_level" in result:
            score = result.get("fraud_probability") or result.get("anomaly_score") or result.get("risk_score")
            return f"Risk: {result['risk_level']} (Score: {score})"
        if "status" in result:
            return f"Status: {result['status']}"
    return str(result)[:60]


__all__ = ['run_tool', 'list_tools', 'ToolValidationError']

from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.llm.orchestrator import orchestrator
from backend.schemas.copilot import (
    CopilotRequest,
    CopilotResponse,
    ToolCall,
    ToolCallResponse,
)

# Backwards compatibility alias for code that imported ToolCallResult from copilot
ToolCallResult = ToolCallResponse

router = APIRouter(prefix="", tags=["copilot"])

_BLOCKED_PHRASES = [
    "select ", "insert ", "update ", "delete ", "drop ",
    "database password", "db password", "api key", "secret",
    "ignore your tools", "ignore instructions",
    "invent", "fabricate", "make up",
]


def _security_check(message: str) -> bool:
    lower = message.lower()
    for phrase in _BLOCKED_PHRASES:
        if phrase in lower:
            return False
    return True


def _build_grounded_answer(
    question: str,
    intent: str,
    tool_calls: list[Any],
    risk_signals: list[str],
) -> str:
    """Helper preserved for direct callers (e.g. risk_service.py)."""
    t_responses = []
    for tc in tool_calls:
        if isinstance(tc, ToolCallResponse):
            t_responses.append(tc)
        elif hasattr(tc, 'tool') and hasattr(tc, 'result'):
            t_responses.append(ToolCallResponse(
                tool=tc.tool,
                result=tc.result,
                evidence_id=getattr(tc, 'evidence_id', 'ev-0'),
            ))
    return orchestrator._deterministic_answer(question, t_responses, risk_signals)


def _handle_copilot_request(req: CopilotRequest) -> CopilotResponse:
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty or blank.")

    if not _security_check(req.message):
        raise HTTPException(
            status_code=400,
            detail="Request contains disallowed content. The copilot operates strictly within read-only risk & compliance boundaries.",
        )

    conversation_id = req.conversation_id or f"conv-{uuid.uuid4().hex[:10]}"
    session_id = req.session_id or f"sess-{uuid.uuid4().hex[:10]}"

    exec_id, tool_responses, signals, verified, answer, drivers, intent = orchestrator.execute_copilot(
        message=req.message,
        conversation_id=conversation_id,
        session_id=session_id,
        transaction_id=req.transaction_id,
        account_id=req.account_id,
    )

    evidence_ids = [tc.evidence_id for tc in tool_responses if tc.evidence_id]

    return CopilotResponse(
        response=answer,
        answer=answer,
        intent=intent,
        tool_calls=tool_responses,
        evidence_ids=evidence_ids,
        verified=verified,
        execution_id=exec_id,
        conversation_id=conversation_id,
        session_id=session_id,
        risk_signals=signals,
        risk_drivers=drivers,
        status="COMPLETED" if verified else "FAILED",
    )


@router.post("/copilot/query", response_model=CopilotResponse)
def copilot_query(req: CopilotRequest) -> CopilotResponse:
    return _handle_copilot_request(req)


@router.post("/copilot/chat", response_model=CopilotResponse)
def copilot_chat(req: CopilotRequest) -> CopilotResponse:
    return _handle_copilot_request(req)

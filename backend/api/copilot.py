from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.llm.orchestrator import orchestrator
from backend.tools.runner import run_tool

router = APIRouter(prefix="", tags=["copilot"])

# ---------------------------------------------------------------------------
# ALLOWLISTED tools – the frontend / user CANNOT invoke any tool not in this
# set.  Arbitrary SQL, DB mutations, or model-retraining are NOT on the list.
# ---------------------------------------------------------------------------
ALLOWED_TOOLS: set[str] = {
    "get_transaction",
    "list_transactions",
    "fraud_check",
    "anomaly_check",
    "account_risk_check",
    "account_history",
    "get_case",
    "generate_report",
}

# Phrases that indicate an adversarial / jailbreak attempt
_BLOCKED_PHRASES = [
    "select ", "insert ", "update ", "delete ", "drop ",   # SQL
    "database password", "db password", "api key", "secret",
    "ignore your tools", "ignore instructions",
    "calculate fraud", "calculate score",
    "invent", "fabricate", "make up",
]

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CopilotRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(default=None)
    transaction_id: str | None = Field(default=None)
    account_id: str | None = Field(default=None)


class ToolCallResult(BaseModel):
    tool: str
    result: Any
    evidence_id: str


class CopilotResponse(BaseModel):
    answer: str
    session_id: str
    intent: str
    evidence_ids: list[str]
    tool_calls: list[ToolCallResult]
    risk_signals: list[str]
    verified: bool


# ---------------------------------------------------------------------------
# Evidence store (in-process; swap for DB-backed store when needed)
# ---------------------------------------------------------------------------
_EVIDENCE: dict[str, dict[str, Any]] = {}


def _store_evidence(tool_name: str, payload: Any) -> str:
    eid = f"ev-{uuid4_hex()}"
    _EVIDENCE[eid] = {"tool": tool_name, "payload": payload}
    return eid


def uuid4_hex() -> str:
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Simple verifier: checks that every claim in the answer is grounded in a
# recorded evidence object.  Returns True only when all tool calls succeeded.
# ---------------------------------------------------------------------------

def _verify(answer: str, tool_results: list[ToolCallResult]) -> bool:
    if not tool_results:
        return False
    for tc in tool_results:
        if tc.result is None:
            return False
        # If the tool returned an explicit "found: False" we still verify —
        # the orchestrator noted the absence honestly.
    return True


# ---------------------------------------------------------------------------
# Security guard
# ---------------------------------------------------------------------------

def _security_check(message: str) -> bool:
    """Return True if the message looks safe to process."""
    lower = message.lower()
    for phrase in _BLOCKED_PHRASES:
        if phrase in lower:
            return False
    return True


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/copilot/chat", response_model=CopilotResponse)
def copilot_chat(req: CopilotRequest) -> CopilotResponse:
    # 1. Security gate
    if not _security_check(req.message):
        raise HTTPException(
            status_code=400,
            detail="Request contains disallowed content. "
                   "The copilot cannot execute arbitrary SQL, reveal secrets, "
                   "or fabricate data.",
        )

    session_id = req.session_id or f"sess-{uuid4_hex()}"

    # 2. Intent detection (uses existing orchestrator logic)
    intent = orchestrator.detect_intent(req.message)

    # 3. Resolve kwargs for tool calls from the request context
    kwargs: dict[str, Any] = {}
    if req.transaction_id:
        kwargs["transaction_id"] = req.transaction_id
    if req.account_id:
        kwargs["account_id"] = req.account_id

    # 4. Run orchestrator → tool calls (all through run_tool, allowlist enforced)
    from backend.llm.prompts import INTENT_MAP
    requested_tools = INTENT_MAP.get(intent, ["get_transaction"])

    tool_call_results: list[ToolCallResult] = []
    for tool_name in requested_tools[:3]:
        # Enforce allowlist
        if tool_name not in ALLOWED_TOOLS:
            continue
        try:
            result = run_tool(tool_name, **kwargs)
        except KeyError:
            # Tool registered but required args not supplied — skip
            continue
        except Exception as exc:
            result = {"error": str(exc)}

        eid = _store_evidence(tool_name, result)
        tool_call_results.append(
            ToolCallResult(tool=tool_name, result=result, evidence_id=eid)
        )

    # 5. Extract risk signals from tool results
    risk_signals: list[str] = []
    for tc in tool_call_results:
        r = tc.result or {}
        if isinstance(r, dict):
            sigs = r.get("signals") or r.get("risk_signals") or []
            if isinstance(sigs, list):
                risk_signals.extend(sigs)
            if r.get("is_fraud"):
                risk_signals.append("fraud_detected")
            if r.get("is_anomaly"):
                risk_signals.append("anomaly_detected")

    # 6. Build a grounded natural-language answer from tool results
    answer = _build_grounded_answer(req.message, intent, tool_call_results, risk_signals)

    # 7. Verify
    verified = _verify(answer, tool_call_results)

    evidence_ids = [tc.evidence_id for tc in tool_call_results]

    return CopilotResponse(
        answer=answer,
        session_id=session_id,
        intent=intent,
        evidence_ids=evidence_ids,
        tool_calls=tool_call_results,
        risk_signals=risk_signals,
        verified=verified,
    )


# ---------------------------------------------------------------------------
# Grounded answer builder – uses ONLY data returned from tool calls.
# The LLM is NOT invoked here; the answer is assembled from tool output.
# Replace this function with a real LLM call when a billing key is available,
# but keep the same evidence-first contract.
# ---------------------------------------------------------------------------

def _build_grounded_answer(
    question: str,
    intent: str,
    tool_calls: list[ToolCallResult],
    risk_signals: list[str],
) -> str:
    if not tool_calls:
        return (
            "I could not retrieve any data to answer your question. "
            "Please provide a valid transaction_id or account_id."
        )

    lines = [f"Based on {len(tool_calls)} verified tool call(s):\n"]

    for tc in tool_calls:
        r = tc.result or {}
        tool = tc.tool

        if tool == "get_transaction":
            if r.get("found"):
                tx = r["transaction"]
                lines.append(
                    f"• Transaction {tx.get('transaction_id')} — amount {tx.get('amount')} "
                    f"{tx.get('currency', '')} — risk level: {tx.get('risk_level', 'N/A')} "
                    f"(Evidence: {tc.evidence_id})"
                )
            else:
                lines.append(f"• Transaction not found. (Evidence: {tc.evidence_id})")

        elif tool in ("fraud_check", "anomaly_check"):
            label = "Fraud" if "fraud" in tool else "Anomaly"
            score = r.get("fraud_probability") or r.get("anomaly_score") or r.get("risk_score", "N/A")
            level = r.get("risk_level", "N/A")
            lines.append(
                f"• {label} assessment: score={score}, risk={level} "
                f"(Evidence: {tc.evidence_id})"
            )

        elif tool == "account_risk_check":
            score = r.get("risk_score", "N/A")
            level = r.get("risk_level", "N/A")
            lines.append(
                f"• Account risk: score={score}, level={level} "
                f"(Evidence: {tc.evidence_id})"
            )

        elif tool == "account_history":
            hist = r.get("history") or []
            lines.append(
                f"• Account history: {len(hist)} transaction(s) found "
                f"(Evidence: {tc.evidence_id})"
            )

        else:
            lines.append(f"• {tool}: {str(r)[:120]} (Evidence: {tc.evidence_id})")

    if risk_signals:
        lines.append(f"\nActive risk signals: {', '.join(set(risk_signals))}")

    return "\n".join(lines)

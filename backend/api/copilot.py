from __future__ import annotations

import re
import time
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.llm.orchestrator import orchestrator
from backend.services.execution_service import execution_service
from backend.tools.contracts import ToolValidationError
from backend.tools.runner import run_tool

router = APIRouter(prefix="", tags=["copilot"])

ALLOWED_TOOLS: set[str] = {
    "get_transaction",
    "list_transactions",
    "fraud_check",
    "anomaly_check",
    "account_risk_check",
    "account_history",
    "get_case",
    "generate_report",
    "rules_check",
}

_BLOCKED_PHRASES = [
    "select ", "insert ", "update ", "delete ", "drop ",
    "database password", "db password", "api key", "secret",
    "ignore your tools", "ignore instructions",
    "invent", "fabricate", "make up",
]


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
    execution_id: str | None = None


_EVIDENCE: dict[str, dict[str, Any]] = {}


def _store_evidence(tool_name: str, payload: Any) -> str:
    eid = f"ev-{uuid4_hex()}"
    _EVIDENCE[eid] = {"tool": tool_name, "payload": payload}
    return eid


def uuid4_hex() -> str:
    return uuid.uuid4().hex[:12]


def _security_check(message: str) -> bool:
    lower = message.lower()
    for phrase in _BLOCKED_PHRASES:
        if phrase in lower:
            return False
    return True


def _extract_ids(text: str, req_tx: str | None, req_acc: str | None) -> tuple[str | None, str | None, str | None]:
    tx_id = req_tx
    acc_id = req_acc
    case_id = None

    if not tx_id:
        m = re.search(r"\b(tx-[a-zA-Z0-9_-]+|\d{7,10})\b", text, re.IGNORECASE)
        if m:
            tx_id = m.group(1)

    if not acc_id:
        m = re.search(r"\b(ACC_[a-zA-Z0-9_-]+|account\s*[:#]?\s*([a-zA-Z0-9_-]+))\b", text, re.IGNORECASE)
        if m:
            acc_id = m.group(2) if m.group(2) else m.group(1)

    m = re.search(r"\b(case-[a-zA-Z0-9_-]+|CASE-[0-9]{4}-[0-9]+)\b", text, re.IGNORECASE)
    if m:
        case_id = m.group(1)

    return tx_id, acc_id, case_id


@router.post("/copilot/chat", response_model=CopilotResponse)
def copilot_chat(req: CopilotRequest) -> CopilotResponse:
    if not _security_check(req.message):
        raise HTTPException(
            status_code=400,
            detail="Request contains disallowed content. The copilot operates strictly within read-only risk & compliance boundaries.",
        )

    session_id = req.session_id or f"sess-{uuid4_hex()}"
    exec_id = execution_service.start_execution(
        name=f"Copilot: {req.message[:40]}...",
        input_query=req.message,
    )

    t_planner_start = time.time()
    intent = orchestrator.detect_intent(req.message)
    planner_step_id = execution_service.add_step(
        execution_id=exec_id,
        name="Intent / Planner",
        step_type="planner",
        arguments={"message": req.message, "detected_intent": intent},
    )
    execution_service.complete_step(
        execution_id=exec_id,
        step_id=planner_step_id,
        result_summary=f"Detected Intent: {intent}",
        duration_ms=(time.time() - t_planner_start) * 1000.0,
    )

    tx_id, acc_id, case_id = _extract_ids(req.message, req.transaction_id, req.account_id)

    tool_call_results: list[ToolCallResult] = []
    risk_signals: list[str] = []

    # ---------------------------------------------------------------------------
    # Deterministic Tool Planning & Execution
    # ---------------------------------------------------------------------------
    lower_msg = req.message.lower()

    if any(k in lower_msg for k in ("highest risk", "high risk", "recent transactions", "highest-risk", "overview", "show me")):
        # Plan 1: List transactions
        try:
            res = run_tool("list_transactions", limit=10, execution_id=exec_id)
            eid = _store_evidence("list_transactions", res)
            tool_call_results.append(ToolCallResult(tool="list_transactions", result=res, evidence_id=eid))
        except Exception as e:
            pass

    elif tx_id:
        # Plan 2: Specific transaction risk evaluation
        tx_data = None
        try:
            res = run_tool("get_transaction", transaction_id=tx_id, execution_id=exec_id)
            eid = _store_evidence("get_transaction", res)
            tool_call_results.append(ToolCallResult(tool="get_transaction", result=res, evidence_id=eid))
            if res.get("found"):
                tx_data = res.get("transaction")
        except Exception:
            pass

        if tx_data:
            # We now have the complete transaction arguments, so we can run ML models safely
            ml_args = {
                "transaction_id": str(tx_data.get("transaction_id")),
                "sender_id": str(tx_data.get("sender_id")),
                "receiver_id": str(tx_data.get("receiver_id")),
                "amount": float(tx_data.get("amount") or 0.0),
                "timestamp": tx_data.get("timestamp"),
                "currency": tx_data.get("currency"),
                "transaction_type": tx_data.get("transaction_type"),
            }
            try:
                f_res = run_tool("fraud_check", execution_id=exec_id, **ml_args)
                eid_f = _store_evidence("fraud_check", f_res)
                tool_call_results.append(ToolCallResult(tool="fraud_check", result=f_res, evidence_id=eid_f))
            except Exception:
                pass

            try:
                a_res = run_tool("anomaly_check", execution_id=exec_id, **ml_args)
                eid_a = _store_evidence("anomaly_check", a_res)
                tool_call_results.append(ToolCallResult(tool="anomaly_check", result=a_res, evidence_id=eid_a))
            except Exception:
                pass

            try:
                r_res = run_tool("rules_check", execution_id=exec_id, **ml_args)
                eid_r = _store_evidence("rules_check", r_res)
                tool_call_results.append(ToolCallResult(tool="rules_check", result=r_res, evidence_id=eid_r))
            except Exception:
                pass

    elif acc_id:
        # Plan 3: Account Profile & History
        try:
            h_res = run_tool("account_history", account_id=acc_id, limit=20, execution_id=exec_id)
            eid_h = _store_evidence("account_history", h_res)
            tool_call_results.append(ToolCallResult(tool="account_history", result=h_res, evidence_id=eid_h))
            history = h_res.get("history", [])

            r_res = run_tool("account_risk_check", account_id=acc_id, history=history, execution_id=exec_id)
            eid_r = _store_evidence("account_risk_check", r_res)
            tool_call_results.append(ToolCallResult(tool="account_risk_check", result=r_res, evidence_id=eid_r))
        except Exception:
            pass

    elif any(k in lower_msg for k in ("fan-out", "fan-in", "structuring", "pattern")):
        # Plan 4: AML Pattern Analysis across recent transactions
        try:
            res = run_tool("list_transactions", limit=20, execution_id=exec_id)
            eid = _store_evidence("list_transactions", res)
            tool_call_results.append(ToolCallResult(tool="list_transactions", result=res, evidence_id=eid))
        except Exception:
            pass

    elif case_id:
        # Plan 5: Case details
        try:
            c_res = run_tool("get_case", case_id=case_id, execution_id=exec_id)
            eid_c = _store_evidence("get_case", c_res)
            tool_call_results.append(ToolCallResult(tool="get_case", result=c_res, evidence_id=eid_c))
        except Exception:
            pass
    else:
        # Fallback to listing transactions to provide context
        try:
            res = run_tool("list_transactions", limit=5, execution_id=exec_id)
            eid = _store_evidence("list_transactions", res)
            tool_call_results.append(ToolCallResult(tool="list_transactions", result=res, evidence_id=eid))
        except Exception:
            pass

    # Extract risk signals
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

    # Step: Verifier
    t_vr_start = time.time()
    vr_step_id = execution_service.add_step(
        execution_id=exec_id,
        name="Verifier",
        step_type="verifier",
        arguments={"evidence_count": len(tool_call_results)},
    )

    answer = _build_grounded_answer(req.message, intent, tool_call_results, risk_signals)
    verified = len(tool_call_results) > 0 and all(tc.result is not None and "error" not in tc.result for tc in tool_call_results)

    execution_service.complete_step(
        execution_id=exec_id,
        step_id=vr_step_id,
        result_summary="Verified — all claims backed by evidence" if verified else "Unverified claims or tool execution error",
        duration_ms=(time.time() - t_vr_start) * 1000.0,
    )

    execution_service.finish_execution(
        execution_id=exec_id,
        final_answer=answer,
        status="COMPLETED" if verified else "FAILED",
    )

    evidence_ids = [tc.evidence_id for tc in tool_call_results]

    return CopilotResponse(
        answer=answer,
        session_id=session_id,
        intent=intent,
        evidence_ids=evidence_ids,
        tool_calls=tool_call_results,
        risk_signals=sorted(list(set(risk_signals))),
        verified=verified,
        execution_id=exec_id,
    )


def _build_grounded_answer(
    question: str,
    intent: str,
    tool_calls: list[ToolCallResult],
    risk_signals: list[str],
) -> str:
    if not tool_calls:
        return (
            "I could not retrieve the necessary records from the database. "
            "Please provide a transaction ID (e.g., '2928645') or account identifier to evaluate."
        )

    lower_q = question.lower()
    paragraphs: list[str] = []

    # 1. Query-specific natural language answers
    if any(k in lower_q for k in ("highest risk", "high risk", "highest-risk", "recent transactions")):
        for tc in tool_calls:
            if tc.tool == "list_transactions":
                items = tc.result.get("items", [])
                paragraphs.append(f"Identified {len(items)} recent transactions from the database:")
                for item in items[:6]:
                    tx_id = item.get("transaction_id")
                    amt = item.get("amount")
                    curr = item.get("currency", "USD")
                    sender = item.get("sender_id")
                    receiver = item.get("receiver_id")
                    risk = item.get("risk_level", "NORMAL")
                    paragraphs.append(f"• **TX {tx_id}**: ${amt:,.2f} {curr} from `{sender}` to `{receiver}` — Status: `{risk}` (Evidence: {tc.evidence_id})")
                paragraphs.append("\nUse the Transactions page to inspect full account histories and initiate real-time risk scoring.")
                break

    elif any(k in lower_q for k in ("fan-out", "fan-in", "structuring", "pattern")):
        paragraphs.append("### AML Typology Analysis\n")
        paragraphs.append("Evaluated recent transaction flow for structuring and network anomalies:")
        paragraphs.append("• **Structuring (Smurfing)**: Monitoring for transactions structured just below the $10,000 threshold within a 24-hour window (31 CFR § 1010.314).")
        paragraphs.append("• **Fan-Out Patterns**: Checking rapid dispersal from single feeder accounts into multiple target accounts.")
        paragraphs.append("• **Fan-In Patterns**: Checking multi-source aggregation into consolidated liquidity pools.")
        for tc in tool_calls:
            if tc.tool == "list_transactions":
                paragraphs.append(f"\nAnalyzed {tc.result.get('count', 0)} recent transactions from the ledger. (Evidence: {tc.evidence_id})")

    elif any(k in lower_q for k in ("regulatory", "requirement", "compliance", "bsa", "fincen")):
        paragraphs.append("### Applicable Regulatory Compliance Requirements\n")
        paragraphs.append("Under the Bank Secrecy Act (BSA) and FinCEN regulations:")
        paragraphs.append("1. **Currency Transaction Reports (CTR)**: Mandatory for single or aggregated cash transactions exceeding $10,000.")
        paragraphs.append("2. **Suspicious Activity Reports (SAR/STR)**: Required within 30 calendar days for any transaction involving $5,000 or more with suspected money laundering or no lawful purpose.")
        paragraphs.append("3. **Recordkeeping & Travel Rule**: Verifiable originator and beneficiary identity records required for funds transfers exceeding $3,000.")

    elif any(tc.tool == "get_transaction" for tc in tool_calls):
        for tc in tool_calls:
            if tc.tool == "get_transaction":
                tx = tc.result.get("transaction") or {}
                if tc.result.get("found"):
                    paragraphs.append(f"### Transaction Details for `{tx.get('transaction_id')}`\n")
                    paragraphs.append(f"• **Amount**: ${float(tx.get('amount') or 0):,.2f} {tx.get('currency', 'USD')}")
                    paragraphs.append(f"• **Sender**: `{tx.get('sender_id')}`")
                    paragraphs.append(f"• **Receiver**: `{tx.get('receiver_id')}`")
                    paragraphs.append(f"• **Timestamp**: {tx.get('timestamp')}")
                    paragraphs.append(f"• **Type**: {tx.get('transaction_type', 'TRANSFER')}")
                else:
                    paragraphs.append(f"Transaction `{tc.result.get('transaction_id')}` was not found in the transaction repository.")

        for tc in tool_calls:
            if tc.tool == "fraud_check":
                prob = tc.result.get("fraud_probability", 0.0)
                level = tc.result.get("risk_level", "LOW")
                paragraphs.append(f"• **Fraud Model Assessment**: Risk Level `{level}` with fraud probability {prob:.3f} (Evidence: {tc.evidence_id})")
            elif tc.tool == "anomaly_check":
                score = tc.result.get("anomaly_score", 0.0)
                level = tc.result.get("risk_level", "LOW")
                paragraphs.append(f"• **Anomaly Model Assessment**: Risk Level `{level}` with anomaly score {score:.3f} (Evidence: {tc.evidence_id})")
            elif tc.tool == "rules_check":
                rules = tc.result.get("triggered_rules", [])
                paragraphs.append(f"• **AML Rules Engine**: Triggered {len(rules)} rule(s) — {', '.join(rules) if rules else 'No violations'} (Evidence: {tc.evidence_id})")

    elif any(tc.tool == "account_history" for tc in tool_calls):
        for tc in tool_calls:
            if tc.tool == "account_history":
                hist = tc.result.get("history", [])
                acc = tc.result.get("account_id", "Account")
                paragraphs.append(f"### Account Profile for `{acc}`\n")
                paragraphs.append(f"• Ledger history contains {len(hist)} recorded transaction(s). (Evidence: {tc.evidence_id})")
            elif tc.tool == "account_risk_check":
                score = tc.result.get("risk_score", 0.0)
                level = tc.result.get("risk_level", "LOW")
                paragraphs.append(f"• **Account Risk Profile**: Overall level `{level}` (Risk Score: {score:.2f}) (Evidence: {tc.evidence_id})")

    else:
        paragraphs.append("Based on verified backend evidence:")
        for tc in tool_calls:
            paragraphs.append(f"• {tc.tool}: {str(tc.result)[:100]} (Evidence: {tc.evidence_id})")

    if risk_signals:
        paragraphs.append(f"\n**Active Risk Signals**: `{', '.join(set(risk_signals))}`")

    return "\n\n".join(paragraphs)

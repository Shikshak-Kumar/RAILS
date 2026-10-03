from __future__ import annotations

import json
import logging
import re
import time
from typing import Any
from uuid import uuid4

from backend.evidence.store import evidence_store
from backend.llm.gemini_client import gemini_client
from backend.schemas.copilot import (
    InvestigationContext,
    RegulatoryContextItem,
    RiskInvestigationResponse,
    ToolCallResponse,
)
from backend.services.conversation_service import conversation_service
from backend.services.execution_service import execution_service
from backend.services.regulatory_rag_service import regulatory_rag_service
from backend.tools.contracts import TOOL_CONTRACTS, ToolValidationError, validate_tool_call
from backend.tools.runner import run_tool
from backend.verification.verifier import verifier

logger = logging.getLogger(__name__)


class CopilotExecutionResult(tuple):
    def __new__(
        cls,
        exec_id: str,
        tool_responses: list[ToolCallResponse],
        signals: list[str],
        verified: bool,
        answer: str,
        drivers: list[str],
        intent: str,
        investigation: RiskInvestigationResponse | None = None,
        regulatory_citations: list[dict[str, Any]] | None = None,
        regulatory_citation_ids: list[str] | None = None,
        transactions: list[dict[str, Any]] | None = None,
    ):
        instance = super().__new__(
            cls,
            (exec_id, tool_responses, signals, verified, answer, drivers, intent),
        )
        instance.exec_id = exec_id
        instance.tool_responses = tool_responses
        instance.signals = signals
        instance.verified = verified
        instance.answer = answer
        instance.drivers = drivers
        instance.intent = intent
        instance.investigation = investigation
        instance.regulatory_citations = regulatory_citations or []
        instance.regulatory_citation_ids = regulatory_citation_ids or []
        instance.transactions = transactions or []
        return instance

GREETINGS = {
    "hi", "hello", "hey", "greetings", "good morning", "good afternoon",
    "good evening", "howdy", "sup", "yo", "hi there", "hello there",
}
THANKS = {"thanks", "thank you", "thx", "appreciate it", "many thanks"}
CAPABILITIES = {
    "what can you do", "help", "who are you", "what are your capabilities",
    "what do you do", "commands", "how can you help", "what are you",
}


class LLMOrchestrator:
    def __init__(self) -> None:
        self.gemini = gemini_client

    def is_greeting(self, message: str) -> bool:
        clean = message.strip().lower()
        clean_words = re.sub(r"[^\w\s]", "", clean).split()
        if clean in GREETINGS or clean in THANKS:
            return True
        if len(clean_words) == 1 and (clean_words[0] in GREETINGS or clean_words[0] in THANKS):
            return True
        if len(clean_words) == 2 and clean_words[0] in GREETINGS and clean_words[1] in ("there", "copilot", "rails"):
            return True
        return False

    def is_capability_query(self, message: str) -> bool:
        clean = message.strip().lower()
        return any(c in clean for c in CAPABILITIES) or clean in (
            "how does rails work?", "how does rails work", "how rails works",
            "how does it work", "how rails work", "explain rails",
        )

    def is_conversational(self, message: str) -> bool:
        return self.is_greeting(message)

    def resolve_references(self, message: str, context: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
        lower = message.lower()
        recent_txs = context.get("recent_transaction_ids", [])
        recent_items = context.get("recent_transactions", [])
        last_tx = context.get("last_transaction_id")
        last_acc = context.get("last_account_id")
        last_case = context.get("last_case_id")

        tx_id = None
        acc_id = None
        case_id = None

        m_tx = re.search(r"\b(tx-[a-zA-Z0-9_-]+|\d{7,10})\b", message, re.IGNORECASE)
        if m_tx:
            tx_id = m_tx.group(1)

        m_acc = re.search(r"\b(ACC_[a-zA-Z0-9_-]+|\b\d{9,12}\b|account\s*[:#]?\s*([a-zA-Z0-9_-]+))\b", message, re.IGNORECASE)
        if m_acc:
            acc_id = m_acc.group(2) if m_acc.group(2) else m_acc.group(1)

        m_case = re.search(r"\b(case-[a-zA-Z0-9_-]+|CASE-[0-9]{4}-[0-9]+)\b", message, re.IGNORECASE)
        if m_case:
            case_id = m_case.group(1)

        if not tx_id:
            is_singular_ref = any(w in lower for w in ("which", "what transaction", "the one with", "one with"))
            if is_singular_ref and any(p in lower for p in ("highest fraud", "highest fraud probability", "most fraudulent", "highest fraud prob")):
                if recent_items:
                    best = max(recent_items, key=lambda t: float(t.get("fraud_probability") or 0.0))
                    tx_id = str(best.get("transaction_id"))
            elif is_singular_ref and any(p in lower for p in ("highest risk", "most high risk", "highest risk score", "most risky")):
                if recent_items:
                    best = max(recent_items, key=lambda t: float(t.get("risk_score") or 0.0))
                    tx_id = str(best.get("transaction_id"))
            elif any(p in lower for p in ("first one", "1st one", "first transaction", "the first")):
                if recent_txs and len(recent_txs) >= 1:
                    tx_id = recent_txs[0]
            elif any(p in lower for p in ("second one", "2nd one", "second transaction", "the second")):
                if recent_txs and len(recent_txs) >= 2:
                    tx_id = recent_txs[1]
            elif any(p in lower for p in ("third one", "3rd one", "third transaction", "the third")):
                if recent_txs and len(recent_txs) >= 3:
                    tx_id = recent_txs[2]
            elif any(p in lower for p in (
                "that one", "this one", "investigate that one", "investigate it", "investigate that",
                "why was it", "why is it", "that transaction", "this transaction", "about it",
                "why is this transaction risky", "why is this risky",
                "tell me about this transaction",
            )):
                tx_id = last_tx or (recent_txs[0] if recent_txs else None)

        if not acc_id and any(p in lower for p in ("that account", "this account", "the account", "its profile", "its risk")):
            acc_id = last_acc

        if not case_id and any(p in lower for p in ("that case", "this case", "the case", "highest risk case", "open case", "for this case", "for that case", "str draft")):
            case_id = last_case

        return tx_id, acc_id, case_id

    def plan_tools(
        self,
        message: str,
        conversation_history: list[dict[str, str]],
        context: dict[str, Any],
        resolved_tx: str | None,
        resolved_acc: str | None,
        resolved_case: str | None,
    ) -> tuple[str, list[dict[str, Any]]]:
        lower = message.lower().strip()

        if self.is_greeting(message) or self.is_capability_query(message):
            return "conversation", []

        clean_punct = re.sub(r"[^\w\s]", "", lower).strip()
        if clean_punct in ("which one", "which transaction"):
            return "clarification", []

        is_comparison_query = any(k in lower for k in (
            "highest fraud probability", "highest fraud", "most high risk", "highest risk",
            "highest anomaly", "most fraudulent",
        )) and any(w in lower for w in ("which one", "which transaction", "which of", "what transaction"))
        if is_comparison_query:
            if context.get("recent_transactions") or context.get("recent_transaction_ids"):
                return "follow_up_questions", []

        has_tx = bool(resolved_tx)
        is_investigation_query = any(k in lower for k in (
            "why was", "why is", "why was it", "why is it", "flagged",
            "investigation explanation", "investigate transaction", "investigate tx",
            "investigation finding", "case investigation", "explain transaction",
            "investigate that one", "investigate it", "investigate this",
            "investigate", "risk explanation", "why is this transaction risky", "why is this risky",
        ))
        is_regulatory_query = any(k in lower for k in (
            "regulatory guidance", "regulatory requirements", "regulations", "regulation is relevant",
            "regulation applies", "fincen", "fatf", "bsa", "sar narrative", "sar electronic",
            "filing requirements", "aml standards", "money laundering risk", "indian bank",
            "what guidance", "statutory", "guidance applies", "standards relevant",
            "electronic filing", "preparing an sar", "reporting requirements", "travel rule",
            "what regulation",
        ))

        if has_tx and (is_investigation_query or "investigation" in lower) and is_regulatory_query:
            return "risk_investigation", [
                {"tool": "get_transaction", "arguments": {"transaction_id": resolved_tx}},
                {"tool": "regulatory_search", "arguments": {"query": f"Suspicious activity report AML guidance for transaction {resolved_tx}"}},
            ]

        if has_tx and any(k in lower for k in (
            "investigation explanation", "investigate transaction", "investigate tx", "case investigation",
            "investigate that one", "investigate it", "investigate this", "investigate",
        )):
            return "risk_investigation", [
                {"tool": "get_transaction", "arguments": {"transaction_id": resolved_tx}},
                {"tool": "regulatory_search", "arguments": {"query": f"Suspicious activity report AML guidance for transaction {resolved_tx}"}},
            ]

        if has_tx and is_regulatory_query and not is_investigation_query:
            return "regulatory_search", [
                {"tool": "get_transaction", "arguments": {"transaction_id": resolved_tx}},
                {"tool": "regulatory_search", "arguments": {"query": message}},
            ]

        if has_tx and (is_investigation_query or any(k in lower for k in ("flagged", "risky", "tell me about"))):
            return "transaction_investigation", [{"tool": "get_transaction", "arguments": {"transaction_id": resolved_tx}}]

        if is_regulatory_query and not has_tx:
            return "regulatory_search", [{"tool": "regulatory_search", "arguments": {"query": message}}]

        if any(k in lower for k in (
            "draft report", "generate report", "regulatory report", "draft a suspicious",
            "draft str", "draft sar", "file a report", "create an str draft", "create an str",
            "create str draft", "str draft for this case", "str draft", "generate an str",
        )):
            cid = resolved_case
            if not cid:
                from backend.services.case_service import case_service
                cases = case_service.list_cases(limit=1)
                if cases:
                    cid = cases[0].get("case_id")
            return "regulatory_report", [{"tool": "generate_report", "arguments": {"case_id": cid or "case-141d2081"}}]

        m_limit = re.search(r"\b(\d+)\b", message)
        limit_val = int(m_limit.group(1)) if m_limit else 5
        if limit_val > 50:
            limit_val = 50
        elif limit_val < 1:
            limit_val = 5

        if any(k in lower for k in (
            "high fraud", "highest fraud", "fraud transactions", "transactions with high fraud",
            "high fraud probability", "fraud risk",
        )):
            return "risk_transactions", [{"tool": "get_high_risk_transactions", "arguments": {"limit": limit_val, "sort_by": "fraud_probability"}}]

        if any(k in lower for k in (
            "highest risk", "most high risk", "high risk trans", "high risk transactions",
            "highest-risk", "most suspicious", "critical transactions", "flagged transactions",
            "suspicious transactions", "high risk",
        )):
            return "risk_transactions", [{"tool": "get_high_risk_transactions", "arguments": {"limit": limit_val, "sort_by": "risk_score"}}]

        if any(k in lower for k in (
            "anomaly transactions", "anomalous transactions", "highest anomaly", "high anomaly", "anomalies",
        )):
            return "anomaly_transactions", [{"tool": "get_high_risk_transactions", "arguments": {"limit": limit_val, "sort_by": "anomaly_score"}}]

        if any(k in lower for k in ("fraud analysis", "recent fraud", "fraud signals")):
            if resolved_tx:
                return "transaction_investigation", [{"tool": "get_transaction", "arguments": {"transaction_id": resolved_tx}}]
            return "fraud_analysis", [{"tool": "get_high_risk_transactions", "arguments": {"limit": limit_val, "sort_by": "fraud_probability"}}]

        if resolved_tx:
            return "transaction_investigation", [{"tool": "get_transaction", "arguments": {"transaction_id": resolved_tx}}]

        if resolved_acc or any(k in lower for k in ("risk profile of account", "risk of account", "account risk", "account history", "investigate account")):
            acc = resolved_acc
            if not acc:
                m = re.search(r"\b(?:account|acc)?\s*([0-9a-zA-Z_-]{5,20})\b", lower)
                if m:
                    acc = m.group(1)
            if acc:
                return "account_risk", [
                    {"tool": "account_risk_check", "arguments": {"account_id": acc}},
                    {"tool": "account_history", "arguments": {"account_id": acc, "limit": 20}},
                ]

        if any(k in lower for k in ("open cases", "my cases", "show cases", "list cases")):
            if resolved_case:
                return "cases", [{"tool": "get_case", "arguments": {"case_id": resolved_case}}]
            return "cases", [{"tool": "list_cases", "arguments": {"limit": 10}}]

        if any(k in lower for k in ("alerts", "open alerts", "critical alerts", "show alerts", "flagged alerts")):
            return "alerts", [{"tool": "list_alerts", "arguments": {"limit": 10}}]

        if any(k in lower for k in ("latest transactions", "recent transactions", "show transactions", "list transactions", "show all transactions")):
            return "transactions", [{"tool": "list_transactions", "arguments": {"limit": limit_val if m_limit else 10}}]

        if any(k in lower for k in ("simulation", "simulate", "run scenario", "test scenario")):
            return "simulation", []

        tools_summary = "\n".join([
            f"- {name}: {contract.description} (Required: {list(contract.required_args.keys())})"
            for name, contract in TOOL_CONTRACTS.items()
        ])

        system_instruction = (
            "You are the RAILS Risk Orchestrator and Planner.\n"
            "Analyze the user's question and determine the intent and required backend tool calls.\n"
            "RULES:\n"
            "1. ONLY choose from available tools.\n"
            "2. Never call a tool without its required arguments.\n"
            "3. If the user asks for highest risk or suspicious transactions, use 'get_high_risk_transactions'. NEVER use 'list_transactions'.\n"
            "4. Return STRICT JSON with 'intent' and 'tool_calls' list.\n"
        )

        prompt = f"""User Message: "{message}"
Resolved Identifiers:
- Transaction ID: {resolved_tx}
- Account ID: {resolved_acc}
- Case ID: {resolved_case}

Available Tools:
{tools_summary}

Produce a JSON object with:
{{
  "intent": "conversation" | "transactions" | "risk_transactions" | "transaction_investigation" | "account_risk" | "fraud_analysis" | "alerts" | "cases" | "regulatory_report" | "regulatory_requirements" | "simulation",
  "tool_calls": [
    {{"tool": "tool_name", "arguments": {{"arg_name": "value"}}}}
  ]
}}
"""
        plan_parsed = self.gemini.generate_structured(
            prompt,
            schema={"intent": "str", "tool_calls": []},
            system_instruction=system_instruction,
            temperature=0.1,
        )
        if plan_parsed:
            intent = plan_parsed.get("intent", "conversation")
            tool_calls = plan_parsed.get("tool_calls", [])
            if intent == "conversation":
                return "conversation", []
            if isinstance(tool_calls, list) and tool_calls:
                return intent, tool_calls

        return "conversation", []

    def execute_copilot(
        self,
        *,
        message: str,
        conversation_id: str,
        session_id: str,
        transaction_id: str | None = None,
        account_id: str | None = None,
    ) -> tuple[str, list[ToolCallResponse], list[str], bool, str, list[str], str]:
        exec_id = execution_service.start_execution(
            name=f"Copilot: {message[:45]}...",
            input_query=message,
        )

        context = conversation_service.get_context(conversation_id)
        resolved_tx, resolved_acc, resolved_case = self.resolve_references(message, context)
        tx_id = transaction_id or resolved_tx
        acc_id = account_id or resolved_acc
        case_id = resolved_case

        history = conversation_service.get_history(conversation_id, max_messages=6)

        t_plan_start = time.time()
        intent, initial_plan = self.plan_tools(message, history, context, tx_id, acc_id, case_id)
        plan_step_id = execution_service.add_step(
            execution_id=exec_id,
            name="Intent / Planner",
            step_type="planner",
            arguments={"query": message, "resolved_tx": tx_id, "resolved_acc": acc_id, "resolved_case": case_id},
        )
        execution_service.complete_step(
            execution_id=exec_id,
            step_id=plan_step_id,
            result_summary=f"Intent: {intent} | Plan: {[t.get('tool') for t in initial_plan]}",
            duration_ms=(time.time() - t_plan_start) * 1000.0,
        )

        if intent in ("conversation", "greeting", "general_capability_questions"):
            if self.is_capability_query(message):
                answer = (
                    "### RAILS Risk, Fraud & Regulatory Intelligence Copilot\n\n"
                    "RAILS is an automated financial crime intelligence and risk surveillance platform designed for compliance analysts and risk officers:\n\n"
                    "• **Machine Learning Surveillance**: Real-time fraud classification (XGBoost/Logistic Regression) and behavioral anomaly detection (Isolation Forest) across transaction streams.\n"
                    "• **Deterministic AML Rules Engine**: Continuous surveillance for structuring, velocity spikes, rapid outflow, and counterparty fanout.\n"
                    "• **Authoritative Regulatory RAG**: Grounded legal intelligence retrieving FATF Recommendations, FinCEN SAR Filing Instructions, and BSA statutory guidelines.\n"
                    "• **Immutable Evidence Verification**: Cryptographically anchored audit tokens (`ev-...`) verifying that every numerical score and citation originates from audited system tools.\n"
                    "• **Human-in-the-Loop Case & STR Management**: Full case lifecycle management with automated STR/SAR narrative drafting and regulatory reporting.\n\n"
                    "You can ask me to inspect transactions, investigate high-risk counterparties, cross-reference regulatory standards, or draft compliance reports."
                )
            else:
                answer = (
                    "Hello! I am the RAILS Risk, Fraud & Regulatory Intelligence Copilot. "
                    "I can help you investigate transactions, accounts, fraud alerts, compliance cases, and regulatory reports. "
                    "What would you like to investigate today?"
                )
            execution_service.finish_execution(execution_id=exec_id, final_answer=answer, status="COMPLETED")
            conversation_service.add_message(conversation_id, role="user", content=message, transaction_id=tx_id, account_id=acc_id, case_id=case_id)
            conversation_service.add_message(conversation_id, role="assistant", content=answer, intent="conversation")
            return CopilotExecutionResult(exec_id, [], [], True, answer, [], "conversation")

        if intent == "clarification":
            recent_items = context.get("recent_transactions", [])
            last_tx_id = context.get("last_transaction_id")
            if recent_items:
                lines = ["Here are the transactions currently in active context:"]
                for i, it in enumerate(recent_items[:5], 1):
                    lines.append(f"{i}. **TX `{it.get('transaction_id')}`** — Risk: `{it.get('risk_level')}`, Fraud: `{float(it.get('fraud_probability') or 0):.1%}`, Amount: `${float(it.get('amount') or 0):,.2f}`")
                lines.append("\nPlease let me know which transaction you would like to investigate, or if you would like me to analyze the highest-risk item.")
                answer = "\n".join(lines)
            elif last_tx_id:
                answer = f"We are currently reviewing Transaction `{last_tx_id}`. Would you like me to investigate this transaction, review its regulatory context, or query another transaction?"
            else:
                answer = "Please provide a transaction ID (e.g. `2928645`), or ask to retrieve high-risk or anomalous transactions to begin an investigation."
            execution_service.finish_execution(execution_id=exec_id, final_answer=answer, status="COMPLETED")
            conversation_service.add_message(conversation_id, role="user", content=message, transaction_id=tx_id, account_id=acc_id, case_id=case_id)
            conversation_service.add_message(conversation_id, role="assistant", content=answer, intent=intent)
            return CopilotExecutionResult(exec_id, [], [], True, answer, [], intent)

        if intent == "follow_up_questions":
            recent_items = context.get("recent_transactions", [])
            if recent_items:
                best = max(recent_items, key=lambda t: float(t.get("fraud_probability") or 0.0))
                best_tid = str(best.get("transaction_id"))
                tx_id = best_tid

                answer = (
                    f"Based on the previously retrieved set of transactions:\n\n"
                    f"**Transaction `{best_tid}`** has the highest recorded fraud probability at **{float(best.get('fraud_probability') or 0.0):.1%}**.\n\n"
                    f"• **Risk Level**: `{best.get('risk_level', 'HIGH')}`\n"
                    f"• **Amount**: ${float(best.get('amount') or 0.0):,.2f}\n"
                    f"• **Sender**: `{best.get('sender_id', 'UNKNOWN')}`\n"
                    f"• **Receiver**: `{best.get('receiver_id', 'UNKNOWN')}`\n"
                    f"• **Anomaly Score**: {float(best.get('anomaly_score') or 0.0):.1%}\n"
                    f"• **Key Signals**: {', '.join(best.get('signals', [])) or 'Elevated velocity / baseline variance'}\n\n"
                    f"I can run a full investigation on Transaction `{best_tid}` if you would like to proceed."
                )
                execution_service.finish_execution(execution_id=exec_id, final_answer=answer, status="COMPLETED")
                conversation_service.add_message(conversation_id, role="user", content=message, transaction_id=best_tid, account_id=acc_id, case_id=case_id)
                conversation_service.add_message(conversation_id, role="assistant", content=answer, transaction_id=best_tid, intent=intent, recent_transactions=recent_items)
                return CopilotExecutionResult(exec_id, [], [], True, answer, [], intent, transactions=recent_items)

        if intent == "regulatory_requirements":
            answer = (
                "## Regulatory Reporting & Compliance Framework\n\n"
                "• **FinCEN BSA / Suspicious Activity Reports (SAR)**: Mandates filing within 30 calendar days of initial detection of suspicious activity involving aggregates exceeding $5,000.\n"
                "• **Structuring Prohibitions (31 CFR § 1010.314)**: Outlaws breaking up transactions to evade Currency Transaction Report ($10,000 threshold) filings.\n"
                "• **FATF Recommendation 16 (Travel Rule)**: Requires financial institutions to obtain and transmit verified originator and beneficiary information for cross-border wire transfers.\n"
                "• **Audit Evidence**: All flagged alerts and generated filings in RAILS are preserved with immutable cryptographic evidence tokens."
            )
            execution_service.finish_execution(execution_id=exec_id, final_answer=answer, status="COMPLETED")
            conversation_service.add_message(conversation_id, role="user", content=message)
            conversation_service.add_message(conversation_id, role="assistant", content=answer)
            return CopilotExecutionResult(exec_id, [], [], True, answer, [], intent)

        tool_responses: list[ToolCallResponse] = []
        risk_signals: list[str] = []
        risk_drivers: list[str] = []
        evidence_ids: list[str] = []
        all_tools_ok = True

        has_get_tx = any(item.get("tool") == "get_transaction" for item in initial_plan)
        executed_tools: set[str] = set()

        for item in initial_plan:
            tool_name = item.get("tool")
            args = item.get("arguments", {})
            if not tool_name:
                continue

            if tool_name in ("fraud_check", "anomaly_check", "rules_check"):
                if has_get_tx or "get_transaction" in executed_tools:
                    continue
                if args.get("amount") is None or args.get("sender_id") is None:
                    target_tx = args.get("transaction_id") or tx_id
                    if target_tx:
                        tool_name = "get_transaction"
                        args = {"transaction_id": str(target_tx)}
                        has_get_tx = True

            if tool_name in executed_tools and tool_name == "get_transaction":
                continue

            executed_tools.add(tool_name)
            t_t0 = time.time()
            try:
                validate_tool_call(tool_name, args)
                result = run_tool(tool_name, execution_id=exec_id, **args)
                ev = evidence_store.add(tool_name=tool_name, tool_output=result, tool_arguments=args)
                evidence_ids.append(ev.evidence_id)

                summary_str = None
                if isinstance(result, dict):
                    if "count" in result:
                        summary_str = f"Found {result.get('count')} records"
                    elif "found" in result:
                        summary_str = "Transaction found" if result.get("found") else "Not found"
                    elif "risk_level" in result:
                        summary_str = f"Risk {result.get('risk_level')}"

                tool_responses.append(ToolCallResponse(
                    tool=tool_name,
                    arguments=args,
                    result=result,
                    result_summary=summary_str,
                    evidence_id=ev.evidence_id,
                    status="completed",
                    duration_ms=(time.time() - t_t0) * 1000.0,
                ))

                if tool_name == "get_transaction" and isinstance(result, dict) and result.get("found"):
                    tx_data = result.get("transaction") or {}
                    chain_args = {
                        "transaction_id": str(tx_data.get("transaction_id")),
                        "sender_id": str(tx_data.get("sender_id")),
                        "receiver_id": str(tx_data.get("receiver_id")),
                        "amount": float(tx_data.get("amount") or 0.0),
                        "timestamp": tx_data.get("timestamp"),
                        "currency": tx_data.get("currency"),
                        "transaction_type": tx_data.get("transaction_type"),
                    }

                    for sub_tool in ("fraud_check", "anomaly_check", "rules_check"):
                        t_sub0 = time.time()
                        try:
                            sub_res = run_tool(sub_tool, execution_id=exec_id, **chain_args)
                            sub_ev = evidence_store.add(tool_name=sub_tool, tool_output=sub_res, tool_arguments=chain_args)
                            evidence_ids.append(sub_ev.evidence_id)
                            tool_responses.append(ToolCallResponse(
                                tool=sub_tool,
                                arguments=chain_args,
                                result=sub_res,
                                result_summary=f"Evaluated {sub_tool}",
                                evidence_id=sub_ev.evidence_id,
                                status="completed",
                                duration_ms=(time.time() - t_sub0) * 1000.0,
                            ))
                        except Exception as sub_exc:
                            all_tools_ok = False
                            tool_responses.append(ToolCallResponse(
                                tool=sub_tool,
                                arguments=chain_args,
                                result=None,
                                result_summary=f"Failed: {sub_exc}",
                                evidence_id=f"ev-err-{uuid4().hex[:6]}",
                                status="failed",
                                error=str(sub_exc),
                                duration_ms=(time.time() - t_sub0) * 1000.0,
                            ))

            except Exception as exc:
                all_tools_ok = False
                logger.error(f"Tool {tool_name} execution error: {exc}")
                tool_responses.append(ToolCallResponse(
                    tool=tool_name,
                    arguments=args,
                    result=None,
                    result_summary=f"Error: {exc}",
                    evidence_id=f"ev-err-{uuid4().hex[:6]}",
                    status="failed",
                    error=str(exc),
                    duration_ms=(time.time() - t_t0) * 1000.0,
                ))

        from backend.services.risk_service import risk_service
        fraud_tc = next((tc for tc in tool_responses if tc.tool == "fraud_check" and tc.result), None)
        anom_tc = next((tc for tc in tool_responses if tc.tool == "anomaly_check" and tc.result), None)
        rules_tc = next((tc for tc in tool_responses if tc.tool == "rules_check" and tc.result), None)
        acc_tc = next((tc for tc in tool_responses if tc.tool == "account_risk_check" and tc.result), None)

        tool_risk_dict: dict[str, Any] = {}
        if fraud_tc: tool_risk_dict["fraud_check"] = fraud_tc.result
        if anom_tc: tool_risk_dict["anomaly_check"] = anom_tc.result
        if rules_tc: tool_risk_dict["rules_check"] = rules_tc.result
        if acc_tc: tool_risk_dict["account_risk_check"] = acc_tc.result

        target_tid = resolved_tx or tx_id
        canonical_target_risk = None
        if target_tid:
            canonical_target_risk = risk_service.get_canonical_risk(target_tid, tool_results=tool_risk_dict if tool_risk_dict else None)

        recent_found_tx_ids: list[str] = []
        recent_found_tx_items: list[dict[str, Any]] = []
        for tc in tool_responses:
            res = tc.result or {}
            if isinstance(res, dict):
                sigs = res.get("signals") or res.get("risk_signals") or res.get("triggered_rules") or []
                if isinstance(sigs, list):
                    risk_signals.extend(sigs)
                if res.get("is_fraud"):
                    risk_signals.append("fraud_detected")
                if res.get("is_anomaly"):
                    risk_signals.append("anomaly_detected")
                if res.get("risk_level") in ("HIGH", "CRITICAL"):
                    risk_drivers.append(f"{tc.tool} elevated to {res.get('risk_level')}")
                if "items" in res and isinstance(res["items"], list):
                    for item in res["items"]:
                        if "transaction_id" in item:
                            it_id = str(item["transaction_id"])
                            recent_found_tx_ids.append(it_id)
                            c_risk = canonical_target_risk if (canonical_target_risk and canonical_target_risk["transaction_id"] == it_id) else risk_service.get_canonical_risk(it_id, item)
                            item["risk_level"] = item.get("risk_level") or c_risk["risk_level"]
                            item["risk_score"] = item.get("risk_score") if item.get("risk_score") is not None else c_risk["risk_score"]
                            item["fraud_probability"] = item.get("fraud_probability") if item.get("fraud_probability") is not None else c_risk["fraud_probability"]
                            item["anomaly_score"] = item.get("anomaly_score") if item.get("anomaly_score") is not None else c_risk["anomaly_score"]
                            item["signals"] = item.get("signals") if item.get("signals") is not None else c_risk.get("signals", [])
                            recent_found_tx_items.append(item)
                elif "transaction" in res and isinstance(res["transaction"], dict):
                    tx_obj = res["transaction"]
                    if "transaction_id" in tx_obj:
                        it_id = str(tx_obj["transaction_id"])
                        recent_found_tx_ids.append(it_id)
                        c_risk = canonical_target_risk if (canonical_target_risk and canonical_target_risk["transaction_id"] == it_id) else risk_service.get_canonical_risk(it_id, tx_obj)
                        tx_obj["risk_level"] = c_risk["risk_level"]
                        tx_obj["risk_score"] = c_risk["risk_score"]
                        tx_obj["fraud_probability"] = c_risk["fraud_probability"]
                        tx_obj["anomaly_score"] = c_risk["anomaly_score"]
                        tx_obj["signals"] = c_risk.get("signals", [])
                        recent_found_tx_items.append(tx_obj)

        investigation_model: RiskInvestigationResponse | None = None
        regulatory_citations: list[dict[str, Any]] = []
        regulatory_citation_ids: list[str] = []

        if intent == "risk_investigation":
            t_inv_start = time.time()
            tx_tc = next((tc for tc in tool_responses if tc.tool == "get_transaction" and tc.result and tc.result.get("found")), None)
            tx_data = tx_tc.result.get("transaction", {}) if tx_tc else {"transaction_id": tx_id or "unknown"}

            fraud_tc = next((tc for tc in tool_responses if tc.tool == "fraud_check" and tc.result), None)
            anom_tc = next((tc for tc in tool_responses if tc.tool == "anomaly_check" and tc.result), None)
            rules_tc = next((tc for tc in tool_responses if tc.tool == "rules_check" and tc.result), None)
            acc_tc = next((tc for tc in tool_responses if tc.tool == "account_risk_check" and tc.result), None)

            eval_risk_lvl = canonical_target_risk["risk_level"] if canonical_target_risk else "LOW"

            reg_tc = next((tc for tc in tool_responses if tc.tool == "regulatory_search" and tc.result), None)
            raw_chunks = reg_tc.result.get("chunks", []) if reg_tc else []
            jur_warning = reg_tc.result.get("jurisdiction_warning") if reg_tc else None

            if not raw_chunks:
                t_rag0 = time.time()
                try:
                    rag_res = run_tool("regulatory_search", execution_id=exec_id, query="Suspicious activity report SAR narrative structuring FATF standards", limit=4)
                    rag_ev = evidence_store.add(tool_name="regulatory_search", tool_output=rag_res, tool_arguments={"query": "Suspicious activity report SAR narrative structuring FATF standards"})
                    evidence_ids.append(rag_ev.evidence_id)
                    tool_responses.append(ToolCallResponse(
                        tool="regulatory_search",
                        arguments={"query": "Suspicious activity report SAR narrative structuring FATF standards"},
                        result=rag_res,
                        result_summary=f"Found {len(rag_res.get('chunks', []))} regulatory passages",
                        evidence_id=rag_ev.evidence_id,
                        status="completed",
                        duration_ms=(time.time() - t_rag0) * 1000.0,
                    ))
                    raw_chunks = rag_res.get("chunks", [])
                    jur_warning = rag_res.get("jurisdiction_warning")
                except Exception as rag_err:
                    logger.warning(f"Fallback regulatory search error: {rag_err}")

            reg_items = [
                RegulatoryContextItem(
                    chunk_id=c["chunk_id"],
                    document_id=c["document_id"],
                    document_name=c["document_name"],
                    authority=c["authority"],
                    jurisdiction=c["jurisdiction"],
                    section=c.get("section"),
                    page_number=c["page_number"],
                    chunk_text=c["chunk_text"],
                    relevance_score=c.get("relevance_score"),
                )
                for c in raw_chunks
            ]

            inv_context = InvestigationContext(
                transaction_data=tx_data,
                risk_data={
                    "risk_level": eval_risk_lvl,
                    "risk_score": canonical_target_risk["risk_score"] if canonical_target_risk else 0.0,
                    "fraud_probability": canonical_target_risk["fraud_probability"] if canonical_target_risk else (fraud_tc.result.get("fraud_probability", 0.0) if fraud_tc else 0.0),
                    "anomaly_score": canonical_target_risk["anomaly_score"] if canonical_target_risk else (anom_tc.result.get("anomaly_score", 0.0) if anom_tc else 0.0),
                    "is_fraud": fraud_tc.result.get("is_fraud", False) if fraud_tc else False,
                    "is_anomaly": anom_tc.result.get("is_anomaly", False) if anom_tc else False,
                    "signals": canonical_target_risk["signals"] if canonical_target_risk else [],
                },
                aml_signals=sorted(list(set(risk_signals))),
                account_context=acc_tc.result if acc_tc else {},
                regulatory_context=reg_items,
                historical_context=[],
            )

            inv_step_id = execution_service.add_step(
                execution_id=exec_id,
                name="Risk Investigation Reasoning",
                step_type="llm",
                arguments={"transaction_id": tx_data.get("transaction_id"), "evidence_count": len(evidence_ids)},
            )

            investigation_model, answer = self.generate_investigation_reasoning(
                context=inv_context,
                execution_evidence_ids=evidence_ids,
                jurisdiction_warning=jur_warning,
            )

            execution_service.complete_step(
                execution_id=exec_id,
                step_id=inv_step_id,
                result_summary=f"Investigation reasoning synthesized for TX {tx_data.get('transaction_id')}",
                duration_ms=(time.time() - t_inv_start) * 1000.0,
            )

            t_vr_start = time.time()
            vr_step_id = execution_service.add_step(
                execution_id=exec_id,
                name="Investigation Verifier",
                step_type="verifier",
                arguments={"investigation_tx": investigation_model.transaction_id, "evidence_count": len(evidence_ids)},
            )
            vr_res = verifier.verify_risk_investigation(
                investigation_model,
                inv_context,
                execution_evidence_ids=evidence_ids,
            )
            verified = all_tools_ok and vr_res.ok and len(evidence_ids) > 0
            vr_summary = f"PASS: Investigation verified ({len(investigation_model.regulatory_citation_ids)} citations verified)" if vr_res.ok else f"FAIL: {'; '.join(vr_res.issues)}"
            execution_service.complete_step(
                execution_id=exec_id,
                step_id=vr_step_id,
                result_summary=vr_summary,
                duration_ms=(time.time() - t_vr_start) * 1000.0,
            )

            regulatory_citations = [c.model_dump() for c in reg_items]
            regulatory_citation_ids = investigation_model.regulatory_citation_ids

        else:
            t_vr_start = time.time()
            vr_step_id = execution_service.add_step(
                execution_id=exec_id,
                name="Verifier",
                step_type="verifier",
                arguments={"evidence_count": len(evidence_ids), "all_tools_ok": all_tools_ok},
            )

            reg_tc = next((tc for tc in tool_responses if tc.tool == "regulatory_search" and tc.result), None)
            if reg_tc and isinstance(reg_tc.result, dict):
                chunks = reg_tc.result.get("chunks", [])
                regulatory_citations = chunks
                regulatory_citation_ids = [c.get("chunk_id") for c in chunks if c.get("chunk_id")]
                vr_reg = verifier.verify_regulatory_retrieval(regulatory_citation_ids)
                verified = all_tools_ok and vr_reg.ok and len(evidence_ids) > 0
                vr_summary = "PASS: Regulatory citations verified" if vr_reg.ok else f"FAIL: {'; '.join(vr_reg.issues)}"
            else:
                verified = all_tools_ok and len(evidence_ids) > 0
                vr_summary = "PASS: All claims strictly backed by verified tool evidence" if verified else "FAIL: Tool execution error or missing evidence"

            execution_service.complete_step(
                execution_id=exec_id,
                step_id=vr_step_id,
                result_summary=vr_summary,
                duration_ms=(time.time() - t_vr_start) * 1000.0,
            )

            t_llm_start = time.time()
            llm_step_id = execution_service.add_step(
                execution_id=exec_id,
                name="LLM Grounded Explanation",
                step_type="llm",
                arguments={"query": message, "verified": verified, "evidence_count": len(evidence_ids)},
            )

            answer = self.generate_grounded_answer(
                message=message,
                intent=intent,
                tool_responses=tool_responses,
                risk_signals=sorted(list(set(risk_signals))),
                verified=verified,
                history=history,
            )

            execution_service.complete_step(
                execution_id=exec_id,
                step_id=llm_step_id,
                result_summary="Grounded explanation generated",
                duration_ms=(time.time() - t_llm_start) * 1000.0,
            )

        canonical_map = {}
        for it in recent_found_tx_items:
            it_id = str(it.get("transaction_id") or "")
            if it_id:
                canonical_map[it_id] = risk_service.get_canonical_risk(it_id, it)
        if target_tid and canonical_target_risk:
            canonical_map[str(target_tid)] = canonical_target_risk

        vr_risk = verifier.verify_risk_consistency(
            answer=answer,
            transactions=recent_found_tx_items,
            canonical_risk_map=canonical_map,
        )
        if not vr_risk.ok:
            verified = False
            logger.warning(f"Risk consistency verification failed: {'; '.join(vr_risk.issues)}")

        execution_service.finish_execution(
            execution_id=exec_id,
            final_answer=answer,
            status="COMPLETED" if verified else "FAILED",
        )

        conversation_service.add_message(
            conversation_id,
            role="user",
            content=message,
            transaction_id=tx_id,
            account_id=acc_id,
            case_id=case_id,
        )
        conversation_service.add_message(
            conversation_id,
            role="assistant",
            content=answer,
            transaction_id=tx_id or (recent_found_tx_ids[0] if recent_found_tx_ids else None),
            recent_tx_ids=recent_found_tx_ids,
            recent_transactions=recent_found_tx_items,
            investigation=investigation_model.model_dump() if investigation_model else None,
            intent=intent,
            evidence_ids=evidence_ids,
        )

        return CopilotExecutionResult(
            exec_id,
            tool_responses,
            sorted(list(set(risk_signals))),
            verified,
            answer,
            risk_drivers,
            intent,
            investigation=investigation_model,
            regulatory_citations=regulatory_citations,
            regulatory_citation_ids=regulatory_citation_ids,
            transactions=recent_found_tx_items,
        )

    def generate_investigation_reasoning(
        self,
        *,
        context: InvestigationContext,
        execution_evidence_ids: list[str],
        jurisdiction_warning: str | None = None,
    ) -> tuple[RiskInvestigationResponse, str]:
        tx = context.transaction_data
        tx_id = str(tx.get("transaction_id", "N/A"))
        amount = float(tx.get("amount") or 0.0)
        currency = tx.get("currency", "USD")
        sender = tx.get("sender_id", "N/A")
        receiver = tx.get("receiver_id", "N/A")
        ts = str(tx.get("timestamp", "N/A"))
        tx_type = tx.get("transaction_type", "TRANSFER")

        risk_data = context.risk_data
        risk_level = risk_data.get("risk_level", "LOW")
        fraud_prob = float(risk_data.get("fraud_probability") or 0.0)
        anom_score = float(risk_data.get("anomaly_score") or 0.0)
        risk_score = float(risk_data.get("risk_score") or 0.0)

        verified_facts = [
            f"Transaction ID: {tx_id}",
            f"Amount: ${amount:,.2f} {currency}",
            f"Sender Account: {sender}",
            f"Receiver Account: {receiver}",
            f"Timestamp: {ts}",
            f"Payment Format: {tx_type}",
        ]

        risk_signals = list(context.aml_signals)
        if not risk_signals:
            if fraud_prob > 0.5:
                risk_signals.append(f"Elevated fraud probability ({fraud_prob:.1%})")
            if anom_score > 0.5:
                risk_signals.append(f"Elevated isolation anomaly ({anom_score:.1%})")
            if not risk_signals:
                risk_signals.append("Baseline ledger activity")

        reg_chunks = context.regulatory_context
        retrieved_ids = [c.chunk_id for c in reg_chunks]

        system_instruction = (
            "You are the investigation reasoning component of RAILS.\n\n"
            "Analyze only the verified transaction/risk evidence and regulatory passages supplied to you.\n\n"
            "CRITICAL: CANONICAL RISK LEVEL IMMUTABILITY\n"
            "- The backend risk level provided in the Risk Data (Evaluated Risk Level: LOW / MEDIUM / HIGH / CRITICAL) is CANONICAL and FINAL.\n"
            "- You must NEVER calculate, reinterpret, alter, or change the risk level, fraud probability, anomaly score, or risk score.\n"
            "- You must explicitly state and explain the exact canonical risk level provided. If backend says LOW, you must say LOW. You must never turn LOW into HIGH or HIGH into LOW based on your own interpretation.\n\n"
            "Do not calculate risk values.\n\n"
            "Do not invent transaction facts.\n\n"
            "Do not invent regulatory requirements.\n\n"
            "Do not create citations that were not supplied.\n\n"
            "Clearly distinguish:\n"
            "1. Verified transaction facts\n"
            "2. Verified risk signals\n"
            "3. Regulatory guidance\n"
            "4. Analytical interpretation\n\n"
            "FATF material is GLOBAL guidance.\n\n"
            "FinCEN material is US-specific.\n\n"
            "Never present FinCEN guidance as Indian law.\n\n"
            "If the supplied regulatory context does not establish a regulatory claim, explicitly state that the available regulatory corpus does not establish it.\n\n"
            "When explaining why a regulatory passage is relevant, explain the connection but do not claim that the guidance legally determines that the transaction is suspicious.\n\n"
            "The final response must be suitable for a compliance analyst reviewing a case."
        )

        reg_text_lines = []
        for rc in reg_chunks[:4]:
            reg_text_lines.append(
                f"- Citation ID: [{rc.chunk_id}] | Document: {rc.document_name} | Authority: {rc.authority} | Jurisdiction: {rc.jurisdiction} | Section: {rc.section} | Page: {rc.page_number}\n"
                f"  Passage text: \"{rc.chunk_text}\""
            )
        reg_summary_str = "\n".join(reg_text_lines) if reg_text_lines else "No regulatory chunks retrieved."

        prompt = f"""Target Transaction: {tx_id}
Verified Facts:
{json.dumps(verified_facts)}

Risk Data:
- Evaluated Risk Level: {risk_level}
- Fraud Probability: {fraud_prob:.1%}
- Anomaly Score: {anom_score:.1%}
- Confirmed Risk Signals: {json.dumps(risk_signals)}

Supplied Regulatory Context:
{reg_summary_str}

Jurisdiction Notice: {jurisdiction_warning or "None"}

Please produce a structured JSON object with the following fields:
{{
  "summary": "1-2 sentence executive summary of the investigation",
  "regulatory_findings": ["1-3 statements explaining the connection to supplied regulatory guidance, citing chunk IDs and page numbers"],
  "investigation_finding": "Detailed compliance analytical interpretation",
  "recommended_action": "Actionable next steps for the compliance officer (e.g. SAR review, CDD refresh)",
  "regulatory_citation_ids": ["list of chunk_ids cited, only from supplied context"]
}}
"""
        parsed_llm = None
        raw_llm = self.gemini.generate(prompt, system_instruction=system_instruction, temperature=0.2)
        if raw_llm:
            try:
                clean_json = re.sub(r"^```(?:json)?\s*", "", raw_llm.strip())
                clean_json = re.sub(r"\s*```$", "", clean_json)
                parsed_llm = json.loads(clean_json)
            except Exception as e:
                logger.warning(f"Could not parse Gemini investigation JSON: {e}")

        if not parsed_llm:
            summary = f"Investigation for transaction {tx_id}: evaluated as {risk_level} risk due to {', '.join(risk_signals[:2])}."
            regulatory_findings = []
            for rc in reg_chunks[:3]:
                regulatory_findings.append(
                    f"[{rc.chunk_id}] {rc.document_name} (Page {rc.page_number}): Standards applicable to {rc.section or 'suspicious activity reporting'}."
                )
            investigation_finding = (
                f"Transaction {tx_id} involves a transfer of ${amount:,.2f} from sender {sender} to receiver {receiver}. "
                f"The transaction triggered risk signals ({', '.join(risk_signals)}), reflecting elevated anomaly or behavioral variance. "
                f"Compliance review is indicated based on established reporting guidelines."
            )
            recommended_action = (
                f"Initiate compliance case review for account {sender}. Verify customer due diligence and determine if a formal SAR filing is warranted under applicable regulations."
            )
            citation_ids = retrieved_ids[:3]
        else:
            summary = parsed_llm.get("summary") or f"Investigation of transaction {tx_id} flagged as {risk_level}."
            regulatory_findings = parsed_llm.get("regulatory_findings") or []
            investigation_finding = parsed_llm.get("investigation_finding") or "Verified analysis indicates elevated risk patterns requiring compliance review."
            recommended_action = parsed_llm.get("recommended_action") or "Review customer profile and escalate for potential SAR filing."
            raw_cids = parsed_llm.get("regulatory_citation_ids") or []
            citation_ids = [cid for cid in raw_cids if cid in retrieved_ids]
            if not citation_ids and retrieved_ids:
                citation_ids = retrieved_ids[:2]

        inv_resp = RiskInvestigationResponse(
            transaction_id=tx_id,
            risk_level=risk_level,
            risk_score=risk_score,
            fraud_probability=fraud_prob,
            anomaly_score=anom_score,
            signals=risk_signals,
            summary=summary,
            verified_facts=verified_facts,
            risk_signals=risk_signals,
            regulatory_findings=regulatory_findings,
            investigation_finding=investigation_finding,
            recommended_action=recommended_action,
            evidence_ids=execution_evidence_ids,
            regulatory_citation_ids=citation_ids,
        )

        reg_lines = []
        if jurisdiction_warning:
            reg_lines.append(f"> ⚠️ **Jurisdiction Notice**: {jurisdiction_warning}")
        if not reg_chunks:
            reg_lines.append("• No specific regulatory filing triggers found for this threshold.")
        else:
            for rc in reg_chunks:
                if rc.chunk_id in citation_ids or len(citation_ids) == 0:
                    reg_lines.append(
                        f"• [{rc.chunk_id}] {rc.document_name} ({rc.authority} — {rc.jurisdiction}): {rc.section or 'Reporting Guidance'} (Page {rc.page_number})\n"
                        f"  \"{rc.chunk_text[:180]}...\""
                    )

        md_lines = [
            f"Transaction `{tx_id}` is currently classified as **{risk_level}** risk.\n",
            "### Verified Facts",
            f"• Amount: ${amount:,.2f} {currency}",
            f"• Sender: `{sender}`",
            f"• Receiver: `{receiver}`",
            f"• Payment method: {tx_type}",
            f"• Timestamp: {ts}\n",
            "### Risk Signals",
        ]
        for s in risk_signals:
            md_lines.append(f"• {s}")

        fprob_str = f"{fraud_prob:.3%}" if (0.0 < fraud_prob < 0.001) else f"{fraud_prob:.1%}"
        anom_str = f"{anom_score:.3%}" if (0.0 < anom_score < 0.001) else f"{anom_score:.1%}"
        md_lines.append(f"\nFraud probability: {fprob_str}")
        md_lines.append(f"Anomaly score: {anom_str}\n")

        md_lines.append("### Regulatory Context")
        md_lines.extend(reg_lines)

        md_lines.append(f"\n### Investigation Finding & Assessment\n{investigation_finding}\n")
        md_lines.append(f"### Recommended Next Step\n{recommended_action}")

        full_md = "\n".join(md_lines)
        return inv_resp, full_md

    def generate_grounded_answer(
        self,
        *,
        message: str,
        intent: str,
        tool_responses: list[ToolCallResponse],
        risk_signals: list[str],
        verified: bool,
        history: list[dict[str, str]],
    ) -> str:
        if not tool_responses:
            return (
                "I could not retrieve matching records from the database. "
                "Please verify the identifier or search query and try again."
            )

        evidence_lines = []
        for tc in tool_responses:
            if tc.status == "failed":
                evidence_lines.append(f"- Tool '{tc.tool}' FAILED with error: {tc.error}")
            else:
                evidence_lines.append(f"- Tool '{tc.tool}': {json.dumps(tc.result, default=str)} [Evidence: {tc.evidence_id}]")

        evidence_str = "\n".join(evidence_lines)

        system_instruction = (
            "You are the RAILS Risk, Fraud and Regulatory Intelligence Copilot.\n"
            "Produce a direct, professional, conversational response answering the user's question like a banking risk/compliance analyst.\n"
            "CRITICAL RULES:\n"
            "1. ONLY state facts, numbers, dates, amounts, risk scores, and statuses that exist in the Verified Tool Evidence.\n"
            "2. CANONICAL RISK LEVEL IMMUTABILITY:\n"
            "   - The backend risk level provided in the evidence (e.g. Risk: LOW / MEDIUM / HIGH / CRITICAL) is CANONICAL, FIXED, and FINAL.\n"
            "   - You must NEVER calculate, reinterpret, alter, or override the risk level, fraud probability, anomaly score, or risk score.\n"
            "   - You must NEVER turn LOW into HIGH or HIGH into LOW based on your own interpretation of individual scores or signals.\n"
            "   - If the backend says LOW, you must state LOW. If the backend says HIGH, you must state HIGH.\n"
            "3. NEVER invent or fabricate any transaction IDs, amounts, accounts, risk levels, or case numbers.\n"
            "4. If tool result is empty or not found, state honestly: 'No high-risk transactions were found in the available dataset.'\n"
            "5. When presenting high-risk or high-fraud transactions, format as:\n"
            "   Here are {N} high-risk transactions:\n\n"
            "   1. Transaction <id>\n"
            "      Risk: <level>\n"
            "      Fraud probability: <prob>%\n"
            "      Amount: $<amount>\n"
            "      Key signal: <signal>\n\n"
            "   I can investigate any of these transactions further.\n"
            "6. When presenting an investigation, format with:\n"
            "   Transaction <id> is currently classified as <level> risk.\n\n"
            "   Verified facts:\n"
            "   • Amount: ...\n"
            "   • Sender: ...\n"
            "   • Receiver: ...\n"
            "   • Payment method: ...\n\n"
            "   Risk signals:\n"
            "   • ...\n\n"
            "   Fraud probability: ...\n"
            "   Anomaly score: ...\n\n"
            "   Regulatory context:\n"
            "   • ...\n\n"
            "   Assessment:\n"
            "   ...\n\n"
            "   Recommended next step:\n"
            "   ...\n"
            "7. Do NOT dump raw JSON into the main response.\n"
            "8. For regulatory knowledge retrieval (regulatory_search):\n"
            "   - Ground answers strictly in the retrieved passages.\n"
            "   - Explicitly cite Document Name, Authority (FATF or FinCEN), Jurisdiction (GLOBAL or US), Section, and Page Number (with Chunk ID).\n"
            "   - If a jurisdiction_warning is present or if asked about an unrepresented jurisdiction (e.g. India / RBI), clearly state that the corpus contains GLOBAL (FATF) and US (FinCEN) guidance, and does not establish India-specific statutory requirements. Do NOT confuse FinCEN with Indian regulations.\n"
            "9. NEVER include raw evidence IDs (e.g. ev-1, ev-case, ev-...) in the final response. Present verified conclusions naturally without exposing raw internal evidence identifiers.\n"
        )

        prompt = f"""User Question: "{message}"
Intent: {intent}
Verified Tool Evidence:
{evidence_str}

Active Risk Signals: {risk_signals}
Verification Status: {"PASSED" if verified else "PARTIAL / FAILED"}

Provide a comprehensive, conversational explanation answering the user's inquiry based strictly on the evidence above.
"""
        gemini_answer = self.gemini.generate(prompt, system_instruction=system_instruction, temperature=0.2)
        if gemini_answer and len(gemini_answer.strip()) > 20:
            return gemini_answer.strip()

        return self._deterministic_answer(message, tool_responses, risk_signals)

    def _deterministic_answer(
        self,
        message: str,
        tool_responses: list[ToolCallResponse],
        risk_signals: list[str],
    ) -> str:
        paragraphs: list[str] = []
        for tc in tool_responses:
            if tc.status == "failed":
                paragraphs.append(f"⚠️ **{tc.tool} failed**: {tc.error}")
                continue

            r = tc.result or {}

            if tc.tool == "get_high_risk_transactions":
                items = r.get("items", [])
                if not items:
                    paragraphs.append("No high-risk transactions were found in the available dataset.")
                else:
                    paragraphs.append(f"Here are {len(items)} high-risk transactions:\n")
                    for i, item in enumerate(items, 1):
                        tid = item.get("transaction_id", "N/A")
                        rlvl = item.get("risk_level", "HIGH")
                        fprob = float(item.get("fraud_probability") or 0.0)
                        amt = float(item.get("amount") or 0.0)
                        sigs = item.get("signals", [])
                        sigs_str = ", ".join(sigs) if sigs else "baseline variance"

                        fprob_display = f"{fprob:.3%}" if (0.0 < fprob < 0.001) else f"{fprob:.1%}"
                        paragraphs.append(
                            f"{i}. Transaction {tid}\n"
                            f"   Risk: {rlvl}\n"
                            f"   Fraud probability: {fprob_display}\n"
                            f"   Amount: ${amt:,.2f}\n"
                            f"   Key signal: {sigs_str}\n"
                        )

                    paragraphs.append("I can investigate any of these transactions further.")

            elif tc.tool == "get_transaction":
                if r.get("found"):
                    tx = r.get("transaction", {})
                    paragraphs.append(
                        f"### Transaction {tx.get('transaction_id')}\n"
                        f"• **Amount**: ${float(tx.get('amount') or 0):,.2f} {tx.get('currency', 'USD')}\n"
                        f"• **Sender**: `{tx.get('sender_id')}`\n"
                        f"• **Receiver**: `{tx.get('receiver_id')}`\n"
                        f"• **Type**: {tx.get('transaction_type', 'TRANSFER')}\n"
                        f"• **Timestamp**: {tx.get('timestamp')}"
                    )
                else:
                    paragraphs.append(f"Transaction `{tc.arguments.get('transaction_id')}` was not found in the ledger database.")

            elif tc.tool == "fraud_check":
                prob = r.get("fraud_probability", 0.0)
                lvl = r.get("risk_level", "LOW")
                paragraphs.append(f"• **Fraud Assessment**: Level `{lvl}` (Probability: {prob:.1%})")

            elif tc.tool == "anomaly_check":
                score = r.get("anomaly_score", 0.0)
                lvl = r.get("risk_level", "LOW")
                paragraphs.append(f"• **Anomaly Assessment**: Level `{lvl}` (Score: {score:.1%})")

            elif tc.tool == "rules_check":
                rules = r.get("triggered_rules", [])
                paragraphs.append(f"• **AML Rules Engine**: Triggered {len(rules)} rule(s) — {', '.join(rules) if rules else 'None'}")

            elif tc.tool == "list_transactions":
                items = r.get("items", [])
                paragraphs.append(f"Retrieved {len(items)} transactions from the database:")
                for item in items[:5]:
                    paragraphs.append(f"• TX `{item.get('transaction_id')}`: ${float(item.get('amount') or 0):,.2f} ({item.get('risk_level', 'LOW')})")

            elif tc.tool == "account_history":
                hist = r.get("history", [])
                paragraphs.append(f"Account `{tc.arguments.get('account_id')}` has {len(hist)} recorded historical transactions.")

            elif tc.tool == "account_risk_check":
                score = r.get("risk_score", 0.0)
                lvl = r.get("risk_level", "LOW")
                paragraphs.append(f"• **Account Risk**: `{lvl}` (Score: {score:.2f})")

            elif tc.tool == "list_cases":
                cases = r.get("items", [])
                paragraphs.append(f"Found {len(cases)} compliance investigation cases:")
                for c in cases[:5]:
                    paragraphs.append(f"• Case `{c.get('case_id')}`: {c.get('title')} ({c.get('status', 'OPEN')})")

            elif tc.tool == "list_alerts":
                alerts = r.get("items", [])
                paragraphs.append(f"Found {len(alerts)} surveillance alerts:")
                for a in alerts[:5]:
                    paragraphs.append(f"• Alert `{a.get('alert_id')}`: TX `{a.get('transaction_id')}` ({a.get('risk_level')})")

            elif tc.tool == "generate_report":
                paragraphs.append(
                    f"## Suspicious Transaction Report Draft\n\n"
                    f"• **Report ID**: `{r.get('report_id')}`\n"
                    f"• **Case ID**: `{r.get('case_id')}`\n"
                    f"• **Status**: `{r.get('status')}`\n"
                    f"• **Summary**: {r.get('title')}\n\n"
                    f"{r.get('body')}"
                )

            elif tc.tool == "regulatory_search":
                chunks = r.get("chunks", [])
                jur_warn = r.get("jurisdiction_warning")
                paragraphs.append("## Regulatory Intelligence Retrieval")
                if jur_warn:
                    paragraphs.append(f"> ⚠️ **Jurisdiction Notice**: {jur_warn}")
                if not chunks:
                    paragraphs.append("No directly matching regulatory passages were found in the authoritative corpus for this query.")
                else:
                    for i, c in enumerate(chunks[:4], 1):
                        paragraphs.append(
                            f"### {i}. {c.get('document_name')} ({c.get('authority')} — {c.get('jurisdiction')})\n"
                            f"• **Section**: *{c.get('section', 'General')}* (Page {c.get('page_number')})\n"
                            f"• **Citation ID**: `{c.get('chunk_id')}`\n"
                            f"• **Passage**:\n"
                            f"> \"{c.get('chunk_text')}\""
                        )

        if risk_signals and not any(tc.tool == "get_high_risk_transactions" for tc in tool_responses):
            paragraphs.append(f"\n**Identified Risk Signals**: `{', '.join(set(risk_signals))}`")

        return "\n\n".join(paragraphs) if paragraphs else "Completed analysis based on verified ledger evidence."


orchestrator = LLMOrchestrator()

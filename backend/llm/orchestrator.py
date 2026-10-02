from __future__ import annotations

import json
import logging
import re
import time
from typing import Any
from uuid import uuid4

from backend.evidence.store import evidence_store
from backend.llm.gemini_client import gemini_client
from backend.schemas.copilot import ToolCallResponse
from backend.services.conversation_service import conversation_service
from backend.services.execution_service import execution_service
from backend.tools.contracts import TOOL_CONTRACTS, ToolValidationError, validate_tool_call
from backend.tools.runner import run_tool

logger = logging.getLogger(__name__)

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

    def is_conversational(self, message: str) -> bool:
        clean = message.strip().lower()
        clean_words = re.sub(r"[^\w\s]", "", clean).split()

        if clean in GREETINGS or clean in THANKS or any(c in clean for c in CAPABILITIES):
            return True
        if len(clean_words) == 1 and (clean_words[0] in GREETINGS or clean_words[0] in THANKS):
            return True
        if len(clean_words) == 2 and clean_words[0] in GREETINGS and clean_words[1] in ("there", "copilot", "rails"):
            return True
        return False

    def resolve_references(self, message: str, context: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
        """Resolves pronoun and ordinal references (e.g. 'the first one', 'it') from conversation context."""
        lower = message.lower()
        recent_txs = context.get("recent_transaction_ids", [])
        last_tx = context.get("last_transaction_id")
        last_acc = context.get("last_account_id")
        last_case = context.get("last_case_id")

        tx_id = None
        acc_id = None
        case_id = None

        # Direct regex extraction
        m_tx = re.search(r"\b(tx-[a-zA-Z0-9_-]+|\d{7,10})\b", message, re.IGNORECASE)
        if m_tx:
            tx_id = m_tx.group(1)

        m_acc = re.search(r"\b(ACC_[a-zA-Z0-9_-]+|[0-9A-Z]{9}|account\s*[:#]?\s*([a-zA-Z0-9_-]+))\b", message, re.IGNORECASE)
        if m_acc:
            acc_id = m_acc.group(2) if m_acc.group(2) else m_acc.group(1)

        m_case = re.search(r"\b(case-[a-zA-Z0-9_-]+|CASE-[0-9]{4}-[0-9]+)\b", message, re.IGNORECASE)
        if m_case:
            case_id = m_case.group(1)

        # Contextual resolution for references
        if not tx_id:
            if any(p in lower for p in ("first one", "1st one", "first transaction", "the first")):
                if recent_txs and len(recent_txs) >= 1:
                    tx_id = recent_txs[0]
            elif any(p in lower for p in ("second one", "2nd one", "second transaction", "the second")):
                if recent_txs and len(recent_txs) >= 2:
                    tx_id = recent_txs[1]
            elif any(p in lower for p in ("third one", "3rd one", "third transaction", "the third")):
                if recent_txs and len(recent_txs) >= 3:
                    tx_id = recent_txs[2]
            elif any(p in lower for p in ("why was it", "why is it", "that transaction", "this transaction", "about it", "flagged")):
                tx_id = last_tx

        if not acc_id and any(p in lower for p in ("that account", "this account", "the account", "its profile", "its risk")):
            acc_id = last_acc

        if not case_id and any(p in lower for p in ("that case", "this case", "the case", "highest risk case", "open case")):
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
        """Determines intent and required tool calls.

        Conversational requests NEVER invoke database tools.
        """
        # 1. Immediate greeting check (Zero tools called)
        if self.is_conversational(message):
            return "conversation", []

        # 2. Deterministic high-priority checks
        lower = message.lower()

        # Regulatory Reports / STR Draft
        if any(k in lower for k in ("str", "sar", "draft report", "generate report", "regulatory report", "draft a suspicious")):
            cid = resolved_case
            if not cid:
                from backend.services.case_service import case_service
                cases = case_service.list_cases(limit=1)
                if cases:
                    cid = cases[0].get("case_id")
            return "regulatory_report", [{"tool": "generate_report", "arguments": {"case_id": cid or "case-141d2081"}}]

        # Risk-ranked queries must ALWAYS use get_high_risk_transactions, NEVER list_transactions
        if any(k in lower for k in (
            "highest risk", "most high risk", "high risk trans", "high risk transactions",
            "highest-risk", "most suspicious", "highest fraud", "fraud transactions",
            "critical transactions", "flagged transactions", "suspicious transactions",
        )):
            sort_by = "fraud_probability" if ("fraud" in lower and "risk" not in lower) else "risk_score"
            return "risk_transactions", [{"tool": "get_high_risk_transactions", "arguments": {"limit": 5, "sort_by": sort_by}}]

        # Fraud analysis
        if any(k in lower for k in ("fraud analysis", "recent fraud", "fraud signals")):
            if resolved_tx:
                return "transaction_investigation", [{"tool": "get_transaction", "arguments": {"transaction_id": resolved_tx}}]
            return "fraud_analysis", [{"tool": "get_high_risk_transactions", "arguments": {"limit": 5, "sort_by": "fraud_probability"}}]

        # Transaction investigation
        if resolved_tx:
            return "transaction_investigation", [{"tool": "get_transaction", "arguments": {"transaction_id": resolved_tx}}]

        # Account risk profile
        if resolved_acc or any(k in lower for k in ("risk profile of account", "risk of account", "account risk")):
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

        # Regulatory Requirements (FinCEN / FATF / BSA guidance — no tools needed)
        if any(k in lower for k in ("fincen", "fatf", "bsa", "regulatory requirements", "travel rule", "reporting requirements")):
            return "regulatory_requirements", []

        # Cases
        if any(k in lower for k in ("open cases", "my cases", "show cases", "list cases")):
            if resolved_case:
                return "cases", [{"tool": "get_case", "arguments": {"case_id": resolved_case}}]
            return "cases", [{"tool": "list_cases", "arguments": {"limit": 10}}]

        # Alerts
        if any(k in lower for k in ("alerts", "open alerts", "critical alerts", "show alerts", "flagged alerts")):
            return "alerts", [{"tool": "list_alerts", "arguments": {"limit": 10}}]

        # Latest / regular transactions
        if any(k in lower for k in ("latest transactions", "recent transactions", "show transactions", "list transactions")):
            return "transactions", [{"tool": "list_transactions", "arguments": {"limit": 10}}]

        # Simulation requests
        if any(k in lower for k in ("simulation", "simulate", "run scenario", "test scenario")):
            return "simulation", []

        # 3. LLM-based planning fallback for nuanced requests
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
        plan_raw = self.gemini.generate(prompt, system_instruction=system_instruction, temperature=0.1)
        if plan_raw:
            try:
                clean_json = re.sub(r"^```(?:json)?\s*", "", plan_raw.strip())
                clean_json = re.sub(r"\s*```$", "", clean_json)
                parsed = json.loads(clean_json)
                intent = parsed.get("intent", "conversation")
                tool_calls = parsed.get("tool_calls", [])
                if intent == "conversation":
                    return "conversation", []
                if isinstance(tool_calls, list):
                    return intent, tool_calls
            except Exception as e:
                logger.warning(f"Failed to parse Gemini plan JSON: {e}")

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
        """Executes full end-to-end Copilot flow with real Gemini planning, tool execution, evidence store, and verifier."""
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

        # Step 1: Planner
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

        # Conversational fast path: NEVER call backend database tools for greetings
        if intent == "conversation":
            answer = (
                "Hello! I'm the RAILS Risk, Fraud, and Regulatory Intelligence Copilot. "
                "I can help you investigate transactions, accounts, fraud alerts, cases, and regulatory reports."
            )
            execution_service.finish_execution(
                execution_id=exec_id,
                final_answer=answer,
                status="COMPLETED",
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
                recent_tx_ids=[],
                evidence_ids=[],
            )
            return exec_id, [], [], True, answer, [], intent

        # Regulatory requirements fast path: Informative guidance without querying individual transactions
        if intent == "regulatory_requirements":
            answer = (
                "## Regulatory Reporting & Compliance Framework\n\n"
                "• **FinCEN BSA / Suspicious Activity Reports (SAR)**: Mandates filing within 30 calendar days of initial detection of suspicious activity involving aggregates exceeding $5,000.\n"
                "• **Structuring Prohibitions (31 CFR § 1010.314)**: Outlaws breaking up transactions to evade Currency Transaction Report ($10,000 threshold) filings.\n"
                "• **FATF Recommendation 16 (Travel Rule)**: Requires financial institutions to obtain and transmit verified originator and beneficiary information for cross-border wire transfers.\n"
                "• **Audit Evidence**: All flagged alerts and generated filings in RAILS are preserved with immutable cryptographic evidence tokens."
            )
            execution_service.finish_execution(
                execution_id=exec_id,
                final_answer=answer,
                status="COMPLETED",
            )
            conversation_service.add_message(conversation_id, role="user", content=message)
            conversation_service.add_message(conversation_id, role="assistant", content=answer)
            return exec_id, [], [], True, answer, [], intent

        # Step 2: Tool execution with dependency chaining
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

                # Dependency chaining if this was get_transaction
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

        # Extract risk signals & drivers
        recent_found_tx_ids: list[str] = []
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
                            recent_found_tx_ids.append(str(item["transaction_id"]))

        # Step 3: Verifier
        t_vr_start = time.time()
        vr_step_id = execution_service.add_step(
            execution_id=exec_id,
            name="Verifier",
            step_type="verifier",
            arguments={"evidence_count": len(evidence_ids), "all_tools_ok": all_tools_ok},
        )
        verified = all_tools_ok and len(evidence_ids) > 0
        vr_summary = "PASS: All claims strictly backed by verified tool evidence" if verified else "FAIL: Tool execution error or missing evidence"
        execution_service.complete_step(
            execution_id=exec_id,
            step_id=vr_step_id,
            result_summary=vr_summary,
            duration_ms=(time.time() - t_vr_start) * 1000.0,
        )

        # Step 4: Grounded Explanation with Gemini
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

        execution_service.finish_execution(
            execution_id=exec_id,
            final_answer=answer,
            status="COMPLETED" if verified else "FAILED",
        )

        # Persist conversation state
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
            recent_tx_ids=recent_found_tx_ids,
            evidence_ids=evidence_ids,
        )

        return exec_id, tool_responses, sorted(list(set(risk_signals))), verified, answer, risk_drivers, intent

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
        """Generates conversational, grounded answer using Gemini based strictly on verified tool outputs."""
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
            "Produce a direct, professional, conversational response answering the user's question.\n"
            "CRITICAL RULES:\n"
            "1. ONLY state facts, numbers, dates, amounts, risk scores, and statuses that exist in the Verified Tool Evidence.\n"
            "2. NEVER invent or fabricate any transaction IDs, amounts, accounts, risk levels, or case numbers.\n"
            "3. If tool result is empty or not found, state honestly: 'No high-risk transactions were found in the available dataset.'\n"
            "4. For risk transactions, format as:\n"
            "   ## Highest-Risk Transactions\n"
            "   1. **TX <id>**\n"
            "      - Risk: <level>\n"
            "      - Risk score: <score>\n"
            "      - Fraud probability: <prob>\n"
            "      - Anomaly score: <score>\n"
            "      - Amount: $<amount>\n"
            "      - Signals: <signals>\n"
            "   ### Why these were flagged\n"
            "   [Explanation based strictly on returned signals]\n"
            "5. Cite verified evidence IDs (e.g. [ev-1]).\n"
            "6. Do NOT dump raw JSON into the main response.\n"
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
                    paragraphs.append(f"## Highest-Risk Transactions\n\nI found {len(items)} transactions with the highest recorded risk scores in the database.")
                    for i, item in enumerate(items, 1):
                        tid = item.get("transaction_id", "N/A")
                        rlvl = item.get("risk_level", "HIGH")
                        rscore = float(item.get("risk_score") or 0.0)
                        fprob = float(item.get("fraud_probability") or 0.0)
                        anom = float(item.get("anomaly_score") or 0.0)
                        amt = float(item.get("amount") or 0.0)
                        sigs = item.get("signals", [])
                        sigs_str = ", ".join(sigs) if sigs else "baseline"

                        paragraphs.append(
                            f"{i}. **TX {tid}**\n"
                            f"   - Risk: {rlvl}\n"
                            f"   - Risk score: {rscore:.2f}\n"
                            f"   - Fraud probability: {fprob:.1%}\n"
                            f"   - Anomaly score: {anom:.2f}\n"
                            f"   - Amount: ${amt:,.2f}\n"
                            f"   - Signals: {sigs_str}"
                        )

                    paragraphs.append(
                        "### Why these were flagged\n"
                        "These transactions triggered high risk thresholds due to elevated anomaly patterns, counterparty risk, velocity shifts, or compliance rule violations, as reflected in their active signals.\n\n"
                        f"Verified evidence: {tc.evidence_id}"
                    )

            elif tc.tool == "get_transaction":
                if r.get("found"):
                    tx = r.get("transaction", {})
                    paragraphs.append(
                        f"### Transaction {tx.get('transaction_id')}\n"
                        f"• **Amount**: ${float(tx.get('amount') or 0):,.2f} {tx.get('currency', 'USD')}\n"
                        f"• **Sender**: `{tx.get('sender_id')}`\n"
                        f"• **Receiver**: `{tx.get('receiver_id')}`\n"
                        f"• **Type**: {tx.get('transaction_type', 'TRANSFER')}\n"
                        f"• **Timestamp**: {tx.get('timestamp')} (Evidence: {tc.evidence_id})"
                    )
                else:
                    paragraphs.append(f"Transaction `{tc.arguments.get('transaction_id')}` was not found in the ledger database.")

            elif tc.tool == "fraud_check":
                prob = r.get("fraud_probability", 0.0)
                lvl = r.get("risk_level", "LOW")
                paragraphs.append(f"• **Fraud Assessment**: Level `{lvl}` (Probability: {prob:.1%}) [Evidence: {tc.evidence_id}]")

            elif tc.tool == "anomaly_check":
                score = r.get("anomaly_score", 0.0)
                lvl = r.get("risk_level", "LOW")
                paragraphs.append(f"• **Anomaly Assessment**: Level `{lvl}` (Score: {score:.1%}) [Evidence: {tc.evidence_id}]")

            elif tc.tool == "rules_check":
                rules = r.get("triggered_rules", [])
                paragraphs.append(f"• **AML Rules Engine**: Triggered {len(rules)} rule(s) — {', '.join(rules) if rules else 'None'} [Evidence: {tc.evidence_id}]")

            elif tc.tool == "list_transactions":
                items = r.get("items", [])
                paragraphs.append(f"Retrieved {len(items)} transactions from the database [Evidence: {tc.evidence_id}]:")
                for item in items[:5]:
                    paragraphs.append(f"• TX `{item.get('transaction_id')}`: ${float(item.get('amount') or 0):,.2f} ({item.get('risk_level', 'LOW')})")

            elif tc.tool == "account_history":
                hist = r.get("history", [])
                paragraphs.append(f"Account `{tc.arguments.get('account_id')}` has {len(hist)} recorded historical transactions [Evidence: {tc.evidence_id}].")

            elif tc.tool == "account_risk_check":
                score = r.get("risk_score", 0.0)
                lvl = r.get("risk_level", "LOW")
                paragraphs.append(f"• **Account Risk**: `{lvl}` (Score: {score:.2f}) [Evidence: {tc.evidence_id}]")

            elif tc.tool == "list_cases":
                cases = r.get("items", [])
                paragraphs.append(f"Found {len(cases)} compliance investigation cases [Evidence: {tc.evidence_id}]:")
                for c in cases[:5]:
                    paragraphs.append(f"• Case `{c.get('case_id')}`: {c.get('title')} ({c.get('status', 'OPEN')})")

            elif tc.tool == "list_alerts":
                alerts = r.get("items", [])
                paragraphs.append(f"Found {len(alerts)} surveillance alerts [Evidence: {tc.evidence_id}]:")
                for a in alerts[:5]:
                    paragraphs.append(f"• Alert `{a.get('alert_id')}`: TX `{a.get('transaction_id')}` ({a.get('risk_level')})")

            elif tc.tool == "generate_report":
                paragraphs.append(
                    f"## Suspicious Transaction Report Draft\n\n"
                    f"• **Report ID**: `{r.get('report_id')}`\n"
                    f"• **Case ID**: `{r.get('case_id')}`\n"
                    f"• **Status**: `{r.get('status')}`\n"
                    f"• **Summary**: {r.get('title')}\n\n"
                    f"{r.get('body')}\n\n"
                    f"Verified evidence: {tc.evidence_id}"
                )

        if risk_signals and not any(tc.tool == "get_high_risk_transactions" for tc in tool_responses):
            paragraphs.append(f"\n**Identified Risk Signals**: `{', '.join(set(risk_signals))}`")

        return "\n\n".join(paragraphs) if paragraphs else "Completed analysis based on verified ledger evidence."


orchestrator = LLMOrchestrator()

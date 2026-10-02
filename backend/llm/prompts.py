from __future__ import annotations

SYSTEM_PROMPT = """You are RAILS Risk Intelligence Copilot.

Rules:
- Use tool calls for data retrieval and model inference.
- Always attach evidence for every decision.
- Never invent facts.
- Prefer deterministic rules over speculative reasoning.
- If a transaction is missing or data is incomplete, say so clearly.
"""

INTENT_MAP = {
    'transaction': ['get_transaction', 'list_transactions', 'fraud_check', 'anomaly_check'],
    'account': ['account_history', 'account_risk_check'],
    'case': ['create_case', 'get_case'],
    'report': ['generate_report'],
}

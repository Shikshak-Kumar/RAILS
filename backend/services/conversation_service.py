from __future__ import annotations

import time
from typing import Any
from uuid import uuid4


class ConversationService:
    def __init__(self) -> None:
        self._conversations: dict[str, dict[str, Any]] = {}

    def get_or_create(self, conversation_id: str | None = None) -> tuple[str, dict[str, Any]]:
        cid = conversation_id or f"conv-{uuid4().hex[:10]}"
        if cid not in self._conversations:
            self._conversations[cid] = {
                "conversation_id": cid,
                "created_at": time.time(),
                "updated_at": time.time(),
                "messages": [],
                "context": {
                    "last_transaction_id": None,
                    "last_account_id": None,
                    "last_case_id": None,
                    "last_intent": None,
                    "last_investigation": None,
                    "recent_transaction_ids": [],
                    "recent_transactions": [],
                    "recent_evidence_ids": [],
                },
            }
        return cid, self._conversations[cid]

    def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        transaction_id: str | None = None,
        account_id: str | None = None,
        case_id: str | None = None,
        recent_tx_ids: list[str] | None = None,
        recent_transactions: list[dict[str, Any]] | None = None,
        investigation: Any | None = None,
        intent: str | None = None,
        evidence_ids: list[str] | None = None,
    ) -> None:
        cid, conv = self.get_or_create(conversation_id)
        conv["updated_at"] = time.time()
        conv["messages"].append({
            "role": role,
            "content": content,
            "timestamp": time.time(),
        })

        ctx = conv["context"]
        if transaction_id:
            ctx["last_transaction_id"] = str(transaction_id)
        if account_id:
            ctx["last_account_id"] = str(account_id)
        if case_id:
            ctx["last_case_id"] = str(case_id)
        if intent:
            ctx["last_intent"] = intent
        if investigation:
            ctx["last_investigation"] = investigation if isinstance(investigation, dict) else (
                investigation.model_dump() if hasattr(investigation, "model_dump") else str(investigation)
            )
        if recent_transactions:
            ctx["recent_transactions"] = list(recent_transactions)
            extracted_ids = [str(t.get("transaction_id")) for t in recent_transactions if t.get("transaction_id")]
            if extracted_ids:
                ctx["recent_transaction_ids"] = extracted_ids
                if not ctx["last_transaction_id"]:
                    ctx["last_transaction_id"] = extracted_ids[0]
        elif recent_tx_ids:
            ctx["recent_transaction_ids"] = list(recent_tx_ids)
            if not ctx["last_transaction_id"] and recent_tx_ids:
                ctx["last_transaction_id"] = recent_tx_ids[0]
        if evidence_ids:
            ctx["recent_evidence_ids"] = list(evidence_ids)

    def get_history(self, conversation_id: str, max_messages: int = 10) -> list[dict[str, str]]:
        if conversation_id not in self._conversations:
            return []
        msgs = self._conversations[conversation_id].get("messages", [])
        return [{"role": m["role"], "content": m["content"]} for m in msgs[-max_messages:]]

    def get_context(self, conversation_id: str) -> dict[str, Any]:
        if conversation_id not in self._conversations:
            return {}
        return dict(self._conversations[conversation_id].get("context", {}))


conversation_service = ConversationService()

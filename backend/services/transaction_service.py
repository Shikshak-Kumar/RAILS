from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.db.repositories.transaction_repository import transaction_repository
from backend.evidence.store import evidence_store
from backend.schemas.transaction import TransactionInput


class TransactionService:
    def __init__(self, repository: Any | None = None, evidence_store_ref: Any | None = None) -> None:
        self.repository = repository or transaction_repository
        self.evidence_store_ref = evidence_store_ref or evidence_store

    def create_transaction(self, payload: TransactionInput | dict[str, Any]) -> dict[str, Any]:
        if isinstance(payload, dict):
            payload = TransactionInput(
                transaction_id=str(payload.get('transaction_id') or payload.get('id') or 'tx-auto'),
                sender_id=str(payload.get('sender_id') or payload.get('sender_account') or 'unknown'),
                receiver_id=str(payload.get('receiver_id') or payload.get('receiver_account') or 'unknown'),
                amount=float(payload.get('amount') or payload.get('amount_paid') or 0.0),
                timestamp=payload.get('timestamp'),
                transaction_type=payload.get('transaction_type') or payload.get('payment_format'),
                currency=payload.get('currency') or payload.get('payment_currency'),
            )
        record = self.repository.upsert(payload)
        evidence = self.evidence_store_ref.add(
            evidence_id=f"ev-tx-{record.transaction_id}",
            request_id=f"req-{record.transaction_id}",
            tool_name='transaction_service',
            tool_arguments=payload.model_dump(mode='json') if hasattr(payload, 'model_dump') else payload,
            tool_output={'status': 'stored', 'transaction_id': record.transaction_id},
            model_name='transaction_service',
            kind='database',
        )
        return {'transaction_id': record.transaction_id, 'status': 'stored', 'evidence_id': evidence.evidence_id}

    def get_transaction(self, transaction_id: str) -> dict[str, Any]:
        item = self.repository.get(transaction_id)
        if item is None:
            return {'transaction_id': transaction_id, 'found': False}
        return {'transaction_id': transaction_id, 'found': True, 'transaction': item.model_dump(mode='json')}


transaction_service = TransactionService()

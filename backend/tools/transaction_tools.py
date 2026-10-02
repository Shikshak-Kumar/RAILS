from __future__ import annotations

from typing import Any

from backend.db.repositories.transaction_repository import transaction_repository
from backend.tools.registry import register_tool


@register_tool('get_transaction')
def get_transaction(transaction_id: str) -> dict[str, Any]:
    item = transaction_repository.get(transaction_id)
    if item is None:
        return {'found': False, 'transaction_id': transaction_id}
    return {'found': True, 'transaction': item.model_dump(mode='json')}


@register_tool('list_transactions')
def list_transactions(limit: int = 50, offset: int = 0) -> dict[str, Any]:
    items = transaction_repository.list(limit=limit, offset=offset)
    return {'count': len(items), 'items': [item.model_dump(mode='json') for item in items]}


@register_tool('upsert_transaction')
def upsert_transaction(payload: dict[str, Any]) -> dict[str, Any]:
    item = transaction_repository.upsert(payload)
    return {'transaction_id': item.transaction_id, 'status': 'stored'}

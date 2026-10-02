from __future__ import annotations

from typing import Any

from backend.db.repositories.transaction_repository import transaction_repository
from backend.tools.registry import register_tool


@register_tool('account_history')
def account_history(account_id: str, limit: int = 50, before: Any = None, **kwargs: Any) -> dict[str, Any]:
    history = transaction_repository.account_history(account_id, before=before, limit=limit)
    return {'account_id': account_id, 'history': history, 'count': len(history)}

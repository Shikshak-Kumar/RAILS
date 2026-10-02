from __future__ import annotations

from typing import Any

from backend.db.repositories.transaction_repository import transaction_repository
from backend.tools.registry import register_tool


@register_tool('account_history')
def account_history(account_id: str) -> dict[str, Any]:
    return {'account_id': account_id, 'history': transaction_repository.account_history(account_id)}

from __future__ import annotations

from typing import Any

from backend.ml.inference import predict_account_risk, predict_transaction_anomaly, predict_transaction_fraud
from backend.tools.registry import register_tool


@register_tool('fraud_check')
def fraud_check(transaction_id: str, sender_id: str, receiver_id: str, amount: float, timestamp: Any, **kwargs: Any) -> dict[str, Any]:
    return predict_transaction_fraud(
        transaction_id=transaction_id,
        sender_id=sender_id,
        receiver_id=receiver_id,
        amount=amount,
        timestamp=timestamp,
        sender_history=kwargs.get('sender_history'),
        receiver_history=kwargs.get('receiver_history'),
        pair_history=kwargs.get('pair_history'),
        currency=kwargs.get('currency'),
        transaction_type=kwargs.get('transaction_type'),
    )


@register_tool('anomaly_check')
def anomaly_check(transaction_id: str, sender_id: str, receiver_id: str, amount: float, timestamp: Any, **kwargs: Any) -> dict[str, Any]:
    return predict_transaction_anomaly(
        transaction_id=transaction_id,
        sender_id=sender_id,
        receiver_id=receiver_id,
        amount=amount,
        timestamp=timestamp,
        sender_history=kwargs.get('sender_history'),
        receiver_history=kwargs.get('receiver_history'),
        pair_history=kwargs.get('pair_history'),
        currency=kwargs.get('currency'),
        transaction_type=kwargs.get('transaction_type'),
    )


@register_tool('account_risk_check')
def account_risk_check(account_id: str, history: list[dict[str, Any]] | None = None, **kwargs: Any) -> dict[str, Any]:
    if history is None:
        from backend.db.repositories.transaction_repository import transaction_repository
        history = transaction_repository.account_history(account_id, limit=50)
    return predict_account_risk(account_id=account_id, history=history or [], **kwargs)


@register_tool('rules_check')
def rules_check(transaction_id: str, sender_id: str, receiver_id: str, amount: float, timestamp: Any, **kwargs: Any) -> dict[str, Any]:
    from backend.ml.rules import evaluate_transaction_rules
    return evaluate_transaction_rules(
        transaction_id=transaction_id,
        sender_id=sender_id,
        receiver_id=receiver_id,
        amount=amount,
        timestamp=timestamp,
        sender_history=kwargs.get('sender_history'),
        receiver_history=kwargs.get('receiver_history'),
        pair_history=kwargs.get('pair_history'),
    )

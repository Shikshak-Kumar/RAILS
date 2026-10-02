from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from backend.db.repositories.transaction_repository import transaction_repository
from backend.services.risk_service import risk_service

router = APIRouter(prefix="", tags=["risk"])


@router.get('/risk/signals')
def risk_signals() -> dict[str, object]:
    return {'signals': ['fraud_probability', 'anomaly_score', 'account_flow_pressure', 'liquidity_stress']}


@router.get('/risk/accounts/{account_id}')
def account_risk(account_id: str) -> dict[str, object]:
    result = risk_service.account_risk(account_id)
    return result


@router.get('/risk/transactions/{transaction_id}')
def transaction_risk(transaction_id: str) -> dict[str, object]:
    item = transaction_repository.get(transaction_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Transaction not found')
    result = risk_service.analyze_transaction(
        item,
    )
    return result.model_dump(mode='json')

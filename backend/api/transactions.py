from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.db.repositories.alert_repository import alert_repository
from backend.db.repositories.transaction_repository import transaction_repository
from backend.schemas.transaction import TransactionInput
from backend.services.risk_service import risk_service

router = APIRouter(prefix="", tags=["transactions"])


@router.get('/transactions')
def list_transactions(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = None,
) -> dict[str, object]:
    items = transaction_repository.list(limit=limit, offset=offset, search=search)
    total = transaction_repository.count_total()
    tx_ids = [tx.transaction_id for tx in items]
    alerts_map = alert_repository.get_alerts_by_txs(tx_ids)
    enriched = []
    for tx in items:
        tx_dict = tx.model_dump(mode='json')
        alert = alerts_map.get(tx.transaction_id)
        if alert:
            tx_dict['risk_assessment'] = {
                'transaction_id': tx.transaction_id,
                'fraud_probability': alert.get('fraud_probability') or 0.0,
                'anomaly_score': alert.get('anomaly_score') or 0.0,
                'risk_score': alert.get('risk_score') or 0.0,
                'risk_level': alert.get('risk_level') or 'LOW',
                'signals': alert.get('signals') or [],
                'evidence_ids': alert.get('evidence_ids') or [],
                'model_versions': [
                    {'model_name': 'fraud_model', 'version': 'v20261002074147', 'loaded_at': alert.get('created_at', '')},
                    {'model_name': 'anomaly_model', 'version': 'v20261002074147', 'loaded_at': alert.get('created_at', '')},
                ],
            }
        enriched.append(tx_dict)
    return {'items': enriched, 'count': len(enriched), 'total': total}


@router.get('/transactions/{transaction_id}')
def get_transaction(transaction_id: str) -> dict[str, object]:
    item = transaction_repository.get(transaction_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Transaction not found')
    return item.model_dump(mode='json')


@router.post('/transactions', status_code=status.HTTP_202_ACCEPTED)
def create_transaction(payload: TransactionInput) -> dict[str, object]:
    assessment = risk_service.analyze_transaction(payload)
    return {
        'status': 'accepted',
        'transaction_id': payload.transaction_id,
        'sender_id': payload.sender_id,
        'receiver_id': payload.receiver_id,
        'amount': payload.amount,
        'risk_level': assessment.risk_level,
        'risk_score': assessment.risk_score,
        'assessment': assessment.model_dump(mode='json'),
    }


@router.post('/risk/transactions/{transaction_id}/analyze')
def analyze_transaction(transaction_id: str, payload: TransactionInput | None = None) -> dict[str, object]:
    item = transaction_repository.get(transaction_id)
    if item is not None:
        payload = TransactionInput(
            transaction_id=item.transaction_id,
            sender_id=item.sender_id,
            receiver_id=item.receiver_id,
            amount=item.amount,
            timestamp=item.timestamp,
            transaction_type=item.transaction_type,
            currency=item.currency,
        )
    if payload is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Transaction payload required')
    assessment = risk_service.analyze_transaction(payload)
    return assessment.model_dump(mode='json')

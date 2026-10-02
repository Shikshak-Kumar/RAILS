from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.db.repositories.transaction_repository import transaction_repository
from backend.schemas.transaction import TransactionInput
from backend.services.risk_service import risk_service

router = APIRouter(prefix="", tags=["transactions"])


@router.get('/transactions')
def list_transactions(limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0)) -> dict[str, object]:
    items = transaction_repository.list(limit=limit, offset=offset)
    return {'items': [tx.model_dump(mode='json') for tx in items], 'count': len(items)}


@router.get('/transactions/{transaction_id}')
def get_transaction(transaction_id: str) -> dict[str, object]:
    item = transaction_repository.get(transaction_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Transaction not found')
    return item.model_dump(mode='json')


from fastapi import BackgroundTasks

@router.post('/transactions', status_code=status.HTTP_202_ACCEPTED)
def create_transaction(payload: TransactionInput, background_tasks: BackgroundTasks) -> dict[str, object]:
    tx = transaction_repository.upsert(payload)
    
    # Automatically trigger risk analysis in the background
    background_tasks.add_task(risk_service.analyze_transaction, payload)
    
    return {
        'status': 'accepted',
        'transaction_id': tx.transaction_id,
        'sender_id': tx.sender_id,
        'receiver_id': tx.receiver_id,
        'amount': tx.amount,
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

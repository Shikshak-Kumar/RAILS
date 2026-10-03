from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from backend.db.repositories.alert_repository import alert_repository
from backend.db.repositories.transaction_repository import transaction_repository
from backend.schemas.transaction import TransactionInput
from backend.services.risk_service import risk_service

router = APIRouter(prefix="", tags=["transactions"])


@router.get('/transactions')
def list_transactions(
    page: int | None = Query(None, ge=1),
    page_size: int | None = Query(None, ge=1, le=200),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: str | None = None,
) -> dict[str, object]:
    actual_page = page if isinstance(page, int) else None
    actual_page_size = page_size if isinstance(page_size, int) else None
    actual_limit = limit if isinstance(limit, int) else 50
    actual_offset = offset if isinstance(offset, int) else 0

    effective_limit = actual_page_size if actual_page_size is not None else actual_limit
    effective_offset = ((actual_page - 1) * effective_limit) if actual_page is not None else actual_offset
    current_page = (effective_offset // effective_limit) + 1 if effective_limit > 0 else 1

    items = transaction_repository.list(limit=effective_limit, offset=effective_offset, search=search)
    total = transaction_repository.count_total()
    tx_ids = [tx.transaction_id for tx in items]
    alerts_map = alert_repository.get_alerts_by_txs(tx_ids)
    enriched = []
    for tx in items:
        tx_dict = tx.model_dump(mode='json')
        alert = alerts_map.get(tx.transaction_id)
        cached = risk_service._canonical_risk_cache.get(tx.transaction_id)

        if alert:
            rlvl = str(alert.get('risk_level') or 'LOW').upper()
            rscore = float(alert.get('risk_score') or 0.0)
            fprob = float(alert.get('fraud_probability') or 0.0)
            ascore = float(alert.get('anomaly_score') or 0.0)
            sigs = list(alert.get('signals') or [])
            ev_ids = list(alert.get('evidence_ids') or [f"ev-{tx.transaction_id}"])
            created_at = alert.get('created_at', '')
        elif cached:
            rlvl = str(cached.get('risk_level') or 'LOW').upper()
            rscore = float(cached.get('risk_score') or 0.0)
            fprob = float(cached.get('fraud_probability') or 0.0)
            ascore = float(cached.get('anomaly_score') or 0.0)
            sigs = list(cached.get('signals') or [])
            ev_ids = list(cached.get('evidence_ids') or [f"ev-{tx.transaction_id}"])
            created_at = ''
        else:
            rlvl = 'LOW'
            rscore = 0.0
            fprob = 0.0
            ascore = 0.0
            sigs = []
            ev_ids = [f"ev-{tx.transaction_id}"]
            created_at = ''

        tx_dict['risk_level'] = rlvl
        tx_dict['risk_score'] = rscore
        tx_dict['fraud_probability'] = fprob
        tx_dict['anomaly_score'] = ascore
        tx_dict['signals'] = sigs
        tx_dict['risk_assessment'] = {
            'transaction_id': tx.transaction_id,
            'fraud_probability': fprob,
            'anomaly_score': ascore,
            'risk_score': rscore,
            'risk_level': rlvl,
            'signals': sigs,
            'evidence_ids': ev_ids,
            'model_versions': [
                {'model_name': 'fraud_model', 'version': 'v20261002074147', 'loaded_at': created_at},
                {'model_name': 'anomaly_model', 'version': 'v20261002074147', 'loaded_at': created_at},
            ],
        }
        enriched.append(tx_dict)
    return {
        'items': enriched,
        'count': len(enriched),
        'total': total,
        'page': current_page,
        'page_size': effective_limit,
        'has_next': (effective_offset + len(enriched)) < total,
        'has_previous': effective_offset > 0,
    }


@router.get('/transactions/{transaction_id}')
def get_transaction(transaction_id: str) -> dict[str, object]:
    item = transaction_repository.get(transaction_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Transaction not found')
    tx_dict = item.model_dump(mode='json')
    canonical = risk_service.get_canonical_risk(transaction_id, item)
    tx_dict['risk_level'] = canonical['risk_level']
    tx_dict['risk_score'] = canonical['risk_score']
    tx_dict['fraud_probability'] = canonical['fraud_probability']
    tx_dict['anomaly_score'] = canonical['anomaly_score']
    tx_dict['signals'] = canonical['signals']

    alert = alert_repository.get_alert_by_tx(transaction_id)
    created_at = alert.get('created_at', '') if alert else ''
    evidence_ids = alert.get('evidence_ids') if alert else [f"ev-{transaction_id}"]
    tx_dict['risk_assessment'] = {
        'transaction_id': transaction_id,
        'fraud_probability': canonical['fraud_probability'],
        'anomaly_score': canonical['anomaly_score'],
        'risk_score': canonical['risk_score'],
        'risk_level': canonical['risk_level'],
        'signals': canonical['signals'],
        'evidence_ids': evidence_ids or [],
        'model_versions': [
            {'model_name': 'fraud_model', 'version': 'v20261002074147', 'loaded_at': created_at},
            {'model_name': 'anomaly_model', 'version': 'v20261002074147', 'loaded_at': created_at},
        ],
    }
    return tx_dict


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

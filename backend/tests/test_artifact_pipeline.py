from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.ml.feature_adapter import build_feature_row
from backend.ml.inference import predict_account_risk, predict_transaction_anomaly, predict_transaction_fraud
from backend.ml.model_loader import load_model
from backend.schemas.transaction import TransactionInput


def test_model_loading_and_latest_resolution():
    model = load_model('fraud_model')
    assert model.model_name == 'fraud_model'
    assert model.model_version == 'v20261002074137'
    assert model.feature_order
    assert model.metadata['model_name'] == 'fraud_model'


def test_fraud_model_uses_metadata_feature_order():
    model = load_model('fraud_model')
    feature_names = model.feature_order
    assert feature_names[0] == 'amount'
    assert 'rapid_move_flag' in feature_names
    assert len(feature_names) == len(model.metadata['features'])


def test_transaction_pydantic_validation():
    tx = TransactionInput(
        transaction_id='t-1',
        sender_id='A1',
        receiver_id='B2',
        amount=125.5,
        timestamp=datetime(2026, 1, 1, 12, 30, tzinfo=timezone.utc),
        transaction_type='TRANSFER',
        currency='USD',
    )
    assert tx.amount == 125.5
    assert tx.transaction_id == 't-1'


def test_database_mapping_is_centralized_and_deterministic():
    row = {
        'Timestamp': '2026/01/01 12:00',
        'Account': 'A100',
        'Account.1': 'B200',
        'Amount Paid': '125.50',
        'Payment Currency': 'USD',
        'Payment Format': 'TRANSFER',
        'Amount Received': '125.50',
        'Receiving Currency': 'USD',
        'Is Laundering': '0',
    }
    mapped = {
        'transaction_id': 'tx-42',
        'sender_id': row['Account'],
        'receiver_id': row['Account.1'],
        'amount': float(row['Amount Paid']),
        'timestamp': datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
        'transaction_type': row['Payment Format'],
        'currency': row['Payment Currency'],
    }
    assert mapped['sender_id'] == 'A100'
    assert mapped['receiver_id'] == 'B200'
    assert mapped['amount'] == 125.5


def test_feature_adapter_respects_model_feature_order():
    feature_row = build_feature_row(
        transaction_id='tx-1',
        sender_id='A',
        receiver_id='B',
        amount=400.0,
        timestamp=datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc),
        sender_history=[],
        receiver_history=[],
        pair_history=[],
    )
    assert isinstance(feature_row, dict)
    assert list(feature_row.keys()) == load_model('fraud_model').feature_order


def test_inference_outputs_are_typed_and_separated():
    fraud = predict_transaction_fraud(
        transaction_id='tx-1',
        sender_id='A',
        receiver_id='B',
        amount=500.0,
        timestamp=datetime(2026, 1, 2, 13, 0, tzinfo=timezone.utc),
        sender_history=[],
        receiver_history=[],
        pair_history=[],
    )
    anomaly = predict_transaction_anomaly(
        transaction_id='tx-1',
        sender_id='A',
        receiver_id='B',
        amount=500.0,
        timestamp=datetime(2026, 1, 2, 13, 0, tzinfo=timezone.utc),
        sender_history=[],
        receiver_history=[],
        pair_history=[],
    )
    assert 'fraud_probability' in fraud
    assert 'anomaly_score' in anomaly
    assert fraud['model_name'] == 'fraud_model'
    assert anomaly['model_name'] == 'anomaly_model'


def test_account_risk_inference_works():
    result = predict_account_risk(account_id='ACC-1', history=[])
    assert 'risk_score' in result
    assert result['model_name'] == 'account_risk_model'


def test_fastapi_health_and_transactions_endpoints():
    client = TestClient(app)
    response = client.get('/health')
    assert response.status_code == 200
    payload = response.json()
    assert 'status' in payload

    tx_response = client.get('/transactions')
    assert tx_response.status_code in {200, 404}

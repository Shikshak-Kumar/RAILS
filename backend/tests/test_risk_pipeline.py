from __future__ import annotations

from datetime import datetime, timezone, timedelta
import pytest

from backend.db.repositories.alert_repository import alert_repository
from backend.db.repositories.transaction_repository import transaction_repository
from backend.ml.feature_adapter import build_feature_row
from backend.ml.inference import _as_frame, predict_transaction_anomaly, predict_transaction_fraud
from backend.ml.model_loader import load_model
from backend.schemas.transaction import TransactionInput
from backend.services.case_service import case_service
from backend.services.risk_service import risk_service


def test_1_normal_transaction_low_risk():
    """Test 1: Normal transaction -> low risk -> no alert created."""
    t_now = datetime(2026, 6, 1, 14, 0, tzinfo=timezone.utc)
    tx_input = TransactionInput(
        transaction_id="tx-normal-test-1",
        sender_id="acc-norm-sender",
        receiver_id="acc-norm-receiver",
        amount=25.0,
        timestamp=t_now,
        transaction_type="transfer",
        currency="USD",
    )
    # Sender has prior history with small amounts
    sender_history = [
        {"transaction_id": "h-1", "sender_id": "acc-norm-sender", "receiver_id": "other", "amount": 20.0, "timestamp": t_now - timedelta(days=2)},
        {"transaction_id": "h-2", "sender_id": "acc-norm-sender", "receiver_id": "other2", "amount": 30.0, "timestamp": t_now - timedelta(days=1)},
    ]
    pair_history = [
        {"transaction_id": "h-p1", "sender_id": "acc-norm-sender", "receiver_id": "acc-norm-receiver", "amount": 22.0, "timestamp": t_now - timedelta(days=1)}
    ]

    assessment = risk_service.analyze_transaction(
        tx_input,
        sender_history=sender_history,
        pair_history=pair_history,
    )

    assert assessment.risk_level == "LOW"
    assert assessment.analysis_status == "completed"
    # No alert should be created for LOW risk
    alert = alert_repository.get_alert_by_transaction_id("tx-normal-test-1") if hasattr(alert_repository, 'get_alert_by_transaction_id') else None
    if not alert:
        alerts = [a for a in alert_repository.list_alerts(limit=50) if a.get('transaction_id') == "tx-normal-test-1"]
        assert len(alerts) == 0


def test_2_high_risk_transaction_alert_and_case():
    """Test 2: High-risk transaction -> alert created -> case created and linked."""
    from uuid import uuid4
    t_now = datetime.now(timezone.utc)
    tx_id = f"tx-high-{uuid4().hex[:8]}"
    tx_input = TransactionInput(
        transaction_id=tx_id,
        sender_id="acc-high-sender",
        receiver_id="acc-high-receiver",
        amount=75000.0,
        timestamp=t_now,
        transaction_type="wire",
        currency="USD",
    )
    # Rapid layering history: 10 txns in past hour, recent huge inflow of 80000
    sender_history = [
        {"transaction_id": f"h-inflow-{i}", "sender_id": f"ext-{i}", "receiver_id": "acc-high-sender", "amount": 80000.0, "timestamp": t_now - timedelta(minutes=10)}
        for i in range(1)
    ] + [
        {"transaction_id": f"h-burst-{i}", "sender_id": "acc-high-sender", "receiver_id": f"rx-{i}", "amount": 1000.0, "timestamp": t_now - timedelta(minutes=i + 1)}
        for i in range(6)
    ]

    assessment = risk_service.analyze_transaction(
        tx_input,
        sender_history=sender_history,
        receiver_history=[],
        pair_history=[],
    )

    assert assessment.risk_level in ("HIGH", "CRITICAL")
    assert assessment.risk_score >= 0.55

    # Check alert was created
    alert = alert_repository.get_alert_by_tx(tx_id)
    if not alert:
        alerts = [a for a in alert_repository.list_alerts(limit=100) if a.get('transaction_id') == tx_id]
        assert len(alerts) == 1
        alert = alerts[0]
    assert alert is not None
    assert alert['risk_level'] == assessment.risk_level
    assert alert['case_id'] is not None

    # Check case exists and is linked
    case = case_service.get_case(alert['case_id'])
    assert case.get('status') == 'OPEN'


def test_3_new_counterparty():
    """Test 3: No previous A -> B pair -> pair_count = 0 -> no crash -> correct new_counterparty signal."""
    t_now = datetime(2026, 6, 3, 10, 0, tzinfo=timezone.utc)
    features = build_feature_row(
        transaction_id="tx-new-pair-test",
        sender_id="acc-alice",
        receiver_id="acc-bob",
        amount=50.0,
        timestamp=t_now,
        sender_history=[],
        receiver_history=[],
        pair_history=[],
    )
    assert features['is_new_pair'] == 1.0
    assert features['pair_hist_cnt'] == 0.0

    # Running fraud check produces new_counterparty signal
    fraud = predict_transaction_fraud(
        transaction_id="tx-new-pair-test",
        sender_id="acc-alice",
        receiver_id="acc-bob",
        amount=50.0,
        timestamp=t_now,
        sender_history=[],
        receiver_history=[],
        pair_history=[],
    )
    assert "new_counterparty" in fraud['signals']


def test_4_existing_pair():
    """Test 4: A -> B has historical transactions -> pair_count calculated correctly."""
    t_now = datetime(2026, 6, 4, 11, 0, tzinfo=timezone.utc)
    pair_history = [
        {"transaction_id": "p-1", "sender_id": "acc-a", "receiver_id": "acc-b", "amount": 10.0, "timestamp": t_now - timedelta(days=3)},
        {"transaction_id": "p-2", "sender_id": "acc-a", "receiver_id": "acc-b", "amount": 15.0, "timestamp": t_now - timedelta(days=2)},
        {"transaction_id": "p-3", "sender_id": "acc-b", "receiver_id": "acc-a", "amount": 20.0, "timestamp": t_now - timedelta(days=1)},
    ]
    features = build_feature_row(
        transaction_id="tx-existing-pair",
        sender_id="acc-a",
        receiver_id="acc-b",
        amount=25.0,
        timestamp=t_now,
        sender_history=[],
        receiver_history=[],
        pair_history=pair_history,
    )
    assert features['is_new_pair'] == 0.0
    assert features['pair_hist_cnt'] == 3.0
    assert features['reverse_pair_cnt'] == 1.0


def test_5_self_contamination_prevented():
    """Test 5: Verify that the current transaction does NOT contaminate its own features."""
    t_target = datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc)
    
    # Prior transactions
    prior_txns = [
        {"transaction_id": "p-1", "sender_id": "acc-clean", "receiver_id": "other", "amount": 100.0, "timestamp": t_target - timedelta(hours=2)},
        {"transaction_id": "p-2", "sender_id": "acc-clean", "receiver_id": "other", "amount": 100.0, "timestamp": t_target - timedelta(hours=1)},
    ]
    
    # Contaminated history including the transaction itself and a future transaction
    contaminated_history = list(prior_txns) + [
        {"transaction_id": "tx-target", "sender_id": "acc-clean", "receiver_id": "acc-dest", "amount": 999999.0, "timestamp": t_target},
        {"transaction_id": "future-tx", "sender_id": "acc-clean", "receiver_id": "acc-dest", "amount": 888888.0, "timestamp": t_target + timedelta(hours=1)},
    ]
    
    features = build_feature_row(
        transaction_id="tx-target",
        sender_id="acc-clean",
        receiver_id="acc-dest",
        amount=999999.0,
        timestamp=t_target,
        sender_history=contaminated_history,
        receiver_history=[],
        pair_history=[{"transaction_id": "tx-target", "sender_id": "acc-clean", "receiver_id": "acc-dest", "amount": 999999.0, "timestamp": t_target}],
    )
    
    # s_hist_cnt MUST be 2 (only prior_txns), NOT 4
    assert features['s_hist_cnt'] == 2.0
    # s_cnt_24h MUST be 2, NOT 4
    assert features['s_cnt_24h'] == 2.0
    # pair_hist_cnt MUST be 0 (the current transaction at T must not count towards history < T)
    assert features['pair_hist_cnt'] == 0.0
    assert features['is_new_pair'] == 1.0


def test_6_missing_feature_detection():
    """Test 6: Verify that missing required features are detected rather than silently converted to zero."""
    incomplete_values = {"amount": 100.0}
    required_features = ["amount", "missing_required_feature_x"]
    
    with pytest.raises(ValueError) as excinfo:
        _as_frame(required_features, incomplete_values, "tx-fail-test", "test_model")
    assert "missing_required_feature_x" in str(excinfo.value)


def test_7_anomaly_model_invoked():
    """Test 7: Verify that the actual saved anomaly model is invoked and calculates a valid score."""
    t_now = datetime(2026, 6, 7, 10, 0, tzinfo=timezone.utc)
    res = predict_transaction_anomaly(
        transaction_id="tx-anomaly-test",
        sender_id="acc-anom-s",
        receiver_id="acc-anom-r",
        amount=150.0,
        timestamp=t_now,
        sender_history=[],
        receiver_history=[],
        pair_history=[],
    )
    assert res['model_name'] == 'anomaly_model'
    assert res['model_version'] == 'v20261002074147'
    assert 'anomaly_score' in res
    assert 0.0 <= res['anomaly_score'] <= 1.0
    assert res['risk_level'] in ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')


def test_8_duplicate_processing_idempotent():
    """Test 8: Analyzing the same transaction twice must not create duplicate alerts or cases."""
    from uuid import uuid4
    t_now = datetime.now(timezone.utc)
    tx_id = f"tx-dup-test-{uuid4().hex[:8]}"
    tx_input = TransactionInput(
        transaction_id=tx_id,
        sender_id="acc-dup-sender",
        receiver_id="acc-dup-receiver",
        amount=95000.0,
        timestamp=t_now,
        transaction_type="wire",
        currency="USD",
    )
    # Burst history causing HIGH risk
    sender_history = [
        {"transaction_id": f"burst-{i}", "sender_id": "acc-dup-sender", "receiver_id": f"rx-{i}", "amount": 500.0, "timestamp": t_now - timedelta(minutes=i + 1)}
        for i in range(8)
    ]
    
    # Process first time
    assessment1 = risk_service.analyze_transaction(
        tx_input,
        sender_history=sender_history,
        receiver_history=[],
        pair_history=[],
    )
    assert assessment1.risk_level in ('HIGH', 'CRITICAL')
    
    # Process second time
    assessment2 = risk_service.analyze_transaction(
        tx_input,
        sender_history=sender_history,
        receiver_history=[],
        pair_history=[],
    )
    assert assessment2.risk_level == assessment1.risk_level
    
    # Verify exactly ONE alert exists in the repository for this transaction_id
    alert = alert_repository.get_alert_by_tx(tx_id)
    assert alert is not None
    alerts = [a for a in alert_repository.list_alerts(limit=100) if a.get('transaction_id') == tx_id]
    assert len(alerts) == 1

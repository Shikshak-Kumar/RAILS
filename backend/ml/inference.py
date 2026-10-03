from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from backend.ml.feature_adapter import build_feature_row
from backend.ml.model_loader import load_model


def _as_frame(feature_order: list[str], values: dict[str, Any], transaction_id: str, model_name: str) -> pd.DataFrame:
    missing = [name for name in feature_order if name not in values]
    if missing:
        import logging
        logging.getLogger(__name__).error(
            f"Missing required model features for {model_name} (txn={transaction_id}): {missing}"
        )
        raise ValueError(f"Missing required model features for {model_name}: {missing}")
    normalized = {name: float(values[name]) for name in feature_order}
    return pd.DataFrame([normalized], columns=feature_order)


def _risk_level(score: float, thresholds: dict[str, float]) -> str:
    if thresholds.get('critical', 0.0) and score >= float(thresholds['critical']):
        return 'CRITICAL'
    if thresholds.get('high', 0.0) and score >= float(thresholds['high']):
        return 'HIGH'
    if thresholds.get('medium', 0.0) and score > float(thresholds['medium']):
        return 'MEDIUM'
    return 'LOW'


def predict_transaction_fraud(
    *,
    transaction_id: str,
    sender_id: str,
    receiver_id: str,
    amount: float,
    timestamp: datetime,
    sender_history: list[dict[str, Any]] | None = None,
    receiver_history: list[dict[str, Any]] | None = None,
    pair_history: list[dict[str, Any]] | None = None,
    currency: str | None = None,
    transaction_type: str | None = None,
) -> dict[str, Any]:
    model = load_model('fraud_model')
    feature_row = build_feature_row(
        transaction_id=transaction_id,
        sender_id=sender_id,
        receiver_id=receiver_id,
        amount=amount,
        timestamp=timestamp,
        sender_history=sender_history,
        receiver_history=receiver_history,
        pair_history=pair_history,
        feature_order=model.feature_order,
        transaction_type=transaction_type,
        currency=currency,
    )
    frame = _as_frame(model.feature_order, feature_row, transaction_id, 'fraud_model')
    model_dict = model.pipeline

    raw_score = float(model_dict['model'].predict_proba(frame)[:, 1][0])
    if 'calibrator' in model_dict and model_dict['calibrator'] is not None:
        calibrated = model_dict['calibrator'].predict(np.asarray([raw_score], dtype=float))
        fraud_probability = float(np.clip(calibrated[0], 0.0, 1.0))
    else:
        fraud_probability = float(np.clip(raw_score, 0.0, 1.0))

    thresholds = model.metadata.get('thresholds', {})
    risk_level = _risk_level(fraud_probability, thresholds)

    signals: list[str] = []
    signal_details: list[dict[str, Any]] = []

    s_cnt_1h = float(feature_row.get('s_cnt_1h', 0))
    s_cnt_24h = float(feature_row.get('s_cnt_24h', 0))
    if s_cnt_1h >= 5 or s_cnt_24h >= 20:
        signals.append('high_transaction_velocity')
        signal_details.append({'signal': 'high_transaction_velocity', 'value': s_cnt_1h, 'threshold': 5})

    s_fanout = float(feature_row.get('s_fanout_ratio', 0))
    s_out_deg = float(feature_row.get('s_out_deg', 0))
    if s_fanout >= 0.8 and s_out_deg >= 5:
        signals.append('high_fanout')
        signal_details.append({'signal': 'high_fanout', 'value': round(s_fanout, 2), 'threshold': 0.8})

    r_fanin = float(feature_row.get('r_fanin_ratio', 0))
    r_in_deg = float(feature_row.get('r_in_deg', 0))
    if r_fanin >= 0.8 and r_in_deg >= 5:
        signals.append('high_fanin')
        signal_details.append({'signal': 'high_fanin', 'value': round(r_fanin, 2), 'threshold': 0.8})

    if float(feature_row.get('is_new_pair', 0)) == 1:
        signals.append('new_counterparty')
        signal_details.append({'signal': 'new_counterparty', 'value': 0, 'threshold': 1})

    s_amt_z = float(feature_row.get('s_amt_z', 0))
    if s_amt_z >= 3.0:
        signals.append('amount_above_sender_baseline')
        signal_details.append({'signal': 'amount_above_sender_baseline', 'value': round(s_amt_z, 2), 'threshold': 3.0})

    if float(feature_row.get('rapid_move_flag', 0)) == 1:
        signals.append('rapid_outflow')
        signal_details.append({'signal': 'rapid_outflow', 'value': 1, 'threshold': 1})

    if float(feature_row.get('is_night', 0)) == 1:
        signals.append('nighttime_transaction')
        signal_details.append({'signal': 'nighttime_transaction', 'value': feature_row.get('hour'), 'threshold': '22:00-06:00'})

    high_thresh = float(thresholds.get('high', 0.1325))
    if fraud_probability >= high_thresh:
        signals.append('elevated_fraud_probability')
        signal_details.append({'signal': 'elevated_fraud_probability', 'value': round(fraud_probability, 4), 'threshold': round(high_thresh, 4)})

    return {
        'transaction_id': transaction_id,
        'fraud_probability': fraud_probability,
        'risk_level': risk_level,
        'signals': signals,
        'signal_details': signal_details,
        'model_name': 'fraud_model',
        'model_version': model.model_version,
        'scoring_method': model.metadata.get('scoring_method', 'supervised_classifier'),
        'feature_summary': feature_row,
    }


def predict_transaction_anomaly(
    *,
    transaction_id: str,
    sender_id: str,
    receiver_id: str,
    amount: float,
    timestamp: datetime,
    sender_history: list[dict[str, Any]] | None = None,
    receiver_history: list[dict[str, Any]] | None = None,
    pair_history: list[dict[str, Any]] | None = None,
    currency: str | None = None,
    transaction_type: str | None = None,
) -> dict[str, Any]:
    model = load_model('anomaly_model')
    feature_row = build_feature_row(
        transaction_id=transaction_id,
        sender_id=sender_id,
        receiver_id=receiver_id,
        amount=amount,
        timestamp=timestamp,
        sender_history=sender_history,
        receiver_history=receiver_history,
        pair_history=pair_history,
        feature_order=model.feature_order,
        transaction_type=transaction_type,
        currency=currency,
    )
    frame = _as_frame(model.feature_order, feature_row, transaction_id, 'anomaly_model')

    pipe = model.pipeline['model'] if isinstance(model.pipeline, dict) and 'model' in model.pipeline else model.pipeline
    raw_decision = float(pipe.decision_function(frame)[0])

    score_grid = model.pipeline.get('score_grid') if isinstance(model.pipeline, dict) else None
    grid = model.pipeline.get('grid') if isinstance(model.pipeline, dict) else None

    if score_grid is not None and grid is not None:
        percentile = float(np.interp(raw_decision, score_grid, grid))
        anomaly_score = float(np.clip(1.0 - percentile, 0.0, 1.0))
    else:
        anomaly_score = float(np.clip(1.0 / (1.0 + np.exp(raw_decision * 10.0)), 0.0, 1.0))

    thresholds = model.metadata.get('thresholds', {})
    risk_level = _risk_level(anomaly_score, thresholds)

    signals: list[str] = []
    signal_details: list[dict[str, Any]] = []

    med_thresh = float(thresholds.get('medium', 0.95))
    high_thresh = float(thresholds.get('high', 0.99))
    crit_thresh = float(thresholds.get('critical', 0.999))

    if anomaly_score >= crit_thresh:
        signals.append('critical_anomaly_outlier')
        signal_details.append({'signal': 'critical_anomaly_outlier', 'value': round(anomaly_score, 4), 'threshold': crit_thresh})
    elif anomaly_score >= high_thresh:
        signals.append('high_anomaly_percentile')
        signal_details.append({'signal': 'high_anomaly_percentile', 'value': round(anomaly_score, 4), 'threshold': high_thresh})
    elif anomaly_score >= med_thresh:
        signals.append('behavioral_anomaly_detected')
        signal_details.append({'signal': 'behavioral_anomaly_detected', 'value': round(anomaly_score, 4), 'threshold': med_thresh})

    return {
        'transaction_id': transaction_id,
        'anomaly_score': anomaly_score,
        'risk_level': risk_level,
        'signals': signals,
        'signal_details': signal_details,
        'model_name': 'anomaly_model',
        'model_version': model.model_version,
        'scoring_method': model.metadata.get('scoring_method', 'unsupervised_anomaly'),
        'feature_summary': feature_row,
    }


def predict_account_risk(
    *,
    account_id: str,
    history: list[dict[str, Any]] | None = None,
    before: datetime | None = None,
) -> dict[str, Any]:
    model = load_model('account_risk_model')
    
    if before is not None:
        from backend.ml.feature_adapter import _parse_ts
        before_dt = _parse_ts(before)
        clean_history = [item for item in (history or []) if _parse_ts(item.get('timestamp')) < before_dt]
    else:
        clean_history = list(history or [])

    total_in = sum(float(item.get('amount', 0.0)) for item in clean_history if item.get('receiver_id') == account_id)
    total_out = sum(float(item.get('amount', 0.0)) for item in clean_history if item.get('sender_id') == account_id)
    transactions = len(clean_history)
    net_flow = total_in - total_out
    volatility = math.sqrt(sum((float(item.get('amount', 0.0)) - (total_in / max(1, transactions))) ** 2 for item in clean_history) / max(1, transactions)) if clean_history else 0.0
    flow_pressure = min(1.0, (total_out / max(1.0, total_in + total_out))) if (total_in + total_out) > 0 else 0.0
    
    score = min(1.0, 0.35 * flow_pressure + 0.2 * (min(transactions, 100) / 100.0) + 0.25 * (max(0.0, net_flow) / max(1.0, abs(net_flow) + total_in + total_out)) + 0.2 * (volatility / max(1.0, total_out + total_in)))
    score = float(max(0.0, min(1.0, score)))

    thresholds = model.metadata.get('thresholds', {})
    risk_level = _risk_level(score, thresholds)

    signals: list[str] = []
    signal_details: list[dict[str, Any]] = []

    if flow_pressure >= 0.8 and (total_out >= 5000.0 or transactions >= 5):
        signals.append('account_flow_pressure')
        signal_details.append({'signal': 'account_flow_pressure', 'value': round(flow_pressure, 2), 'threshold': 0.8})

    if transactions >= 20:
        signals.append('velocity_instability')
        signal_details.append({'signal': 'velocity_instability', 'value': transactions, 'threshold': 20})

    if score >= float(thresholds.get('high', 0.750)):
        signals.append('high_account_risk')
        signal_details.append({'signal': 'high_account_risk', 'value': round(score, 3), 'threshold': round(float(thresholds.get('high', 0.750)), 3)})

    return {
        'account_id': account_id,
        'risk_score': score,
        'risk_level': risk_level,
        'signals': signals,
        'signal_details': signal_details,
        'model_name': 'account_risk_model',
        'model_version': model.model_version,
        'evidence_ids': [],
    }


def predict_liquidity_risk(
    *,
    account_id: str,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    model = load_model('liquidity_model')
    history = history or []
    recent = [float(item.get('amount', 0.0)) for item in history if item.get('sender_id') == account_id]
    inflow = sum(float(item.get('amount', 0.0)) for item in history if item.get('receiver_id') == account_id)
    outflow = sum(float(item.get('amount', 0.0)) for item in history if item.get('sender_id') == account_id)
    net_24h = inflow - outflow
    outflow_spike = outflow / max(1.0, inflow + outflow)
    score = min(1.0, 0.6 * outflow_spike + 0.25 * max(0.0, -net_24h / max(1.0, inflow + outflow)) + 0.15 * (len(recent) / 50.0))
    risk_level = _risk_level(score, model.metadata.get('thresholds', {}))
    return {
        'account': account_id,
        'liquidity_score': score,
        'risk_level': risk_level,
        'signals': ['outflow_spike', 'funding_pressure', 'insufficient_buffer'],
        'metrics_used': ['inflow', 'outflow', 'net_24h', 'outflow_spike'],
        'model_name': 'liquidity_model',
        'model_version': model.model_version,
        'evidence_ids': [],
    }


def predict_credit_risk(
    *,
    entity_id: str,
    features: dict[str, float] | None = None,
) -> dict[str, Any]:
    model = load_model('credit_model')
    feature_values = features or {}
    ordered = {name: float(feature_values.get(name, 0.0)) for name in model.feature_order}
    frame = pd.DataFrame([ordered], columns=model.feature_order)
    raw_score = float(model.pipeline['model'].predict_proba(frame)[:, 1][0])
    if 'calibrator' in model.pipeline:
        calibrated = model.pipeline['calibrator'].predict(np.asarray([raw_score], dtype=float))
        score = float(calibrated[0])
    else:
        score = raw_score
    risk_level = _risk_level(score, model.metadata.get('thresholds', {}))
    return {
        'entity_id': entity_id,
        'credit_score': score,
        'risk_level': risk_level,
        'signals': ['synthetic_credit_risk', 'debt_pressure'],
        'model_name': 'credit_model',
        'model_version': model.model_version,
        'evidence_ids': [],
    }

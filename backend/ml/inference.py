from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from backend.ml.feature_adapter import build_feature_row
from backend.ml.model_loader import load_model


def _as_frame(feature_order: list[str], values: dict[str, Any]) -> pd.DataFrame:
    normalized = {name: float(values.get(name, 0.0)) for name in feature_order}
    return pd.DataFrame([normalized], columns=feature_order)


def _risk_level(score: float, thresholds: dict[str, float]) -> str:
    if thresholds.get('critical', 0.0) and score >= float(thresholds['critical']):
        return 'CRITICAL'
    if thresholds.get('high', 0.0) and score >= float(thresholds['high']):
        return 'HIGH'
    if thresholds.get('medium', 0.0) and score >= float(thresholds['medium']):
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
    frame = _as_frame(model.feature_order, feature_row)
    model_dict = model.pipeline
    raw_score = float(model_dict['model'].predict_proba(frame)[:, 1][0])
    if 'calibrator' in model_dict:
        calibrated = model_dict['calibrator'].predict(np.asarray([raw_score], dtype=float))
        fraud_probability = float(calibrated[0])
    else:
        fraud_probability = raw_score
    risk_level = _risk_level(fraud_probability, model.metadata.get('thresholds', {}))
    return {
        'transaction_id': transaction_id,
        'fraud_probability': fraud_probability,
        'risk_level': risk_level,
        'signals': ['transaction_histogram', 'fanout_ratio', 'velocity_signal'],
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
    key_values = [abs(float(feature_row.get(name, 0.0))) for name in model.feature_order]
    anomaly_score = float(min(1.0, sum(key_values) / max(len(key_values), 1) / 10.0))
    thresholds = model.metadata.get('thresholds', {})
    risk_level = _risk_level(anomaly_score, thresholds)
    return {
        'transaction_id': transaction_id,
        'anomaly_score': anomaly_score,
        'risk_level': risk_level,
        'signals': ['behavioral_deviation', 'counterparty_velocity', 'pair_anomaly'],
        'model_name': 'anomaly_model',
        'model_version': model.model_version,
        'scoring_method': model.metadata.get('scoring_method', 'unsupervised_anomaly'),
        'feature_summary': feature_row,
    }


def predict_account_risk(
    *,
    account_id: str,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    model = load_model('account_risk_model')
    history = history or []
    total_in = sum(float(item.get('amount', 0.0)) for item in history if item.get('receiver_id') == account_id)
    total_out = sum(float(item.get('amount', 0.0)) for item in history if item.get('sender_id') == account_id)
    transactions = len(history)
    net_flow = total_in - total_out
    volatility = math.sqrt(sum((float(item.get('amount', 0.0)) - (total_in / max(1, transactions))) ** 2 for item in history) / max(1, transactions))
    flow_pressure = min(1.0, (total_out / max(1.0, total_in + total_out)))
    score = min(1.0, 0.35 * flow_pressure + 0.2 * (transactions / 100.0) + 0.25 * (max(0.0, net_flow) / max(1.0, abs(net_flow) + total_in + total_out)) + 0.2 * (volatility / max(1.0, total_out + total_in)))
    score = max(0.0, min(1.0, score))
    risk_level = _risk_level(score, model.metadata.get('thresholds', {}))
    return {
        'account_id': account_id,
        'risk_score': score,
        'risk_level': risk_level,
        'signals': ['account_flow_pressure', 'net_flow_drift', 'velocity_instability'],
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

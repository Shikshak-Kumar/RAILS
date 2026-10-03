from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.db.persistence import get_write_connection


class AlertRepository:
    def __init__(self) -> None:
        self._alerts: dict[str, dict[str, Any]] = {}
        self._tx_to_alert: dict[str, str] = {}

    def create_or_get_alert(
        self,
        *,
        transaction_id: str,
        risk_level: str,
        risk_score: float,
        fraud_probability: float | None = None,
        anomaly_score: float | None = None,
        signals: list[str] | None = None,
        evidence_ids: list[str] | None = None,
        case_id: str | None = None,
        status: str = 'OPEN',
    ) -> dict[str, Any]:
        signals_json = json.dumps(signals or [])
        evidence_ids_json = json.dumps(evidence_ids or [])
        alert_id = f"alt-{uuid4().hex[:10]}"

        if transaction_id in self._tx_to_alert:
            existing_id = self._tx_to_alert[transaction_id]
            if existing_id in self._alerts:
                existing = dict(self._alerts[existing_id])
                if case_id and not existing.get('case_id'):
                    existing['case_id'] = case_id
                    self._alerts[existing_id] = existing
                return existing

        try:
            with get_write_connection() as conn:
                from psycopg.rows import dict_row
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        INSERT INTO alerts (
                            alert_id, transaction_id, risk_level, risk_score,
                            fraud_probability, anomaly_score, signals, evidence_ids,
                            status, case_id, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (transaction_id) DO UPDATE
                            SET case_id = COALESCE(alerts.case_id, EXCLUDED.case_id),
                                updated_at = CURRENT_TIMESTAMP
                        RETURNING alert_id, transaction_id, risk_level, risk_score,
                                  fraud_probability, anomaly_score, signals, evidence_ids,
                                  status, case_id, created_at, updated_at;
                        """,
                        (
                            alert_id,
                            transaction_id,
                            risk_level,
                            float(risk_score),
                            float(fraud_probability) if fraud_probability is not None else None,
                            float(anomaly_score) if anomaly_score is not None else None,
                            signals_json,
                            evidence_ids_json,
                            status,
                            case_id,
                        ),
                    )
                    row = cur.fetchone()
                    conn.commit()
                    if row:
                        res = dict(row)
                        if isinstance(res.get('signals'), str):
                            res['signals'] = json.loads(res['signals'])
                        if isinstance(res.get('evidence_ids'), str):
                            res['evidence_ids'] = json.loads(res['evidence_ids'])
                        if isinstance(res.get('created_at'), datetime):
                            res['created_at'] = res['created_at'].isoformat()
                        if isinstance(res.get('updated_at'), datetime):
                            res['updated_at'] = res['updated_at'].isoformat()
                        self._alerts[res['alert_id']] = res
                        self._tx_to_alert[transaction_id] = res['alert_id']
                        return res
        except Exception as e:
            pass

        record = {
            'alert_id': alert_id,
            'transaction_id': transaction_id,
            'risk_level': risk_level,
            'risk_score': float(risk_score),
            'fraud_probability': float(fraud_probability) if fraud_probability is not None else None,
            'anomaly_score': float(anomaly_score) if anomaly_score is not None else None,
            'signals': list(signals or []),
            'evidence_ids': list(evidence_ids or []),
            'status': status,
            'case_id': case_id,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat(),
        }
        self._alerts[alert_id] = record
        self._tx_to_alert[transaction_id] = alert_id
        return record

    def get_alert(self, alert_id: str) -> dict[str, Any] | None:
        if alert_id in self._alerts:
            return self._alerts[alert_id]
        try:
            with get_write_connection() as conn:
                from psycopg.rows import dict_row
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT * FROM alerts WHERE alert_id = %s", (alert_id,))
                    row = cur.fetchone()
                    if row:
                        res = dict(row)
                        if isinstance(res.get('signals'), str):
                            res['signals'] = json.loads(res['signals'])
                        if isinstance(res.get('evidence_ids'), str):
                            res['evidence_ids'] = json.loads(res['evidence_ids'])
                        if isinstance(res.get('created_at'), datetime):
                            res['created_at'] = res['created_at'].isoformat()
                        if isinstance(res.get('updated_at'), datetime):
                            res['updated_at'] = res['updated_at'].isoformat()
                        self._alerts[alert_id] = res
                        return res
        except Exception:
            pass
    def get_alert_by_tx(self, transaction_id: str) -> dict[str, Any] | None:
        if transaction_id in self._tx_to_alert:
            aid = self._tx_to_alert[transaction_id]
            return self.get_alert(aid)
        try:
            with get_write_connection() as conn:
                from psycopg.rows import dict_row
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT * FROM alerts WHERE transaction_id = %s", (transaction_id,))
                    row = cur.fetchone()
                    if row:
                        res = dict(row)
                        if isinstance(res.get('signals'), str):
                            res['signals'] = json.loads(res['signals'])
                        if isinstance(res.get('evidence_ids'), str):
                            res['evidence_ids'] = json.loads(res['evidence_ids'])
                        if isinstance(res.get('created_at'), datetime):
                            res['created_at'] = res['created_at'].isoformat()
                        if isinstance(res.get('updated_at'), datetime):
                            res['updated_at'] = res['updated_at'].isoformat()
                        self._alerts[res['alert_id']] = res
                        self._tx_to_alert[transaction_id] = res['alert_id']
                        return res
        except Exception:
            pass
        return None
    def get_alerts_by_txs(self, tx_ids: list[str]) -> dict[str, dict[str, Any]]:
        if not tx_ids:
            return {}
        results: dict[str, dict[str, Any]] = {}
        missing_ids = []
        for tid in tx_ids:
            if tid in self._tx_to_alert:
                aid = self._tx_to_alert[tid]
                alert = self._alerts.get(aid)
                if alert:
                    results[tid] = alert
            else:
                missing_ids.append(tid)

        if missing_ids:
            try:
                with get_write_connection() as conn:
                    from psycopg.rows import dict_row
                    with conn.cursor(row_factory=dict_row) as cur:
                        cur.execute("SELECT * FROM alerts WHERE transaction_id = ANY(%s)", (missing_ids,))
                        for row in cur.fetchall():
                            res = dict(row)
                            if isinstance(res.get('signals'), str):
                                res['signals'] = json.loads(res['signals'])
                            if isinstance(res.get('evidence_ids'), str):
                                res['evidence_ids'] = json.loads(res['evidence_ids'])
                            if isinstance(res.get('created_at'), datetime):
                                res['created_at'] = res['created_at'].isoformat()
                            if isinstance(res.get('updated_at'), datetime):
                                res['updated_at'] = res['updated_at'].isoformat()
                            results[res['transaction_id']] = res
                            self._alerts[res['alert_id']] = res
                            self._tx_to_alert[res['transaction_id']] = res['alert_id']
            except Exception:
                pass
        return results

    def list_alerts(self, *, limit: int = 50, offset: int = 0, risk_level: str | None = None) -> list[dict[str, Any]]:
        try:
            with get_write_connection() as conn:
                from psycopg.rows import dict_row
                with conn.cursor(row_factory=dict_row) as cur:
                    query = "SELECT * FROM alerts"
                    params: list[Any] = []
                    if risk_level:
                        query += " WHERE risk_level = %s"
                        params.append(risk_level)
                    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                    params.extend([limit, offset])
                    cur.execute(query, tuple(params))
                    rows = cur.fetchall()
                    results = []
                    for row in rows:
                        res = dict(row)
                        if isinstance(res.get('signals'), str):
                            res['signals'] = json.loads(res['signals'])
                        if isinstance(res.get('evidence_ids'), str):
                            res['evidence_ids'] = json.loads(res['evidence_ids'])
                        if isinstance(res.get('created_at'), datetime):
                            res['created_at'] = res['created_at'].isoformat()
                        if isinstance(res.get('updated_at'), datetime):
                            res['updated_at'] = res['updated_at'].isoformat()
                        results.append(res)
                    return results
        except Exception:
            pass

        items = list(self._alerts.values())
        if risk_level:
            items = [a for a in items if a.get('risk_level') == risk_level]
        return items[offset: offset + limit]

    def count_by_risk(self, risk_level: str | None = None) -> int:
        try:
            with get_write_connection() as conn:
                with conn.cursor() as cur:
                    if risk_level:
                        cur.execute("SELECT count(*) FROM alerts WHERE risk_level = %s", (risk_level,))
                    else:
                        cur.execute("SELECT count(*) FROM alerts")
                    row = cur.fetchone()
                    if row:
                        return int(row[0])
        except Exception:
            pass

        if risk_level:
            return sum(1 for a in self._alerts.values() if a.get('risk_level') == risk_level)
        return len(self._alerts)

    def link_case(self, alert_id: str, case_id: str) -> None:
        try:
            with get_write_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE alerts SET case_id = %s, updated_at = CURRENT_TIMESTAMP WHERE alert_id = %s",
                        (case_id, alert_id),
                    )
                conn.commit()
        except Exception:
            pass
        if alert_id in self._alerts:
            self._alerts[alert_id]['case_id'] = case_id


alert_repository = AlertRepository()

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.db.persistence import get_write_connection

VALID_TRANSITIONS = {
    'OPEN': ['UNDER_REVIEW', 'APPROVED', 'REJECTED', 'FILED', 'CLOSED'],
    'UNDER_REVIEW': ['PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'FILED', 'CLOSED'],
    'PENDING_APPROVAL': ['APPROVED', 'REJECTED', 'FILED', 'CLOSED'],
    'APPROVED': ['FILED', 'CLOSED'],
    'REJECTED': ['CLOSED', 'OPEN'],
    'FILED': ['CLOSED'],
    'CLOSED': ['OPEN'],
}


class CaseService:
    def __init__(self) -> None:
        self._in_memory_cases: dict[str, dict[str, Any]] = {}

    def _extract_tx_id(self, summary: str) -> str:
        match = re.search(r'(?:TX|Transaction)\s*[:#-]?\s*([a-zA-Z0-9_-]+)', summary, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _format_case(self, row: dict[str, Any], alerts_map: dict[str, Any] | None = None) -> dict[str, Any]:
        cid = str(row.get('case_id', ''))
        summary = str(row.get('summary', ''))
        tx_id = str(row.get('transaction_id') or self._extract_tx_id(summary))
        risk_level = str(row.get('risk_level') or '') or None
        if not risk_level:
            if alerts_map and tx_id in alerts_map:
                risk_level = alerts_map[tx_id].get('risk_level')
            elif tx_id:
                try:
                    from backend.services.risk_service import risk_service
                    cached = risk_service._canonical_risk_cache.get(tx_id)
                    if cached:
                        risk_level = cached.get('risk_level')
                except Exception:
                    pass
        if not risk_level:
            risk_level = 'CRITICAL' if 'CRITICAL' in summary.upper() else ('HIGH' if 'HIGH' in summary.upper() else ('MEDIUM' if 'MEDIUM' in summary.upper() else 'LOW'))
        
        created_at = row.get('created_at')
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        elif not created_at:
            created_at = datetime.now(timezone.utc).isoformat()

        updated_at = row.get('updated_at')
        if isinstance(updated_at, datetime):
            updated_at = updated_at.isoformat()
        elif not updated_at:
            updated_at = created_at

        return {
            'id': cid,
            'case_id': cid,
            'title': summary,
            'summary': summary,
            'description': summary,
            'status': str(row.get('status', 'OPEN')),
            'risk_level': risk_level,
            'assigned_to': 'Compliance Officer',
            'created_at': created_at,
            'updated_at': updated_at,
            'transaction_id': tx_id,
            'evidence_ids': [f"ev-{cid}"],
            'signals': [],
        }

    def list_cases(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        try:
            with get_write_connection() as conn:
                from psycopg.rows import dict_row
                with conn.cursor(row_factory=dict_row) as cur:
                    query = "SELECT case_id, summary, status, created_at, updated_at FROM cases"
                    clauses = []
                    params: list[Any] = []
                    if status and status != 'ALL':
                        clauses.append("status = %s")
                        params.append(status)
                    if search:
                        clauses.append("(case_id ILIKE %s OR summary ILIKE %s)")
                        params.extend([f"%{search}%", f"%{search}%"])
                    if clauses:
                        query += " WHERE " + " AND ".join(clauses)
                    query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                    params.extend([limit, offset])
                    cur.execute(query, tuple(params))
                    rows = cur.fetchall()
                    dict_rows = [dict(row) for row in rows]
                    tx_ids = [str(r.get('transaction_id') or self._extract_tx_id(r.get('summary', ''))) for r in dict_rows]
                    tx_ids = [t for t in tx_ids if t]
                    alerts_map: dict[str, Any] = {}
                    if tx_ids:
                        try:
                            from backend.db.repositories.alert_repository import alert_repository
                            alerts_map = alert_repository.get_alerts_by_txs(tx_ids)
                        except Exception:
                            pass
                    return [self._format_case(r, alerts_map=alerts_map) for r in dict_rows]
        except Exception as e:
            print(f"Error listing cases: {e}")
            items = list(self._in_memory_cases.values())
            if status and status != 'ALL':
                items = [c for c in items if c['status'] == status]
            if search:
                s_lower = search.lower()
                items = [c for c in items if s_lower in c['case_id'].lower() or s_lower in c['summary'].lower()]
            return [self._format_case(c) for c in items[offset: offset + limit]]

    def create_case(
        self,
        summary: str,
        *,
        status: str = 'OPEN',
        case_id: str | None = None,
        transaction_id: str | None = None,
        alert_id: str | None = None,
    ) -> dict[str, Any]:
        if transaction_id:
            try:
                with get_write_connection() as conn:
                    from psycopg.rows import dict_row
                    with conn.cursor(row_factory=dict_row) as cur:
                        cur.execute("SELECT case_id, summary, status, created_at, updated_at FROM cases WHERE summary LIKE %s", (f"%{transaction_id}%",))
                        existing = cur.fetchone()
                        if existing:
                            res = self._format_case(dict(existing))
                            res['transaction_id'] = transaction_id
                            return res
            except Exception:
                pass
            for c in self._in_memory_cases.values():
                if transaction_id in c.get('summary', ''):
                    return self._format_case(c)

        cid = case_id or f"case-{uuid4().hex[:8]}"
        try:
            with get_write_connection() as conn:
                from psycopg.rows import dict_row
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        INSERT INTO cases (case_id, summary, status)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (case_id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
                        RETURNING case_id, summary, status, created_at, updated_at
                        """,
                        (cid, summary, status)
                    )
                    row = cur.fetchone()
                    conn.commit()
                    if row:
                        res = self._format_case(dict(row))
                        if transaction_id:
                            res['transaction_id'] = transaction_id
                        self._in_memory_cases[cid] = res
                        return res
        except Exception as e:
            print(f"Error creating case: {e}")

        now_iso = datetime.now(timezone.utc).isoformat()
        res = {
            'case_id': cid,
            'summary': summary,
            'status': status,
            'created_at': now_iso,
            'updated_at': now_iso,
            'transaction_id': transaction_id or self._extract_tx_id(summary),
        }
        self._in_memory_cases[cid] = res
        return self._format_case(res)

    def count_cases(self, status: str | None = 'OPEN') -> int:
        try:
            with get_write_connection() as conn:
                with conn.cursor() as cur:
                    if status and status != 'ALL':
                        cur.execute("SELECT count(*) FROM cases WHERE status = %s", (status,))
                    else:
                        cur.execute("SELECT count(*) FROM cases")
                    row = cur.fetchone()
                    if row:
                        return int(row[0])
        except Exception:
            pass

        if status and status != 'ALL':
            return sum(1 for c in self._in_memory_cases.values() if c.get('status') == status)
        return len(self._in_memory_cases)

    def get_case(self, case_id: str) -> dict[str, Any]:
        try:
            with get_write_connection() as conn:
                from psycopg.rows import dict_row
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT case_id, summary, status, created_at, updated_at FROM cases WHERE case_id = %s", (case_id,))
                    row = cur.fetchone()
                    if row:
                        return self._format_case(dict(row))
        except Exception as e:
            print(f"Error getting case: {e}")

        if case_id in self._in_memory_cases:
            return self._format_case(self._in_memory_cases[case_id])
        return {'case_id': case_id, 'status': 'NOT_FOUND'}

    def update_case(self, case_id: str, new_status: str) -> dict[str, Any]:
        case = self.get_case(case_id)
        if case.get('status') == 'NOT_FOUND':
            return case

        current_status = case['status']
        allowed = VALID_TRANSITIONS.get(current_status, [])
        if new_status not in allowed and new_status != current_status:
            raise ValueError(f"Invalid transition from {current_status} to {new_status}")

        try:
            with get_write_connection() as conn:
                from psycopg.rows import dict_row
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        """
                        UPDATE cases
                        SET status = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE case_id = %s
                        RETURNING case_id, summary, status, created_at, updated_at
                        """,
                        (new_status, case_id)
                    )
                    row = cur.fetchone()
                    conn.commit()
                    if row:
                        res = self._format_case(dict(row))
                        self._in_memory_cases[case_id] = res
                        return res
        except Exception as e:
            print(f"Error updating case: {e}")
            raise e

        if case_id in self._in_memory_cases:
            self._in_memory_cases[case_id]['status'] = new_status
            self._in_memory_cases[case_id]['updated_at'] = datetime.now(timezone.utc).isoformat()
            return self._format_case(self._in_memory_cases[case_id])

        case['status'] = new_status
        return case


case_service = CaseService()

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from backend.db.persistence import ensure_schema, get_write_connection


class ReportRepository:

    def __init__(self) -> None:
        self._reports: dict[str, dict[str, Any]] = {}
        self._db_ready = False
        try:
            ensure_schema()
            self._db_ready = True
        except Exception as e:
            print(f"Warning: Write DB not available for reports: {e}")

    def create_report(
        self,
        *,
        case_id: str,
        title: str,
        body: str,
        report_id: str | None = None,
        report_type: str = 'STR',
        status: str = 'DRAFT',
        evidence_ids: list[str] | None = None,
        structured_data: dict[str, Any] | None = None,
        approved_by: str | None = None,
    ) -> dict[str, Any]:
        rid = report_id or f"rep-{uuid4().hex[:8]}"
        ev_ids = evidence_ids or []
        sd = structured_data or {}

        if self._db_ready:
            try:
                with get_write_connection() as conn:
                    from psycopg.rows import dict_row
                    with conn.cursor(row_factory=dict_row) as cur:
                        cur.execute(
                            """
                            INSERT INTO reports (
                                report_id, case_id, type, title, status, body,
                                evidence_ids, structured_data, approved_by
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                            ON CONFLICT (report_id) DO UPDATE SET
                                title = EXCLUDED.title,
                                body = EXCLUDED.body,
                                status = EXCLUDED.status,
                                evidence_ids = EXCLUDED.evidence_ids,
                                structured_data = EXCLUDED.structured_data,
                                approved_by = EXCLUDED.approved_by,
                                updated_at = CURRENT_TIMESTAMP
                            RETURNING *
                            """,
                            (
                                rid,
                                case_id,
                                report_type,
                                title,
                                status,
                                body,
                                json.dumps(ev_ids),
                                json.dumps(sd),
                                approved_by,
                            ),
                        )
                        row = cur.fetchone()
                        conn.commit()
                        if row:
                            res = self._format_row(dict(row))
                            self._reports[rid] = res
                            return res
            except Exception as e:
                print(f"DB write error for report: {e}")

        now_iso = datetime.now(timezone.utc).isoformat()
        record = {
            'report_id': rid,
            'case_id': case_id,
            'type': report_type,
            'title': title,
            'status': status,
            'body': body,
            'evidence_ids': ev_ids,
            'structured_data': sd,
            'approved_by': approved_by,
            'created_at': now_iso,
            'updated_at': now_iso,
        }
        self._reports[rid] = record
        return record

    def get_report(self, report_id: str) -> dict[str, Any] | None:
        if self._db_ready:
            try:
                with get_write_connection() as conn:
                    from psycopg.rows import dict_row
                    with conn.cursor(row_factory=dict_row) as cur:
                        cur.execute("SELECT * FROM reports WHERE report_id = %s", (report_id,))
                        row = cur.fetchone()
                        if row:
                            return self._format_row(dict(row))
            except Exception as e:
                print(f"DB read error for report: {e}")
        return self._reports.get(report_id)

    def update_report_status(
        self,
        report_id: str,
        status: str,
        *,
        approved_by: str | None = None,
    ) -> dict[str, Any] | None:
        if self._db_ready:
            try:
                with get_write_connection() as conn:
                    from psycopg.rows import dict_row
                    with conn.cursor(row_factory=dict_row) as cur:
                        if approved_by is not None:
                            cur.execute(
                                """
                                UPDATE reports
                                SET status = %s, approved_by = %s, updated_at = CURRENT_TIMESTAMP
                                WHERE report_id = %s
                                RETURNING *
                                """,
                                (status, approved_by, report_id),
                            )
                        else:
                            cur.execute(
                                """
                                UPDATE reports
                                SET status = %s, updated_at = CURRENT_TIMESTAMP
                                WHERE report_id = %s
                                RETURNING *
                                """,
                                (status, report_id),
                            )
                        row = cur.fetchone()
                        conn.commit()
                        if row:
                            res = self._format_row(dict(row))
                            self._reports[report_id] = res
                            return res
            except Exception as e:
                print(f"DB update error for report: {e}")

        if report_id in self._reports:
            self._reports[report_id]['status'] = status
            if approved_by is not None:
                self._reports[report_id]['approved_by'] = approved_by
            self._reports[report_id]['updated_at'] = datetime.now(timezone.utc).isoformat()
            return self._reports[report_id]
        return None

    def list_reports(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
        case_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if self._db_ready:
            try:
                with get_write_connection() as conn:
                    from psycopg.rows import dict_row
                    with conn.cursor(row_factory=dict_row) as cur:
                        query = "SELECT * FROM reports"
                        clauses = []
                        params: list[Any] = []
                        if status:
                            clauses.append("status = %s")
                            params.append(status)
                        if case_id:
                            clauses.append("case_id = %s")
                            params.append(case_id)
                        if clauses:
                            query += " WHERE " + " AND ".join(clauses)
                        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
                        params.extend([limit, offset])

                        cur.execute(query, tuple(params))
                        rows = cur.fetchall()
                        return [self._format_row(dict(row)) for row in rows]
            except Exception as e:
                print(f"DB list error for reports: {e}")

        items = list(self._reports.values())
        if status:
            items = [r for r in items if r.get('status') == status]
        if case_id:
            items = [r for r in items if r.get('case_id') == case_id]
        return items[offset: offset + limit]

    def count_reports(self, status: str | None = None) -> int:
        if self._db_ready:
            try:
                with get_write_connection() as conn:
                    with conn.cursor() as cur:
                        if status:
                            cur.execute("SELECT count(*) FROM reports WHERE status = %s", (status,))
                        else:
                            cur.execute("SELECT count(*) FROM reports")
                        row = cur.fetchone()
                        if row:
                            return int(row[0])
            except Exception:
                pass

        if status:
            return sum(1 for r in self._reports.values() if r.get('status') == status)
        return len(self._reports)

    def _format_row(self, row: dict[str, Any]) -> dict[str, Any]:
        if isinstance(row.get('evidence_ids'), str):
            try:
                row['evidence_ids'] = json.loads(row['evidence_ids'])
            except Exception:
                row['evidence_ids'] = []
        elif row.get('evidence_ids') is None:
            row['evidence_ids'] = []

        if isinstance(row.get('structured_data'), str):
            try:
                row['structured_data'] = json.loads(row['structured_data'])
            except Exception:
                row['structured_data'] = {}
        elif not row.get('structured_data'):
            row['structured_data'] = {}

        if isinstance(row.get('created_at'), datetime):
            row['created_at'] = row['created_at'].isoformat()
        if isinstance(row.get('updated_at'), datetime):
            row['updated_at'] = row['updated_at'].isoformat()
        return row


report_repository = ReportRepository()

from __future__ import annotations

from uuid import uuid4

from backend.db.persistence import get_write_connection

VALID_TRANSITIONS = {
    'OPEN': ['UNDER_REVIEW'],
    'UNDER_REVIEW': ['PENDING_APPROVAL'],
    'PENDING_APPROVAL': ['CLOSED'],
    'CLOSED': []
}

class CaseService:
    def list_cases(self) -> list[dict[str, str]]:
        try:
            with get_write_connection() as conn:
                from psycopg.rows import dict_row
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT case_id, summary, status FROM cases ORDER BY created_at DESC")
                    return [dict(row) for row in cur.fetchall()]
        except Exception as e:
            print(f"Error listing cases: {e}")
            return []

    def create_case(self, summary: str, *, status: str = 'OPEN') -> dict[str, str]:
        case_id = f"case-{uuid4().hex[:8]}"
        try:
            with get_write_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO cases (case_id, summary, status) VALUES (%s, %s, %s)",
                        (case_id, summary, status)
                    )
                conn.commit()
        except Exception as e:
            print(f"Error creating case: {e}")
        return {'case_id': case_id, 'summary': summary, 'status': status}

    def get_case(self, case_id: str) -> dict[str, str]:
        try:
            with get_write_connection() as conn:
                from psycopg.rows import dict_row
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute("SELECT case_id, summary, status FROM cases WHERE case_id = %s", (case_id,))
                    row = cur.fetchone()
                    if row:
                        return dict(row)
        except Exception as e:
            print(f"Error getting case: {e}")
        return {'case_id': case_id, 'status': 'NOT_FOUND'}

    def update_case(self, case_id: str, new_status: str) -> dict[str, str]:
        case = self.get_case(case_id)
        if case.get('status') == 'NOT_FOUND':
            return case

        current_status = case['status']
        if new_status not in VALID_TRANSITIONS.get(current_status, []):
            raise ValueError(f"Invalid transition from {current_status} to {new_status}")

        try:
            with get_write_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE cases SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE case_id = %s",
                        (new_status, case_id)
                    )
                conn.commit()
            case['status'] = new_status
            return case
        except Exception as e:
            print(f"Error updating case: {e}")
            raise e

case_service = CaseService()

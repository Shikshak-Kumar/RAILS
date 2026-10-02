from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.db.models import EvidenceRecord, TransactionRecord
from backend.db.persistence import ensure_schema, get_connection, get_database_url
from backend.schemas.transaction import TransactionInput


def _parse_timestamp(value: Any) -> datetime:
    if value is None:
        raise ValueError('timestamp is required')
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        clean = value.strip()
        for fmt in ('%Y-%m-%d %H:%M:%S%z', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M', '%Y/%m/%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S'):
            try:
                return datetime.strptime(clean, fmt)
            except ValueError:
                continue
        try:
            return datetime.fromisoformat(clean.replace('Z', '+00:00'))
        except ValueError as exc:  # pragma: no cover - fallback
            raise ValueError(f'Unsupported timestamp format: {value!r}') from exc
    raise TypeError(f'Unsupported timestamp type: {type(value)!r}')


class TransactionRepository:
    def __init__(self) -> None:
        self._transactions: dict[str, TransactionRecord] = {}
        self._evidence: dict[str, EvidenceRecord] = {}
        self._db_ready = False
        from backend.db.persistence import get_write_url
        self._database_url = get_write_url()
        if self._database_url and not self._database_url.startswith('sqlite'):
            try:
                ensure_schema()
                self._db_ready = True
            except Exception:
                self._db_ready = False

    @staticmethod
    def map_db_row(row: dict[str, Any]) -> dict[str, Any]:
        sender_id = (
            row.get('sender_id')
            or row.get('Account')
            or row.get('account')
            or row.get('sender_account')
            or row.get('from_account')
        )
        receiver_id = (
            row.get('receiver_id')
            or row.get('Account.1')
            or row.get('receiver_account')
            or row.get('to_account')
        )
        amount = row.get('amount')
        if amount is None:
            amount = row.get('Amount Paid') or row.get('amount_paid') or row.get('Amount Received') or row.get('amount_received')
        currency = row.get('currency') or row.get('Payment Currency') or row.get('payment_currency') or row.get('Currency')
        transaction_type = row.get('transaction_type') or row.get('Payment Format') or row.get('payment_format') or row.get('Type')
        timestamp_raw = row.get('timestamp') or row.get('Timestamp') or row.get('created_at')
        timestamp = _parse_timestamp(timestamp_raw)
        transaction_id = row.get('transaction_id') or row.get('id') or f"tx-{len(row)}"

        return {
            'transaction_id': str(transaction_id),
            'sender_id': str(sender_id),
            'receiver_id': str(receiver_id),
            'amount': float(amount),
            'timestamp': timestamp,
            'transaction_type': str(transaction_type) if transaction_type is not None else None,
            'currency': str(currency) if currency is not None else None,
        }

    def _normalize_payload(self, payload: TransactionInput | TransactionRecord | dict[str, Any]) -> TransactionRecord:
        if isinstance(payload, TransactionInput):
            return TransactionRecord(
                transaction_id=payload.transaction_id,
                sender_id=payload.sender_id,
                receiver_id=payload.receiver_id,
                amount=payload.amount,
                timestamp=payload.timestamp,
                transaction_type=payload.transaction_type,
                currency=payload.currency,
            )
        if isinstance(payload, TransactionRecord):
            return payload
        mapped = self.map_db_row(payload)
        return TransactionRecord(**mapped)

    def _persist_to_db(self, record: TransactionRecord) -> None:
        if not self._db_ready:
            return
        from backend.db.persistence import get_write_connection
        try:
            with get_write_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO transactions (
                            timestamp, from_bank, sender_account, to_bank, receiver_account,
                            amount_received, receiving_currency, amount_paid, payment_currency,
                            payment_format, is_laundering
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (
                            record.timestamp,
                            None,
                            record.sender_id,
                            None,
                            record.receiver_id,
                            None,
                            record.currency,
                            record.amount,
                            record.currency,
                            record.transaction_type,
                            bool(record.is_laundering or False),
                        ),
                    )
        except Exception as e:
            print(f"Failed to persist to write DB: {e}")

    def upsert(self, payload: TransactionInput | TransactionRecord | dict[str, Any]) -> TransactionRecord:
        record = self._normalize_payload(payload)
        self._transactions[record.transaction_id] = record
        self._persist_to_db(record)
        return record

    def get(self, transaction_id: str) -> TransactionRecord | None:
        if transaction_id in self._transactions:
            return self._transactions[transaction_id]
        
        try:
            with get_connection() as connection:
                from psycopg.rows import dict_row
                with connection.cursor(row_factory=dict_row) as cursor:
                    # Convert string transaction_id back to int if possible, 
                    # assuming the frontend might prefix it or use raw strings
                    try:
                        db_id = int(str(transaction_id).replace('tx-', ''))
                    except ValueError:
                        return None
                        
                    cursor.execute(
                        """
                        SELECT id, timestamp, from_bank, sender_account, to_bank, receiver_account,
                               amount_received, receiving_currency, amount_paid, payment_currency,
                               payment_format, is_laundering
                        FROM transactions WHERE id = %s
                        """, 
                        (db_id,)
                    )
                    row = cursor.fetchone()
                    if row:
                        row['transaction_id'] = str(row['id'])
                        return self._normalize_payload(row)
        except Exception as e:
            print(f"DB read error for get: {e}")
        return None

    def list(self, *, limit: int = 50, offset: int = 0) -> list[TransactionRecord]:
        try:
            with get_connection() as connection:
                from psycopg.rows import dict_row
                with connection.cursor(row_factory=dict_row) as cursor:
                    cursor.execute(
                        """
                        SELECT id, timestamp, from_bank, sender_account, to_bank, receiver_account,
                               amount_received, receiving_currency, amount_paid, payment_currency,
                               payment_format, is_laundering
                        FROM transactions 
                        ORDER BY timestamp DESC 
                        LIMIT %s OFFSET %s
                        """, 
                        (limit, offset)
                    )
                    rows = cursor.fetchall()
            
            results = []
            for row in rows:
                row['transaction_id'] = str(row['id'])
                results.append(self._normalize_payload(row))
            return results
        except Exception as e:
            print(f"DB read error for list: {e}")
            items = list(self._transactions.values())
            return items[offset: offset + limit]

    def append_evidence(self, evidence: EvidenceRecord) -> EvidenceRecord:
        self._evidence[evidence.evidence_id] = evidence
        return evidence

    def get_evidence(self, evidence_id: str) -> EvidenceRecord | None:
        return self._evidence.get(evidence_id)

    def account_history(self, account_id: str) -> list[dict[str, Any]]:
        history: list[dict[str, Any]] = []
        for tx in self._transactions.values():
            if tx.sender_id == account_id or tx.receiver_id == account_id:
                history.append({
                    'sender_id': tx.sender_id,
                    'receiver_id': tx.receiver_id,
                    'amount': tx.amount,
                    'timestamp': tx.timestamp,
                })
        history.sort(key=lambda item: item.get('timestamp'))
        return history


transaction_repository = TransactionRepository()

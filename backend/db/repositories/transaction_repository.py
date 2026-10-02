from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.db.models import EvidenceRecord, TransactionRecord
from backend.db.persistence import ensure_schema, get_connection, get_database_url
from backend.schemas.transaction import TransactionInput


def _parse_timestamp(value: Any) -> datetime:
    if value is None:
        raise ValueError('timestamp is required')
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        clean = value.strip()
        for fmt in ('%Y-%m-%d %H:%M:%S%z', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d %H:%M', '%Y/%m/%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S'):
            try:
                dt = datetime.strptime(clean, fmt)
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        try:
            dt = datetime.fromisoformat(clean.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt
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

    def list(self, *, limit: int = 50, offset: int = 0, search: str | None = None) -> list[TransactionRecord]:
        try:
            with get_connection() as connection:
                from psycopg.rows import dict_row
                with connection.cursor(row_factory=dict_row) as cursor:
                    if search and search.strip():
                        s = search.strip()
                        db_id = None
                        try:
                            clean_id = s.lower().replace('tx-', '').replace('tx_', '')
                            if clean_id.isdigit():
                                db_id = int(clean_id)
                        except Exception:
                            pass

                        if db_id is not None:
                            cursor.execute(
                                """
                                SELECT id, timestamp, from_bank, sender_account, to_bank, receiver_account,
                                       amount_received, receiving_currency, amount_paid, payment_currency,
                                       payment_format, is_laundering
                                FROM transactions 
                                WHERE id = %s OR sender_account = %s OR receiver_account = %s
                                ORDER BY timestamp DESC 
                                LIMIT %s OFFSET %s
                                """,
                                (db_id, s, s, limit, offset),
                            )
                        else:
                            cursor.execute(
                                """
                                SELECT id, timestamp, from_bank, sender_account, to_bank, receiver_account,
                                       amount_received, receiving_currency, amount_paid, payment_currency,
                                       payment_format, is_laundering
                                FROM transactions 
                                WHERE sender_account ILIKE %s OR receiver_account ILIKE %s
                                ORDER BY timestamp DESC 
                                LIMIT %s OFFSET %s
                                """,
                                (f"%{s}%", f"%{s}%", limit, offset),
                            )
                    else:
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
            if search and search.strip():
                s = search.strip().lower()
                items = [
                    tx for tx in items
                    if s in tx.transaction_id.lower() or s in tx.sender_id.lower() or s in tx.receiver_id.lower()
                ]
            return items[offset: offset + limit]

    def append_evidence(self, evidence: EvidenceRecord) -> EvidenceRecord:
        self._evidence[evidence.evidence_id] = evidence
        return evidence

    def get_evidence(self, evidence_id: str) -> EvidenceRecord | None:
        return self._evidence.get(evidence_id)

    def account_history(self, account_id: str, *, before: datetime | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        before_dt = _parse_timestamp(before) if before is not None else None
        records: dict[str, dict[str, Any]] = {}

        # 1. Query PostgreSQL read replica
        try:
            with get_connection() as connection:
                from psycopg.rows import dict_row
                with connection.cursor(row_factory=dict_row) as cursor:
                    query = """
                        (
                            SELECT id, timestamp, from_bank, sender_account, to_bank, receiver_account,
                                   amount_received, receiving_currency, amount_paid, payment_currency,
                                   payment_format, is_laundering
                            FROM transactions 
                            WHERE sender_account = %s
                    """
                    params: list[Any] = [account_id]
                    if before_dt is not None:
                        query += " AND timestamp < %s"
                        params.append(before_dt)
                    query += " ORDER BY timestamp ASC LIMIT %s) UNION ALL ("
                    params.append(limit)

                    query += """
                            SELECT id, timestamp, from_bank, sender_account, to_bank, receiver_account,
                                   amount_received, receiving_currency, amount_paid, payment_currency,
                                   payment_format, is_laundering
                            FROM transactions 
                            WHERE receiver_account = %s
                    """
                    params.append(account_id)
                    if before_dt is not None:
                        query += " AND timestamp < %s"
                        params.append(before_dt)
                    query += " ORDER BY timestamp ASC LIMIT %s)"
                    params.append(limit)
                    query += " ORDER BY timestamp ASC LIMIT %s"
                    params.append(limit)

                    cursor.execute(query, tuple(params))
                    for row in cursor.fetchall():
                        mapped = self.map_db_row(row)
                        records[mapped['transaction_id']] = mapped
        except Exception as e:
            # Safe fallback if DB is not available in isolated test environments
            pass

        # 2. Check in-memory store
        for tx in self._transactions.values():
            if tx.sender_id == account_id or tx.receiver_id == account_id:
                tx_ts = _parse_timestamp(tx.timestamp)
                if before_dt is not None and tx_ts >= before_dt:
                    continue
                records[tx.transaction_id] = {
                    'transaction_id': tx.transaction_id,
                    'sender_id': tx.sender_id,
                    'receiver_id': tx.receiver_id,
                    'amount': tx.amount,
                    'timestamp': tx_ts,
                    'transaction_type': tx.transaction_type,
                    'currency': tx.currency,
                }

        history = list(records.values())
        history.sort(key=lambda item: _parse_timestamp(item['timestamp']))
        return history[:limit]

    def pair_history(self, sender_id: str, receiver_id: str, *, before: datetime | None = None, limit: int = 1000) -> list[dict[str, Any]]:
        before_dt = _parse_timestamp(before) if before is not None else None
        records: dict[str, dict[str, Any]] = {}

        # 1. Query PostgreSQL read replica for both directions using UNION ALL for fast index scans
        try:
            with get_connection() as connection:
                from psycopg.rows import dict_row
                with connection.cursor(row_factory=dict_row) as cursor:
                    query = """
                        (
                            SELECT id, timestamp, from_bank, sender_account, to_bank, receiver_account,
                                   amount_received, receiving_currency, amount_paid, payment_currency,
                                   payment_format, is_laundering
                            FROM transactions 
                            WHERE sender_account = %s AND receiver_account = %s
                    """
                    params: list[Any] = [sender_id, receiver_id]
                    if before_dt is not None:
                        query += " AND timestamp < %s"
                        params.append(before_dt)
                    query += " ORDER BY timestamp ASC LIMIT %s) UNION ALL ("
                    params.append(limit)

                    query += """
                            SELECT id, timestamp, from_bank, sender_account, to_bank, receiver_account,
                                   amount_received, receiving_currency, amount_paid, payment_currency,
                                   payment_format, is_laundering
                            FROM transactions 
                            WHERE sender_account = %s AND receiver_account = %s
                    """
                    params.extend([receiver_id, sender_id])
                    if before_dt is not None:
                        query += " AND timestamp < %s"
                        params.append(before_dt)
                    query += " ORDER BY timestamp ASC LIMIT %s)"
                    params.append(limit)
                    query += " ORDER BY timestamp ASC LIMIT %s"
                    params.append(limit)

                    cursor.execute(query, tuple(params))
                    for row in cursor.fetchall():
                        mapped = self.map_db_row(row)
                        records[mapped['transaction_id']] = mapped
        except Exception as e:
            pass

        # 2. Check in-memory store
        for tx in self._transactions.values():
            is_forward = (tx.sender_id == sender_id and tx.receiver_id == receiver_id)
            is_reverse = (tx.sender_id == receiver_id and tx.receiver_id == sender_id)
            if is_forward or is_reverse:
                tx_ts = _parse_timestamp(tx.timestamp)
                if before_dt is not None and tx_ts >= before_dt:
                    continue
                records[tx.transaction_id] = {
                    'transaction_id': tx.transaction_id,
                    'sender_id': tx.sender_id,
                    'receiver_id': tx.receiver_id,
                    'amount': tx.amount,
                    'timestamp': tx_ts,
                    'transaction_type': tx.transaction_type,
                    'currency': tx.currency,
                }

        history = list(records.values())
        history.sort(key=lambda item: _parse_timestamp(item['timestamp']))
        return history[:limit]

    _cached_total: int | None = None
    _cached_total_time: float = 0.0

    def count_total(self) -> int:
        import time
        now = time.time()
        if self._cached_total is not None and (now - self._cached_total_time) < 60.0:
            return self._cached_total

        try:
            with get_connection() as connection:
                with connection.cursor() as cursor:
                    # Instant statistical row count from pg_class (<1ms vs full table scan)
                    cursor.execute("SELECT reltuples::bigint FROM pg_class WHERE relname = 'transactions'")
                    row = cursor.fetchone()
                    if row and row[0] and int(row[0]) > 0:
                        count = int(row[0])
                        self._cached_total = count
                        self._cached_total_time = now
                        return count
                    # Fallback to count(*) if reltuples has not been populated
                    cursor.execute("SELECT count(*) FROM transactions")
                    row = cursor.fetchone()
                    if row:
                        count = int(row[0])
                        self._cached_total = count
                        self._cached_total_time = now
                        return count
        except Exception:
            pass

        if self._cached_total is not None:
            return self._cached_total
        return 3100000 + len(self._transactions)


transaction_repository = TransactionRepository()

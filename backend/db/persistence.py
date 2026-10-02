from __future__ import annotations

from pathlib import Path
from typing import Any

import psycopg

from backend.config import READ_DB_URL, WRITE_DB_URL

ROOT_DIR = Path(__file__).resolve().parents[2]


def get_read_url() -> str:
    """Connection URL for the read replica (contains transactions)."""
    return READ_DB_URL


def get_write_url() -> str:
    """Connection URL for the write database."""
    return WRITE_DB_URL


# Keep a backward-compatible alias used by the repository layer
def get_database_url() -> str:
    """Returns the read DB URL (primary source of transaction data)."""
    return get_read_url()


def ensure_schema() -> None:
    """Apply schema migrations against the write database."""
    schema_sql = (ROOT_DIR / 'database' / 'schema.sql').read_text(encoding='utf-8')
    with psycopg.connect(get_write_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_sql)


def get_connection() -> Any:
    """Return a read-replica connection (transactions live here)."""
    return psycopg.connect(get_read_url())


def get_write_connection() -> Any:
    """Return a write-database connection for inserts/updates."""
    return psycopg.connect(get_write_url())


__all__ = [
    'get_database_url',
    'get_read_url',
    'get_write_url',
    'get_connection',
    'get_write_connection',
    'ensure_schema',
]

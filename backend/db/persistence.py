from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import threading
from typing import Any, Generator

import psycopg

from backend.config import READ_DB_URL, WRITE_DB_URL

ROOT_DIR = Path(__file__).resolve().parents[2]

_local = threading.local()


def get_read_url() -> str:
    return READ_DB_URL


def get_write_url() -> str:
    return WRITE_DB_URL


def get_database_url() -> str:
    return get_read_url()


def ensure_schema() -> None:
    schema_sql = (ROOT_DIR / 'database' / 'schema.sql').read_text(encoding='utf-8')
    with psycopg.connect(get_write_url(), connect_timeout=10) as connection:
        with connection.cursor() as cursor:
            cursor.execute(schema_sql)


def _get_active_write_conn() -> psycopg.Connection[Any]:
    conn = getattr(_local, 'write_conn', None)
    if conn is not None and not conn.closed:
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT 1;')
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            conn = None
    if conn is None or conn.closed:
        _local.write_conn = psycopg.connect(get_write_url(), connect_timeout=10, autocommit=True)
    return _local.write_conn


def _get_active_read_conn() -> psycopg.Connection[Any]:
    conn = getattr(_local, 'read_conn', None)
    if conn is not None and not conn.closed:
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT 1;')
        except Exception:
            try:
                conn.close()
            except Exception:
                pass
            conn = None
    if conn is None or conn.closed:
        _local.read_conn = psycopg.connect(get_read_url(), connect_timeout=10, autocommit=True)
    return _local.read_conn


@contextmanager
def get_write_connection() -> Generator[psycopg.Connection[Any], None, None]:
    conn = _get_active_write_conn()
    try:
        yield conn
    except Exception:
        if not conn.closed:
            try:
                conn.rollback()
            except Exception:
                pass
        raise


@contextmanager
def get_connection() -> Generator[psycopg.Connection[Any], None, None]:
    conn = _get_active_read_conn()
    try:
        yield conn
    except Exception:
        if not conn.closed:
            try:
                conn.rollback()
            except Exception:
                pass
        raise


__all__ = [
    'get_database_url',
    'get_read_url',
    'get_write_url',
    'get_connection',
    'get_write_connection',
    'ensure_schema',
]

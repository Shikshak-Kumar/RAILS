from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.config import READ_DB_URL, WRITE_DB_URL


def get_read_engine() -> Any:
    """SQLAlchemy engine pointed at the read replica (transactions)."""
    return create_engine(READ_DB_URL, future=True)


def get_write_engine() -> Any:
    """SQLAlchemy engine pointed at the write database."""
    return create_engine(WRITE_DB_URL, future=True)


# Backward-compatible aliases
def get_engine() -> Any:
    return get_read_engine()


def get_session_factory(*, write: bool = False) -> Any:
    """Return a session factory. Pass write=True to target the write DB."""
    engine = get_write_engine() if write else get_read_engine()
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


__all__ = [
    'get_engine',
    'get_read_engine',
    'get_write_engine',
    'get_session_factory',
]

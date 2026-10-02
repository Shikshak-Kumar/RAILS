from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DBTransaction(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    id: int | None = None
    timestamp: datetime
    from_bank: int | None = None
    sender_account: str = Field(min_length=1)
    to_bank: int | None = None
    receiver_account: str = Field(min_length=1)
    amount_received: float | None = None
    receiving_currency: str | None = None
    amount_paid: float = Field(gt=0)
    payment_currency: str | None = None
    payment_format: str | None = None
    is_laundering: bool = False


class TransactionRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')

    transaction_id: str
    sender_id: str
    receiver_id: str
    amount: float
    timestamp: datetime
    transaction_type: str | None = None
    currency: str | None = None
    is_laundering: bool | None = None


class EvidenceRecord(BaseModel):
    model_config = ConfigDict(extra='forbid')

    evidence_id: str
    timestamp: datetime
    session_id: str | None = None
    request_id: str | None = None
    tool_name: str
    tool_arguments: dict
    tool_output: dict
    model_name: str | None = None
    model_version: str | None = None
    kind: Literal['database', 'model', 'tool', 'rag', 'verification'] = 'tool'

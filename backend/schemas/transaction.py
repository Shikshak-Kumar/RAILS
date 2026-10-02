from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TransactionInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    transaction_id: str = Field(min_length=1)
    sender_id: str = Field(min_length=1)
    receiver_id: str = Field(min_length=1)
    amount: float = Field(gt=0, allow_inf_nan=False)
    timestamp: datetime
    transaction_type: str | None = None
    currency: str | None = None


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')

    error_code: str
    message: str
    request_id: str

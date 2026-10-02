from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="ignore")

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_summary: str | None = None
    evidence_id: str | None = None
    status: Literal["completed", "failed"] = "completed"
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, v: Any) -> str:
        if isinstance(v, str):
            lower = v.lower()
            if lower in ("success", "completed", "ok"):
                return "completed"
            if lower in ("failed", "error", "fail"):
                return "failed"
        return "completed"


# Backward compatibility aliases
ToolCallResponse = ToolCall
ToolCallRequest = ToolCall


class ExecutionStepModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    execution_id: str
    step_id: str
    step_type: str  # "planner" | "tool" | "verifier" | "llm"
    name: str
    tool_name: str | None = None
    status: Literal["QUEUED", "RUNNING", "COMPLETED", "FAILED"] = "COMPLETED"
    input: dict[str, Any] = Field(default_factory=dict)
    output: Any = None
    evidence_id: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: float = 0.0
    error: str | None = None


class CopilotRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None
    transaction_id: str | None = None
    account_id: str | None = None

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Message cannot be empty or blank")
        return v.strip()


class CopilotResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    response: str
    intent: str
    tool_calls: list[ToolCall] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    verified: bool = True
    execution_id: str | None = None
    conversation_id: str | None = None
    session_id: str | None = None
    answer: str | None = None
    risk_signals: list[str] = Field(default_factory=list)
    risk_drivers: list[str] = Field(default_factory=list)
    status: Literal["COMPLETED", "FAILED"] = "COMPLETED"

    def model_post_init(self, __context: Any) -> None:
        if self.answer is None:
            self.answer = self.response


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    error_code: str
    message: str
    execution_id: str | None = None
    details: dict[str, Any] | None = None

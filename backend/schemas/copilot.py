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


ToolCallResponse = ToolCall
ToolCallRequest = ToolCall


class ExecutionStepModel(BaseModel):
    model_config = ConfigDict(extra="ignore")

    execution_id: str
    step_id: str
    step_type: str
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


class RegulatoryContextItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chunk_id: str
    document_id: str
    document_name: str
    authority: str
    jurisdiction: str
    section: str | None = None
    page_number: int
    chunk_text: str
    relevance_score: float | None = None


class InvestigationContext(BaseModel):
    model_config = ConfigDict(extra="ignore")

    transaction_data: dict[str, Any] = Field(default_factory=dict)
    risk_data: dict[str, Any] = Field(default_factory=dict)
    aml_signals: list[str] = Field(default_factory=list)
    account_context: dict[str, Any] = Field(default_factory=dict)
    regulatory_context: list[RegulatoryContextItem] = Field(default_factory=list)
    historical_context: list[dict[str, Any]] = Field(default_factory=list)


class RiskInvestigationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    transaction_id: str
    risk_level: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = "LOW"
    risk_score: float | None = None
    fraud_probability: float | None = None
    anomaly_score: float | None = None
    signals: list[str] = Field(default_factory=list)
    summary: str
    verified_facts: list[str] = Field(default_factory=list)
    risk_signals: list[str] = Field(default_factory=list)
    regulatory_findings: list[str] = Field(default_factory=list)
    investigation_finding: str
    recommended_action: str
    evidence_ids: list[str] = Field(default_factory=list)
    regulatory_citation_ids: list[str] = Field(default_factory=list)


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
    investigation: RiskInvestigationResponse | None = None
    regulatory_citations: list[dict[str, Any]] = Field(default_factory=list)
    regulatory_citation_ids: list[str] = Field(default_factory=list)
    transactions: list[dict[str, Any]] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if self.answer is None:
            self.answer = self.response


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    error_code: str
    message: str
    execution_id: str | None = None
    details: dict[str, Any] | None = None

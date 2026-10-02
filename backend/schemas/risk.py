from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ModelResult(BaseModel):
    model_config = ConfigDict(extra='forbid')

    model_name: str
    model_version: str | None = None
    score: float | None = None
    risk_level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] | None = None
    output_key: str | None = None


class RiskAssessment(BaseModel):
    model_config = ConfigDict(extra='forbid')

    transaction_id: str | None = None
    fraud_probability: float | None = None
    anomaly_score: float | None = None
    account_risk_score: float | None = None
    risk_score: float | None = None
    overall_score: float | None = None
    risk_level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] = 'LOW'
    risk_types: list[str] = Field(default_factory=list)
    signals: list[str] = Field(default_factory=list)
    risk_drivers: list[str] = Field(default_factory=list)
    rule_results: list[dict[str, Any]] = Field(default_factory=list)
    model_results: list[ModelResult] = Field(default_factory=list)
    model_versions: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    explanation: str | None = None
    created_at: str | None = None
    analysis_status: str | None = None

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class RegulatoryCitationItem(BaseModel):
    model_config = ConfigDict(extra='ignore')

    citation_id: str
    authority: str
    document_name: str
    jurisdiction: str
    section: str | None = None
    page_number: int | None = None
    summary: str


class SupportingEvidenceItem(BaseModel):
    model_config = ConfigDict(extra='ignore')

    evidence_id: str
    purpose: str
    source: str


class STRDraft(BaseModel):
    model_config = ConfigDict(extra='ignore')

    report_id: str
    case_id: str
    report_type: str = "STR"
    status: str = "DRAFT"
    reporting_institution: str
    internal_case_id: str
    transaction_id: str
    transaction_date: str
    transaction_amount: float
    currency: str
    sender_account: str
    receiver_account: str
    payment_method: str
    risk_level: str
    fraud_probability: float
    anomaly_score: float
    risk_signals: list[str] = Field(default_factory=list)
    executive_summary: str
    suspicious_activity_description: str
    transaction_details: dict[str, Any] = Field(default_factory=dict)
    risk_indicators: list[str] = Field(default_factory=list)
    regulatory_context: list[RegulatoryCitationItem] = Field(default_factory=list)
    supporting_evidence: list[SupportingEvidenceItem] = Field(default_factory=list)
    analyst_notes: str
    recommended_next_step: str
    generated_at: str
    evidence_ids: list[str] = Field(default_factory=list)
    regulatory_citation_ids: list[str] = Field(default_factory=list)

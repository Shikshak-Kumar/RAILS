from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.evidence.store import evidence_store
from backend.main import app
from backend.schemas.copilot import (
    CopilotRequest,
    CopilotResponse,
    InvestigationContext,
    RegulatoryContextItem,
    RiskInvestigationResponse,
)
from backend.verification.verifier import verifier

client = TestClient(app)

SAMPLE_TX_ID = "2928645"


def test_scenario_1_why_flagged_uses_risk_tools():
    response = client.post(
        "/copilot/query",
        json={"message": f"Why was transaction {SAMPLE_TX_ID} flagged?"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["verified"] is True
    tool_names = [tc["tool"] for tc in data["tool_calls"]]
    assert "get_transaction" in tool_names or "fraud_check" in tool_names
    assert "regulatory_search" not in tool_names
    assert len(data["regulatory_citation_ids"]) == 0
    assert SAMPLE_TX_ID in data["response"]


def test_scenario_2_regulatory_guidance_uses_regulatory_search():
    response = client.post(
        "/copilot/query",
        json={"message": f"What regulatory guidance is relevant to transaction {SAMPLE_TX_ID}?"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["verified"] is True
    tool_names = [tc["tool"] for tc in data["tool_calls"]]
    assert "regulatory_search" in tool_names
    assert len(data["regulatory_citation_ids"]) > 0
    for cid in data["regulatory_citation_ids"]:
        assert any(prefix in cid.lower() for prefix in ("fatf", "fincen"))


def test_scenario_3_why_flagged_and_regulatory_uses_both():
    response = client.post(
        "/copilot/query",
        json={"message": f"Why was transaction {SAMPLE_TX_ID} flagged and what regulatory guidance is relevant?"},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["verified"] is True
    tool_names = [tc["tool"] for tc in data["tool_calls"]]
    assert "get_transaction" in tool_names or "fraud_check" in tool_names
    assert "regulatory_search" in tool_names
    assert len(data["regulatory_citation_ids"]) > 0
    assert len(data["regulatory_citations"]) > 0

    for cit_id in data["regulatory_citation_ids"]:
        assert any(prefix in cit_id.lower() for prefix in ("fatf", "fincen"))
        assert any(cit["chunk_id"] == cit_id for cit in data["regulatory_citations"])

    for cit in data["regulatory_citations"]:
        assert cit["authority"] in ("FATF", "FinCEN")
        assert cit["jurisdiction"] in ("GLOBAL", "US")
        assert cit["page_number"] > 0
        assert len(cit["chunk_text"]) > 20


def test_scenario_4_create_investigation_explanation():
    response = client.post(
        "/copilot/query",
        json={"message": f"Create an investigation explanation for transaction {SAMPLE_TX_ID}."},
    )
    assert response.status_code == 200
    data = response.json()

    assert data["verified"] is True
    assert data["investigation"] is not None
    inv = data["investigation"]

    assert inv["transaction_id"] == SAMPLE_TX_ID
    assert inv["risk_level"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    assert len(inv["verified_facts"]) > 0
    assert len(inv["investigation_finding"]) > 0
    assert len(inv["recommended_action"]) > 0
    assert len(inv["evidence_ids"]) > 0

    text = data["response"]
    assert "Verified Facts" in text or "VERIFIED FACTS" in text or "Transaction Details" in text
    assert "Risk Signals" in text or "RISK SIGNALS" in text
    assert "Investigation Finding" in text or "INVESTIGATION" in text


def test_scenario_5_indian_regulatory_question_safety():
    response = client.post(
        "/copilot/query",
        json={"message": "What are the Indian banking regulatory requirements and does FinCEN apply to Indian domestic transactions?"},
    )
    assert response.status_code == 200
    data = response.json()

    resp_text = data["response"].lower()
    assert "fincen is indian" not in resp_text
    has_jurisdiction_clarity = (
        "us" in resp_text or "united states" in resp_text or "global" in resp_text or "corpus" in resp_text
    )
    assert has_jurisdiction_clarity is True


def test_scenario_6_unrelated_question():
    response = client.post(
        "/copilot/query",
        json={"message": "What is the best recipe for baking chocolate chip cookies at home?"},
    )
    assert response.status_code == 200
    data = response.json()

    tool_names = [tc["tool"] for tc in data["tool_calls"]]
    assert "regulatory_search" not in tool_names
    assert len(data["regulatory_citation_ids"]) == 0


def test_verifier_strict_rejection_of_fabricated_citations():
    ev = evidence_store.add(tool_name="test_tool", tool_output={"status": "ok"})
    context = InvestigationContext(
        transaction_data={"id": "2928645", "amount": 17801.52, "currency": "USD"},
        risk_data={"risk_level": "HIGH", "risk_score": 0.85},
        regulatory_context=[
            RegulatoryContextItem(
                chunk_id="reg_fatf_005",
                document_id="fatf-recommendations-2012",
                document_name="FATF Recommendations (2012)",
                authority="FATF",
                jurisdiction="GLOBAL",
                section="Scope",
                page_number=4,
                chunk_text="Countries should apply a risk-based approach to ensure that measures to prevent or mitigate money laundering.",
            )
        ],
    )

    valid_resp = RiskInvestigationResponse(
        transaction_id="2928645",
        risk_level="HIGH",
        summary="Verified high risk transaction",
        verified_facts=["Amount: 17801.52 USD"],
        risk_signals=["High volume transfer"],
        regulatory_findings=["CDD obligations apply under FATF guidance"],
        investigation_finding="Requires customer identity verification",
        recommended_action="Request identity documents from customer",
        evidence_ids=[ev.evidence_id],
        regulatory_citation_ids=["reg_fatf_005"],
    )

    v_res = verifier.verify_risk_investigation(
        investigation=valid_resp,
        context=context,
        execution_evidence_ids=[ev.evidence_id],
    )
    assert v_res.ok is True
    assert len(v_res.issues) == 0

    fake_resp = RiskInvestigationResponse(
        transaction_id="2928645",
        risk_level="HIGH",
        summary="Fabricated citation test",
        verified_facts=["Amount: 17801.52 USD"],
        risk_signals=["Risk signal"],
        regulatory_findings=["Fabricated finding"],
        investigation_finding="Investigation finding",
        recommended_action="Action",
        evidence_ids=[ev.evidence_id],
        regulatory_citation_ids=["FABRICATED-REG-999"],
    )

    v_res_fake = verifier.verify_risk_investigation(
        investigation=fake_resp,
        context=context,
        execution_evidence_ids=[ev.evidence_id],
    )
    assert v_res_fake.ok is False
    assert any("does not exist in authoritative corpus" in iss or "was not in retrieved" in iss for iss in v_res_fake.issues)


def test_verifier_rejects_mismatched_transaction_id():
    ev = evidence_store.add(tool_name="test_tool", tool_output={"status": "ok"})
    context = InvestigationContext(
        transaction_data={"id": "2928645", "amount": 17801.52},
        risk_data={"risk_level": "HIGH"},
    )

    mismatched_resp = RiskInvestigationResponse(
        transaction_id="9999999",
        risk_level="HIGH",
        summary="Mismatched ID",
        verified_facts=[],
        risk_signals=[],
        regulatory_findings=[],
        investigation_finding="Finding",
        recommended_action="Action",
        evidence_ids=[ev.evidence_id],
        regulatory_citation_ids=[],
    )

    v_res = verifier.verify_risk_investigation(
        investigation=mismatched_resp,
        context=context,
        execution_evidence_ids=[ev.evidence_id],
    )
    assert v_res.ok is False
    assert any("does not match" in iss.lower() or "mismatch" in iss.lower() for iss in v_res.issues)

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas.copilot import CopilotRequest, CopilotResponse
from backend.tools.runner import run_tool
from backend.tools.transaction_tools import get_high_risk_transactions
from backend.verification.verifier import verifier

client = TestClient(app)


def test_1_greeting_does_not_call_tools():
    payload = {"message": "hi"}
    response = client.post("/copilot/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "conversation"
    assert len(data["tool_calls"]) == 0
    assert len(data["evidence_ids"]) == 0
    assert data["verified"] is True
    assert "RAILS" in data["response"] or "RAILS" in data["answer"]


def test_2_high_risk_query_uses_risk_tool():
    payload = {"message": "give me the most high risk transactions"}
    response = client.post("/copilot/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] in ("risk_transactions", "fraud_analysis")

    tool_names = [tc["tool"] for tc in data["tool_calls"]]
    assert "get_high_risk_transactions" in tool_names
    assert "list_transactions" not in tool_names


def test_3_high_risk_transactions_sorted():
    result = get_high_risk_transactions(limit=10, sort_by="risk_score")
    assert "items" in result
    items = result["items"]
    assert len(items) > 0

    scores = [item["risk_score"] for item in items]
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1], f"Scores not descending: {scores}"


def test_4_no_fake_risk_levels():
    result = get_high_risk_transactions(limit=5)
    for item in result["items"]:
        assert item["risk_level"] in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
        assert 0.0 <= item["risk_score"] <= 1.0
        assert 0.0 <= item["fraud_probability"] <= 1.0
        assert 0.0 <= item["anomaly_score"] <= 1.0
        assert isinstance(item["signals"], list)


def test_5_account_query():
    payload = {"message": "What is the risk profile of account 808B1C350?"}
    response = client.post("/copilot/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "account_risk"
    tool_names = [tc["tool"] for tc in data["tool_calls"]]
    assert "account_risk_check" in tool_names or "account_history" in tool_names


def test_6_latest_transactions():
    payload = {"message": "show latest transactions"}
    response = client.post("/copilot/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["intent"] == "transactions"
    tool_names = [tc["tool"] for tc in data["tool_calls"]]
    assert "list_transactions" in tool_names
    assert "get_high_risk_transactions" not in tool_names


def test_7_copilot_response_is_pydantic():
    payload = {"message": "what can you do?"}
    response = client.post("/copilot/query", json=payload)
    assert response.status_code == 200
    parsed = CopilotResponse.model_validate(response.json())
    assert isinstance(parsed, CopilotResponse)
    assert parsed.intent == "conversation"
    assert parsed.verified is True
    assert len(parsed.tool_calls) == 0


def test_8_tool_failure():
    with pytest.raises(Exception):
        run_tool("get_transaction")


def test_9_evidence_ids():
    payload = {"message": "give me the most high risk transactions"}
    response = client.post("/copilot/query", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert len(data["evidence_ids"]) > 0
    for eid in data["evidence_ids"]:
        assert eid.startswith("ev-")


def test_10_verifier_failure():
    class FakeBadAssessment:
        risk_score = 99.9
        risk_level = "CRITICAL"

    v_result = verifier.verify_assessment(FakeBadAssessment())
    assert v_result.verified is False
    assert any("risk_score out of range" in iss for iss in v_result.issues)

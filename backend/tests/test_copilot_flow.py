from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas.copilot import CopilotResponse

client = TestClient(app)


def test_12_exact_questions_flow():
    conv_id = "test-conv-12-exact-flow"

    res1 = client.post("/copilot/query", json={"message": "hi", "conversation_id": conv_id})
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["intent"] == "conversation"
    assert len(data1["tool_calls"]) == 0
    assert "RAILS" in data1["response"] or "RAILS" in data1["answer"]

    res2 = client.post("/copilot/query", json={"message": "Provide me 5 transactions with high fraud", "conversation_id": conv_id})
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["intent"] == "risk_transactions"
    tool_names_2 = [tc["tool"] for tc in data2["tool_calls"]]
    assert "get_high_risk_transactions" in tool_names_2
    assert "Hello!" not in data2["response"][:30]
    assert len(data2["transactions"]) > 0 or len(data2["response"]) > 50
    assert "Transaction" in data2["response"] or "TX" in data2["response"]

    res3 = client.post("/copilot/query", json={"message": "Show me 10 high risk transactions", "conversation_id": conv_id})
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["intent"] == "risk_transactions"
    tool_names_3 = [tc["tool"] for tc in data3["tool_calls"]]
    assert "get_high_risk_transactions" in tool_names_3
    assert len(data3["transactions"]) > 0

    res4 = client.post("/copilot/query", json={"message": "Which one has the highest fraud probability?", "conversation_id": conv_id})
    assert res4.status_code == 200
    data4 = res4.json()
    assert data4["intent"] in ("follow_up_questions", "risk_transactions", "clarification")
    assert "fraud" in data4["response"].lower()
    assert "transaction" in data4["response"].lower()

    res5 = client.post("/copilot/query", json={"message": "Investigate transaction 2928645", "conversation_id": conv_id})
    assert res5.status_code == 200
    data5 = res5.json()
    assert data5["intent"] in ("risk_investigation", "transaction_investigation")
    tool_names_5 = [tc["tool"] for tc in data5["tool_calls"]]
    assert "get_transaction" in tool_names_5

    res6 = client.post("/copilot/query", json={"message": "What regulation is relevant to this investigation?", "conversation_id": conv_id})
    assert res6.status_code == 200
    data6 = res6.json()
    tool_names_6 = [tc["tool"] for tc in data6["tool_calls"]]
    assert "regulatory_search" in tool_names_6 or len(data6.get("regulatory_citations", [])) > 0
    assert data6["verified"] is True

    res7 = client.post("/copilot/query", json={"message": "Why is this transaction risky?", "conversation_id": conv_id})
    assert res7.status_code == 200
    data7 = res7.json()
    assert data7["verified"] is True
    assert len(data7["response"]) > 30

    res8 = client.post("/copilot/query", json={"message": "Create an STR draft for this case", "conversation_id": conv_id})
    assert res8.status_code == 200
    data8 = res8.json()
    tool_names_8 = [tc["tool"] for tc in data8["tool_calls"]]
    assert "generate_report" in tool_names_8 or "report" in data8["response"].lower()

    res9 = client.post("/copilot/query", json={"message": "Tell me about this transaction", "conversation_id": conv_id})
    assert res9.status_code == 200
    data9 = res9.json()
    assert len(data9["response"]) > 30

    res10 = client.post("/copilot/query", json={"message": "Which one?", "conversation_id": conv_id})
    assert res10.status_code == 200
    data10 = res10.json()
    assert "transaction" in data10["response"].lower()

    res11 = client.post("/copilot/query", json={"message": "Investigate that one", "conversation_id": conv_id})
    assert res11.status_code == 200
    data11 = res11.json()
    assert data11["intent"] in ("risk_investigation", "transaction_investigation")

    res12 = client.post("/copilot/query", json={"message": "How does RAILS work?", "conversation_id": conv_id})
    assert res12.status_code == 200
    data12 = res12.json()
    assert data12["intent"] == "conversation"
    assert len(data12["tool_calls"]) == 0
    assert "RAILS" in data12["response"]
    assert "surveillance" in data12["response"].lower() or "intelligence" in data12["response"].lower()

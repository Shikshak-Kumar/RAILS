import sys
import json
from backend.services.risk_service import risk_service
from backend.tools.transaction_tools import get_transaction, list_transactions
from backend.api.transactions import get_transaction as api_get_transaction, list_transactions as api_list_transactions
from backend.services.case_service import case_service
from backend.verification.verifier import Verifier
from backend.schemas.copilot import CopilotRequest
from backend.llm.orchestrator import orchestrator

def test_canonical_risk_consistency():
    can_risk = risk_service.get_canonical_risk("2928643")
    assert can_risk["risk_level"] == "LOW", f"Expected LOW, got {can_risk['risk_level']}"
    assert can_risk["fraud_probability"] < 0.001, f"Expected small fraud prob, got {can_risk['fraud_probability']}"

    t_tool = get_transaction("2928643")
    assert t_tool.get("transaction", {}).get("risk_level") == "LOW"

    list_tool = list_transactions(search="2928643")
    found = [t for t in list_tool.get("transactions", []) if str(t.get("transaction_id")) == "2928643"]
    if found:
        assert found[0].get("risk_level") == "LOW"

    api_tx = api_get_transaction("2928643")
    assert api_tx.get("risk_level") == "LOW"
    assert api_tx.get("risk_assessment", {}).get("risk_level") == "LOW"

    api_list = api_list_transactions(search="2928643")
    found_api = [t for t in api_list.get("items", []) if str(t.get("transaction_id")) == "2928643"]
    if found_api:
        assert found_api[0].get("risk_level") == "LOW"

    c = case_service._format_case({"case_id": "test-case-2928643", "summary": "Investigation of TX #2928643", "transaction_id": "2928643"})
    assert c.get("risk_level") == "LOW", f"Expected LOW for case of 2928643, got {c.get('risk_level')}"

    verifier = Verifier()
    v_ok = verifier.verify_risk_consistency(
        answer="The transaction 2928643 has been evaluated as LOW risk. Fraud probability is 0.013%.",
        transactions=[{"transaction_id": "2928643", "risk_level": "LOW"}],
        canonical_risk_map={"2928643": {"risk_level": "LOW", "risk_score": 0.40, "fraud_probability": 0.00013}}
    )
    assert v_ok.ok is True

    v_fail_card = verifier.verify_risk_consistency(
        answer="The transaction 2928643 has been evaluated as LOW risk.",
        transactions=[{"transaction_id": "2928643", "risk_level": "HIGH"}],
        canonical_risk_map={"2928643": {"risk_level": "LOW", "risk_score": 0.40, "fraud_probability": 0.00013}}
    )
    assert v_fail_card.ok is False
    assert any("mismatch" in issue.lower() for issue in v_fail_card.issues)

    v_fail_text = verifier.verify_risk_consistency(
        answer="The transaction 2928643 has been evaluated as HIGH risk.",
        transactions=[{"transaction_id": "2928643", "risk_level": "LOW"}],
        canonical_risk_map={"2928643": {"risk_level": "LOW", "risk_score": 0.40, "fraud_probability": 0.00013}}
    )
    assert v_fail_text.ok is False
    assert any("mismatch in response text" in issue.lower() for issue in v_fail_text.issues)

    can_risk_high = risk_service.get_canonical_risk("tx-high-e27384ff")
    assert can_risk_high["risk_level"] in ("HIGH", "CRITICAL"), f"Expected HIGH/CRITICAL, got {can_risk_high['risk_level']}"
    c_high = case_service._format_case({"case_id": "test-case-high", "summary": "Alert for TX #tx-high-e27384ff", "transaction_id": "tx-high-e27384ff"})
    assert c_high.get("risk_level") in ("HIGH", "CRITICAL")

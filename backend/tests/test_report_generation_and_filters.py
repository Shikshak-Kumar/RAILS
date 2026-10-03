from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.case_service import case_service
from backend.services.report_service import report_service
from backend.db.repositories.transaction_repository import transaction_repository
from backend.schemas.transaction import TransactionInput
from datetime import datetime, timezone

client = TestClient(app)


@pytest.fixture(scope="module")
def sample_test_case():
    tx_input = TransactionInput(
        transaction_id="tx-report-test-9988",
        sender_id="ACC_SRC_9988",
        receiver_id="ACC_DST_9988",
        amount=145000.0,
        currency="USD",
        transaction_type="WIRE",
        timestamp=datetime(2026, 10, 2, 14, 30, 0, tzinfo=timezone.utc),
    )
    transaction_repository.upsert(tx_input)

    c = case_service.create_case(
        "High risk wire transfer investigation TX tx-report-test-9988",
        status="OPEN",
        transaction_id="tx-report-test-9988",
    )
    return c


def test_report_data_completeness_and_accuracy(sample_test_case):
    cid = sample_test_case["case_id"]
    rep = report_service.generate_str_draft(case_id=cid, transaction_id="tx-report-test-9988")

    assert rep["report_id"].startswith("rep-")
    assert rep["case_id"] == cid
    assert rep["status"] == "DRAFT"

    sd = rep.get("structured_data", {})
    assert sd["internal_case_id"] == cid
    assert sd["transaction_id"] == "tx-report-test-9988"
    assert sd["transaction_amount"] == 145000.0
    assert sd["currency"] == "USD"
    assert sd["payment_method"] == "WIRE"
    assert sd["sender_account"] == "ACC_SRC_9988"
    assert sd["receiver_account"] == "ACC_DST_9988"
    assert sd["transaction_date"] == "2026-10-02 14:30:00 UTC"
    assert sd["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert isinstance(sd["fraud_probability"], float)
    assert isinstance(sd["anomaly_score"], float)


def test_no_placeholders_or_raw_markdown(sample_test_case):
    cid = sample_test_case["case_id"]
    rep = report_service.generate_str_draft(case_id=cid, transaction_id="tx-report-test-9988")

    body = rep.get("body", "")
    sd = rep.get("structured_data", {})

    assert "[Your Financial Institution Name]" not in body
    assert "[Your Financial Institution Name]" not in sd.get("reporting_institution", "")
    assert "**Date" not in body
    assert "Not configured" in sd.get("reporting_institution", "") or "Bank" in sd.get("reporting_institution", "")
    assert sd.get("transaction_date") != "Not available in source data"
    assert not body.startswith("**")


def test_evidence_and_citations_validity(sample_test_case):
    cid = sample_test_case["case_id"]
    rep = report_service.generate_str_draft(case_id=cid, transaction_id="tx-report-test-9988")

    sd = rep.get("structured_data", {})
    evidence_ids = sd.get("evidence_ids", [])
    citation_ids = sd.get("regulatory_citation_ids", [])

    assert len(evidence_ids) > 0
    for eid in evidence_ids:
        assert isinstance(eid, str) and eid.startswith("ev-")

    assert len(citation_ids) > 0
    from backend.services.regulatory_rag_service import regulatory_rag_service
    for cid_val in citation_ids:
        chunk = regulatory_rag_service.get_chunk(cid_val)
        assert chunk is not None
        assert chunk["chunk_id"] == cid_val


def test_case_status_filters():
    res_all = client.get("/cases?status=ALL&limit=10")
    assert res_all.status_code == 200
    assert isinstance(res_all.json(), list)

    res_open = client.get("/cases?status=OPEN&limit=10")
    assert res_open.status_code == 200
    cases_open = res_open.json()
    for c in cases_open:
        assert c["status"] == "OPEN"

    res_appr = client.get("/cases?status=APPROVED&limit=10")
    assert res_appr.status_code == 200
    cases_appr = res_appr.json()
    for c in cases_appr:
        assert c["status"] == "APPROVED"


def test_case_search():
    res = client.get("/cases?search=case&limit=5")
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)


def test_report_status_transitions_and_human_approval(sample_test_case):
    cid = sample_test_case["case_id"]
    rep = report_service.generate_str_draft(case_id=cid, transaction_id="tx-report-test-9988")
    rid = rep["report_id"]

    assert rep["status"] == "DRAFT"

    res_appr = client.post(f"/reports/{rid}/approve", json={"approved_by": "Compliance Lead"})
    assert res_appr.status_code == 200
    appr_data = res_appr.json()
    assert appr_data["status"] == "APPROVED"
    assert appr_data["approved_by"] == "Compliance Lead"

    res_rej = client.post(f"/reports/{rid}/reject")
    assert res_rej.status_code == 200
    rej_data = res_rej.json()
    assert rej_data["status"] == "REJECTED"


def test_report_generation_performance_and_metrics(sample_test_case):
    cid = sample_test_case["case_id"]
    rep = report_service.generate_str_draft(case_id=cid, transaction_id="tx-report-test-9988")

    metrics = rep.get("generation_metrics", {})
    assert "case_retrieval_ms" in metrics
    assert "transaction_retrieval_ms" in metrics
    assert "evidence_retrieval_ms" in metrics
    assert "regulatory_retrieval_ms" in metrics
    assert "generation_ms" in metrics
    assert "persistence_ms" in metrics
    assert "total_ms" in metrics
    assert metrics["generation_ms"] < 250

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.regulatory_rag_service import regulatory_rag_service
from backend.verification.verifier import verifier

client = TestClient(app)


def test_regulatory_documents_metadata():
    docs = regulatory_rag_service.get_documents_metadata()
    assert len(docs) == 3

    docs_by_id = {d["document_id"]: d for d in docs}

    assert "fatf_recommendations" in docs_by_id
    fatf = docs_by_id["fatf_recommendations"]
    assert fatf["authority"] == "FATF"
    assert fatf["jurisdiction"] == "GLOBAL"
    assert fatf["document_type"] == "AML_CFT_STANDARD"
    assert fatf["file_name"] == "fatf-recommendations-2012.pdf"
    assert "June 2026" in fatf["document_name"] or "June 2026" in fatf["publication_date"]

    assert "fincen_sar_efiling" in docs_by_id
    efile = docs_by_id["fincen_sar_efiling"]
    assert efile["authority"] == "FinCEN"
    assert efile["jurisdiction"] == "US"
    assert efile["document_type"] == "SAR_FILING_GUIDANCE"
    assert efile["file_name"] == "FinCEN SAR ElectronicFilingInstructions- Stand Alone doc.pdf"

    assert "fincen_sar_narrative" in docs_by_id
    narrative = docs_by_id["fincen_sar_narrative"]
    assert narrative["authority"] == "FinCEN"
    assert narrative["jurisdiction"] == "US"
    assert narrative["document_type"] == "SAR_NARRATIVE_GUIDANCE"
    assert narrative["file_name"] == "sarnarrcompletguidfinal_112003.pdf"


def test_query_fatf_standards():
    res = regulatory_rag_service.search("What are the FATF standards relevant to money laundering risk?", limit=5)
    assert res["jurisdiction"] == "GLOBAL"
    assert len(res["chunks"]) > 0
    for c in res["chunks"]:
        assert c["authority"] == "FATF"
        assert c["jurisdiction"] == "GLOBAL"
        assert c["page_number"] >= 1
        assert c["chunk_id"].startswith("reg_fatf_")
        assert c["section"] is not None


def test_query_fincen_sar_narrative():
    res = regulatory_rag_service.search("What information is relevant when preparing an SAR narrative?", limit=5)
    assert res["jurisdiction"] == "US"
    assert len(res["chunks"]) > 0
    first_chunk = res["chunks"][0]
    assert first_chunk["authority"] == "FinCEN"
    assert first_chunk["jurisdiction"] == "US"
    assert first_chunk["document_id"] == "fincen_sar_narrative"
    assert first_chunk["page_number"] >= 1
    assert first_chunk["chunk_id"].startswith("reg_fincen_narrative_")


def test_query_fincen_sar_efiling():
    res = regulatory_rag_service.search("What are the SAR electronic filing requirements?", limit=5)
    assert res["jurisdiction"] == "US"
    assert len(res["chunks"]) > 0
    top_chunk = res["chunks"][0]
    assert top_chunk["authority"] == "FinCEN"
    assert top_chunk["jurisdiction"] == "US"
    assert top_chunk["document_id"] == "fincen_sar_efiling"
    assert top_chunk["page_number"] >= 1
    assert top_chunk["chunk_id"].startswith("reg_fincen_efile_")


def test_query_indian_bank_jurisdiction_safety():
    res = regulatory_rag_service.search("What guidance applies to an Indian bank?", limit=5)
    assert res["jurisdiction_warning"] is not None
    assert "Indian" in res["jurisdiction_warning"]
    assert "FinCEN" in res["jurisdiction_warning"]
    assert "GLOBAL (FATF Recommendations)" in res["jurisdiction_warning"]
    for c in res["chunks"]:
        assert c["jurisdiction"] == "GLOBAL"
        assert c["authority"] == "FATF"


def test_query_irrelevant_question():
    res = regulatory_rag_service.search("What is the recipe for chocolate cake with baking powder?", limit=5)
    assert len(res["chunks"]) == 0

    res2 = regulatory_rag_service.search("How to tune a violin string?", limit=5)
    assert len(res2["chunks"]) == 0


def test_chunk_retrieval_by_id():
    chunk = regulatory_rag_service.get_chunk("reg_fatf_001")
    assert chunk is not None
    assert chunk["chunk_id"] == "reg_fatf_001"
    assert chunk["authority"] == "FATF"
    assert chunk["page_number"] == 1
    assert len(chunk["chunk_text"]) > 20

    assert regulatory_rag_service.get_chunk("non_existent_chunk_999") is None


def test_api_endpoints():
    resp = client.get("/regulatory/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 3
    assert len(data["documents"]) == 3

    resp = client.get("/regulatory/chunks/reg_fincen_efile_001")
    assert resp.status_code == 200
    chunk_data = resp.json()
    assert chunk_data["chunk_id"] == "reg_fincen_efile_001"
    assert chunk_data["authority"] == "FinCEN"
    assert chunk_data["jurisdiction"] == "US"

    resp = client.get("/regulatory/chunks/invalid_chunk_xyz")
    assert resp.status_code == 404

    resp = client.get("/regulatory/search?query=FATF+money+laundering+standards&limit=3")
    assert resp.status_code == 200
    search_data = resp.json()
    assert len(search_data["chunks"]) > 0
    assert search_data["chunks"][0]["authority"] == "FATF"


def test_verifier_regulatory_retrieval():
    v_res = verifier.verify_regulatory_retrieval(["reg_fatf_001", "reg_fincen_efile_001"])
    assert v_res.ok is True
    assert len(v_res.issues) == 0

    v_res_bad = verifier.verify_regulatory_retrieval(["reg_fatf_001", "reg_fake_999"])
    assert v_res_bad.ok is False
    assert any("reg_fake_999" in issue for issue in v_res_bad.issues)

    v_res_mismatch = verifier.verify_regulatory_retrieval(["reg_fatf_001"], expected_jurisdiction="US")
    assert v_res_mismatch.ok is False
    assert any("does not match expected US" in issue for issue in v_res_mismatch.issues)

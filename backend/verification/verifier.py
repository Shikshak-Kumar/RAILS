from __future__ import annotations

import re
from typing import Any

from backend.evidence.store import evidence_store


class VerificationResult:
    def __init__(self, *, ok: bool, issues: list[str] | None = None, evidence_ids: list[str] | None = None) -> None:
        self.ok = ok
        self.issues = issues or []
        self.evidence_ids = evidence_ids or []

    @property
    def verified(self) -> bool:
        return self.ok

    def model_dump(self) -> dict[str, Any]:
        return {'ok': self.ok, 'verified': self.ok, 'issues': self.issues, 'evidence_ids': self.evidence_ids}


class Verifier:
    def __init__(self, evidence_store_ref: Any | None = None) -> None:
        self.evidence_store_ref = evidence_store_ref or evidence_store

    def verify_assessment(self, assessment: Any, *, evidence_ids: list[str] | None = None) -> VerificationResult:
        issues: list[str] = []
        evidence_ids = evidence_ids or []

        if assessment is None:
            return VerificationResult(ok=False, issues=['Assessment missing'], evidence_ids=[])

        risk_score = getattr(assessment, 'risk_score', None)
        risk_level = getattr(assessment, 'risk_level', None)
        if risk_score is not None and not 0.0 <= float(risk_score) <= 1.0:
            issues.append('risk_score out of range')
        if risk_level and risk_level not in {'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'}:
            issues.append('risk_level invalid')
        if not evidence_ids and not getattr(assessment, 'evidence_ids', None):
            issues.append('No evidence attached')

        for evidence_id in evidence_ids:
            item = self.evidence_store_ref.get(evidence_id)
            if item is None:
                issues.append(f'Evidence {evidence_id} missing')

        return VerificationResult(ok=not issues, issues=issues, evidence_ids=evidence_ids)

    def verify_transaction_workflow(self, transaction: Any, assessment: Any, evidence_ids: list[str] | None = None) -> VerificationResult:
        issues: list[str] = []
        evidence_ids = evidence_ids or []
        if transaction is None:
            issues.append('Transaction missing')
        if assessment is None:
            issues.append('Assessment missing')
        if not evidence_ids:
            issues.append('No evidence recorded for workflow')
        return VerificationResult(ok=not issues, issues=issues, evidence_ids=evidence_ids)

    def verify_regulatory_retrieval(self, chunk_ids: list[str], *, expected_jurisdiction: str | None = None) -> VerificationResult:
        from backend.services.regulatory_rag_service import regulatory_rag_service
        issues: list[str] = []
        verified_ids: list[str] = []

        if not chunk_ids:
            return VerificationResult(ok=True, issues=[], evidence_ids=[])

        for cid in chunk_ids:
            chunk = regulatory_rag_service.get_chunk(cid)
            if not chunk:
                issues.append(f"Regulatory chunk {cid} not found in authoritative corpus")
            else:
                verified_ids.append(cid)
                if expected_jurisdiction and chunk.get("jurisdiction", "").upper() != expected_jurisdiction.upper():
                    issues.append(f"Chunk {cid} jurisdiction {chunk.get('jurisdiction')} does not match expected {expected_jurisdiction}")

        return VerificationResult(ok=len(issues) == 0, issues=issues, evidence_ids=verified_ids)

    def verify_risk_investigation(
        self,
        investigation: Any,
        context: Any,
        execution_evidence_ids: list[str] | None = None,
    ) -> VerificationResult:
        from backend.services.regulatory_rag_service import regulatory_rag_service

        issues: list[str] = []
        verified_evidence: list[str] = []

        if investigation is None:
            return VerificationResult(ok=False, issues=["Investigation missing"], evidence_ids=[])

        target_tx_id = getattr(investigation, "transaction_id", None)
        ctx_tx_data = getattr(context, "transaction_data", {}) or {}
        ctx_tx_id = ctx_tx_data.get("transaction_id") or ctx_tx_data.get("id")

        if not target_tx_id:
            issues.append("Investigation missing transaction_id")
        elif ctx_tx_id and str(target_tx_id) != str(ctx_tx_id):
            issues.append(f"Investigation transaction_id '{target_tx_id}' does not match context '{ctx_tx_id}'")

        risk_lvl = getattr(investigation, "risk_level", None)
        ctx_risk_data = getattr(context, "risk_data", {}) or {}
        expected_risk_lvl = ctx_risk_data.get("risk_level")
        if risk_lvl and risk_lvl not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            issues.append(f"Investigation risk_level '{risk_lvl}' is invalid")
        elif expected_risk_lvl and risk_lvl and risk_lvl != expected_risk_lvl:
            issues.append(f"Investigation risk_level '{risk_lvl}' does not match evaluated risk '{expected_risk_lvl}'")

        inv_evidence_ids = getattr(investigation, "evidence_ids", []) or []
        for eid in inv_evidence_ids:
            item = self.evidence_store_ref.get(eid)
            if item is None:
                issues.append(f"Evidence {eid} missing from evidence store")
            else:
                verified_evidence.append(eid)

        if execution_evidence_ids is not None:
            for eid in inv_evidence_ids:
                if eid not in execution_evidence_ids:
                    issues.append(f"Evidence {eid} was not part of this investigation execution")

        ctx_reg_items = getattr(context, "regulatory_context", []) or []
        retrieved_chunk_ids = {
            item.chunk_id if hasattr(item, "chunk_id") else item.get("chunk_id")
            for item in ctx_reg_items
        }

        inv_citation_ids = getattr(investigation, "regulatory_citation_ids", []) or []
        for cid in inv_citation_ids:
            if cid not in retrieved_chunk_ids:
                issues.append(f"Unsupported regulatory citation '{cid}' was not in retrieved regulatory context")

            chunk = regulatory_rag_service.get_chunk(cid)
            if not chunk:
                issues.append(f"Regulatory citation '{cid}' does not exist in authoritative corpus")
            else:
                chunk_jur = chunk.get("jurisdiction")
                chunk_auth = chunk.get("authority")
                if chunk_auth == "FATF" and chunk_jur != "GLOBAL":
                    issues.append(f"Chunk '{cid}' FATF authority must be GLOBAL jurisdiction")
                elif chunk_auth == "FinCEN" and chunk_jur != "US":
                    issues.append(f"Chunk '{cid}' FinCEN authority must be US jurisdiction")

                expected_page = chunk.get("page_number")
                matching_ctx_item = next(
                    (it for it in ctx_reg_items if (it.chunk_id if hasattr(it, "chunk_id") else it.get("chunk_id")) == cid),
                    None
                )
                if matching_ctx_item:
                    ctx_page = matching_ctx_item.page_number if hasattr(matching_ctx_item, "page_number") else matching_ctx_item.get("page_number")
                    if ctx_page is not None and expected_page is not None and ctx_page != expected_page:
                        issues.append(f"Chunk '{cid}' page number {ctx_page} does not match stored page {expected_page}")

        return VerificationResult(ok=len(issues) == 0, issues=issues, evidence_ids=verified_evidence)

    def verify_risk_consistency(
        self,
        *,
        answer: str,
        transactions: list[dict[str, Any]],
        canonical_risk_map: dict[str, dict[str, Any]],
    ) -> VerificationResult:
        issues: list[str] = []

        for tx in transactions:
            tid = str(tx.get("transaction_id") or tx.get("id") or "")
            if not tid or tid not in canonical_risk_map:
                continue
            backend_risk = str(canonical_risk_map[tid].get("risk_level", "LOW")).upper()
            card_risk = str(tx.get("risk_level", "")).upper()

            if card_risk != backend_risk:
                issues.append(
                    f"Risk level mismatch for transaction {tid}: card displays '{card_risk}' but canonical backend risk is '{backend_risk}'"
                )

            for lvl in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
                if lvl != backend_risk:
                    patterns = [
                        rf"transaction [`']?{re.escape(tid)}[`']?.*?\b(?:is currently classified as|classified as|evaluated as|level)\s*\*{{0,2}}{lvl}\*{{0,2}}\b",
                        rf"tx\s*(?:#|[`']?)\s*{re.escape(tid)}\b.*?\b{lvl}\s+risk\b",
                        rf"tx\s*(?:#|[`']?)\s*{re.escape(tid)}\b.*?\brisk\s*:\s*\*{{0,2}}{lvl}\*{{0,2}}\b",
                        rf"\b{lvl}\s+risk\b.*?(?:transaction|tx)\s*(?:#|[`']?)\s*{re.escape(tid)}\b",
                        rf"(?:transaction|tx)\s*(?:#|[`']?)\s*{re.escape(tid)}\b.*?\b{lvl}\b",
                    ]
                    for pat in patterns:
                        if re.search(pat, answer, re.IGNORECASE):
                            issues.append(
                                f"Risk level mismatch in response text for TX {tid}: text claims '{lvl}' risk but canonical backend risk is '{backend_risk}'"
                            )
                            break

        return VerificationResult(ok=len(issues) == 0, issues=issues)


verifier = Verifier()

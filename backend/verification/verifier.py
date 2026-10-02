from __future__ import annotations

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


verifier = Verifier()

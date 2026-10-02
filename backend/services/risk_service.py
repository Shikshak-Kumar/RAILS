from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from backend.db.repositories.transaction_repository import transaction_repository
from backend.schemas.risk import ModelResult, RiskAssessment
from backend.schemas.transaction import TransactionInput
from backend.tools.runner import run_tool
from backend.evidence.store import evidence_store
from backend.verification.verifier import verifier
from backend.services.case_service import case_service


def _risk_rank(score: float | None) -> str:
    if score is None:
        return 'LOW'
    if score >= 0.75:
        return 'CRITICAL'
    if score >= 0.55:
        return 'HIGH'
    if score >= 0.35:
        return 'MEDIUM'
    return 'LOW'


class RiskService:
    def __init__(self, repository: Any | None = None) -> None:
        self.repository = repository or transaction_repository

    def _normalize_payload(self, payload: TransactionInput | dict[str, Any] | Any) -> TransactionInput:
        if isinstance(payload, TransactionInput):
            return payload
        if hasattr(payload, 'transaction_id'):
            return TransactionInput(
                transaction_id=str(getattr(payload, 'transaction_id', 'tx-auto')),
                sender_id=str(getattr(payload, 'sender_id', 'unknown')),
                receiver_id=str(getattr(payload, 'receiver_id', 'unknown')),
                amount=float(getattr(payload, 'amount', 0.0) or 0.0),
                timestamp=getattr(payload, 'timestamp', None),
                transaction_type=getattr(payload, 'transaction_type', None),
                currency=getattr(payload, 'currency', None),
            )
        if hasattr(payload, 'get'):
            return TransactionInput(
                transaction_id=str(payload.get('transaction_id') or payload.get('id') or 'tx-auto'),
                sender_id=str(payload.get('sender_id') or payload.get('sender_account') or 'unknown'),
                receiver_id=str(payload.get('receiver_id') or payload.get('receiver_account') or 'unknown'),
                amount=float(payload.get('amount') or payload.get('amount_paid') or 0.0),
                timestamp=payload.get('timestamp'),
                transaction_type=payload.get('transaction_type') or payload.get('payment_format'),
                currency=payload.get('currency') or payload.get('payment_currency'),
            )
        raise TypeError(f'Unsupported transaction payload type: {type(payload)!r}')

    def analyze_transaction(self, payload: TransactionInput | dict[str, Any], *, sender_history: list[dict[str, Any]] | None = None, receiver_history: list[dict[str, Any]] | None = None, pair_history: list[dict[str, Any]] | None = None) -> RiskAssessment:
        payload = self._normalize_payload(payload)
        tx = self.repository.upsert(payload)

        # 1. Execute ML/Deterministic tools and capture evidence
        tool_results = []
        evidence_ids = []

        try:
            fraud_res = run_tool('fraud_check',
                transaction_id=tx.transaction_id,
                sender_id=tx.sender_id,
                receiver_id=tx.receiver_id,
                amount=tx.amount,
                timestamp=tx.timestamp,
                sender_history=sender_history or self.repository.account_history(tx.sender_id),
                receiver_history=receiver_history or self.repository.account_history(tx.receiver_id),
                pair_history=pair_history,
                currency=tx.currency,
                transaction_type=tx.transaction_type,
            )
            fraud_ev = evidence_store.add(tool_name='fraud_check', tool_output=fraud_res)
            tool_results.append(('fraud_check', fraud_res, fraud_ev.evidence_id))
            evidence_ids.append(fraud_ev.evidence_id)
        except Exception as exc:
            fraud_res = {'error': str(exc)}
            tool_results.append(('fraud_check', fraud_res, 'ev-error'))

        try:
            anomaly_res = run_tool('anomaly_check',
                transaction_id=tx.transaction_id,
                sender_id=tx.sender_id,
                receiver_id=tx.receiver_id,
                amount=tx.amount,
                timestamp=tx.timestamp,
                sender_history=sender_history or self.repository.account_history(tx.sender_id),
                receiver_history=receiver_history or self.repository.account_history(tx.receiver_id),
                pair_history=pair_history,
                currency=tx.currency,
                transaction_type=tx.transaction_type,
            )
            anomaly_ev = evidence_store.add(tool_name='anomaly_check', tool_output=anomaly_res)
            tool_results.append(('anomaly_check', anomaly_res, anomaly_ev.evidence_id))
            evidence_ids.append(anomaly_ev.evidence_id)
        except Exception as exc:
            anomaly_res = {'error': str(exc)}
            tool_results.append(('anomaly_check', anomaly_res, 'ev-error'))

        try:
            account_res = run_tool('account_risk_check',
                account_id=tx.sender_id,
                history=self.repository.account_history(tx.sender_id),
            )
            account_ev = evidence_store.add(tool_name='account_risk_check', tool_output=account_res)
            tool_results.append(('account_risk_check', account_res, account_ev.evidence_id))
            evidence_ids.append(account_ev.evidence_id)
        except Exception as exc:
            account_res = {'error': str(exc)}
            tool_results.append(('account_risk_check', account_res, 'ev-error'))

        # 2. Extract Signals & Scores
        fraud = fraud_res if 'error' not in fraud_res else {}
        anomaly = anomaly_res if 'error' not in anomaly_res else {}
        account_signal = account_res if 'error' not in account_res else {}

        score_candidates = [
            float(fraud.get('fraud_probability') or 0.0),
            float(anomaly.get('anomaly_score') or 0.0),
            float(account_signal.get('risk_score') or 0.0),
        ]
        overall_score = max(score_candidates) if score_candidates else 0.0
        risk_level = _risk_rank(overall_score)
        
        all_signals = list(dict.fromkeys((fraud.get('signals', []) or []) + (anomaly.get('signals', []) or []) + (account_signal.get('signals', []) or [])))

        # 3. LLM Orchestrator Explanation
        from backend.api.copilot import ToolCallResult, _build_grounded_answer
        tcr = [ToolCallResult(tool=t, result=r, evidence_id=e) for t, r, e in tool_results if e != 'ev-error']
        explanation = _build_grounded_answer(
            question=f"Analyze transaction {tx.transaction_id}",
            intent="transaction",
            tool_calls=tcr,
            risk_signals=all_signals
        )

        # 4. Verifier Validates Assessment
        analysis_status = "completed"
        if any('error' in r for t, r, e in tool_results):
            analysis_status = "partial_failure"

        assessment = RiskAssessment(
            transaction_id=tx.transaction_id,
            fraud_probability=fraud.get('fraud_probability'),
            anomaly_score=anomaly.get('anomaly_score'),
            risk_score=overall_score,
            risk_level=risk_level,
            signals=all_signals,
            risk_types=["fraud"] if float(fraud.get('fraud_probability') or 0) > 0.5 else [],
            model_results=[
                ModelResult(model_name='fraud_model', model_version=fraud.get('model_version'), score=fraud.get('fraud_probability'), risk_level=fraud.get('risk_level'), output_key='fraud_probability'),
                ModelResult(model_name='anomaly_model', model_version=anomaly.get('model_version'), score=anomaly.get('anomaly_score'), risk_level=anomaly.get('risk_level'), output_key='anomaly_score'),
                ModelResult(model_name='account_risk_model', model_version=account_signal.get('model_version'), score=account_signal.get('risk_score'), risk_level=account_signal.get('risk_level'), output_key='risk_score'),
            ],
            model_versions=[
                str(fraud.get('model_version') or ''),
                str(anomaly.get('model_version') or ''),
                str(account_signal.get('model_version') or ''),
            ],
            evidence_ids=evidence_ids,
            explanation=explanation,
            created_at=datetime.now(timezone.utc).isoformat(),
            analysis_status=analysis_status
        )

        vr = verifier.verify_assessment(assessment, evidence_ids=evidence_ids)
        if not vr.ok:
            assessment.analysis_status = f"verification_failed: {', '.join(vr.issues)}"

        # 5. Case creation and STR draft for HIGH / CRITICAL
        if assessment.risk_level in ('HIGH', 'CRITICAL') and vr.ok:
            case = case_service.create_case(
                summary=f"Automated Case for {assessment.risk_level} Risk Transaction {tx.transaction_id}",
                status="OPEN"
            )
            # Add to assessment explanation to simulate attaching case
            assessment.explanation += f"\n\nAutomatically created Case: {case['case_id']}."
            assessment.explanation += f"\nAI GENERATED DRAFT: STR required for {tx.transaction_id} due to {assessment.risk_level} risk."

        return assessment

    def account_risk(self, account_id: str) -> dict[str, Any]:
        history = self.repository.account_history(account_id)
        result = run_tool('account_risk_check', account_id=account_id, history=history)
        return result


risk_service = RiskService()

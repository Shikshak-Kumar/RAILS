import logging
from datetime import datetime, timezone
from typing import Any

from backend.db.repositories.alert_repository import alert_repository
from backend.db.repositories.transaction_repository import transaction_repository, _parse_timestamp
from backend.evidence.store import evidence_store
from backend.schemas.risk import ModelResult, RiskAssessment
from backend.schemas.transaction import TransactionInput
from backend.services.case_service import case_service
from backend.tools.runner import run_tool
from backend.verification.verifier import verifier

logger = logging.getLogger("risk_service")


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
                timestamp=_parse_timestamp(getattr(payload, 'timestamp', datetime.now(timezone.utc))),
                transaction_type=getattr(payload, 'transaction_type', None),
                currency=getattr(payload, 'currency', None),
            )
        if hasattr(payload, 'get'):
            raw_ts = payload.get('timestamp') or payload.get('Timestamp') or datetime.now(timezone.utc)
            return TransactionInput(
                transaction_id=str(payload.get('transaction_id') or payload.get('id') or 'tx-auto'),
                sender_id=str(payload.get('sender_id') or payload.get('sender_account') or 'unknown'),
                receiver_id=str(payload.get('receiver_id') or payload.get('receiver_account') or 'unknown'),
                amount=float(payload.get('amount') or payload.get('amount_paid') or 0.0),
                timestamp=_parse_timestamp(raw_ts),
                transaction_type=payload.get('transaction_type') or payload.get('payment_format'),
                currency=payload.get('currency') or payload.get('payment_currency'),
            )
        raise TypeError(f'Unsupported transaction payload type: {type(payload)!r}')

    def analyze_transaction(
        self,
        payload: TransactionInput | dict[str, Any],
        *,
        sender_history: list[dict[str, Any]] | None = None,
        receiver_history: list[dict[str, Any]] | None = None,
        pair_history: list[dict[str, Any]] | None = None,
    ) -> RiskAssessment:
        tx = self._normalize_payload(payload)
        tx_timestamp = _parse_timestamp(tx.timestamp)

        # 1. Fetch strictly prior history (timestamp < tx_timestamp) before persistence
        # This completely avoids self-contamination / data leakage
        s_hist = sender_history if sender_history is not None else self.repository.account_history(tx.sender_id, before=tx_timestamp)
        r_hist = receiver_history if receiver_history is not None else self.repository.account_history(tx.receiver_id, before=tx_timestamp)
        p_hist = pair_history if pair_history is not None else self.repository.pair_history(tx.sender_id, tx.receiver_id, before=tx_timestamp)

        tool_results = []
        evidence_ids = []

        # 2. Execute Detection Tools via run_tool and capture audit evidence
        # Tool: fraud_check
        try:
            fraud_res = run_tool(
                'fraud_check',
                transaction_id=tx.transaction_id,
                sender_id=tx.sender_id,
                receiver_id=tx.receiver_id,
                amount=tx.amount,
                timestamp=tx_timestamp,
                sender_history=s_hist,
                receiver_history=r_hist,
                pair_history=p_hist,
                currency=tx.currency,
                transaction_type=tx.transaction_type,
            )
            fraud_ev = evidence_store.add(tool_name='fraud_check', tool_output=fraud_res)
            tool_results.append(('fraud_check', fraud_res, fraud_ev.evidence_id))
            evidence_ids.append(fraud_ev.evidence_id)
        except Exception as exc:
            logger.error(f"fraud_check tool error for txn {tx.transaction_id}: {exc}")
            fraud_res = {'error': str(exc)}
            tool_results.append(('fraud_check', fraud_res, 'ev-error'))

        # Tool: anomaly_check
        try:
            anomaly_res = run_tool(
                'anomaly_check',
                transaction_id=tx.transaction_id,
                sender_id=tx.sender_id,
                receiver_id=tx.receiver_id,
                amount=tx.amount,
                timestamp=tx_timestamp,
                sender_history=s_hist,
                receiver_history=r_hist,
                pair_history=p_hist,
                currency=tx.currency,
                transaction_type=tx.transaction_type,
            )
            anomaly_ev = evidence_store.add(tool_name='anomaly_check', tool_output=anomaly_res)
            tool_results.append(('anomaly_check', anomaly_res, anomaly_ev.evidence_id))
            evidence_ids.append(anomaly_ev.evidence_id)
        except Exception as exc:
            logger.error(f"anomaly_check tool error for txn {tx.transaction_id}: {exc}")
            anomaly_res = {'error': str(exc)}
            tool_results.append(('anomaly_check', anomaly_res, 'ev-error'))

        # Tool: account_risk_check
        try:
            account_res = run_tool(
                'account_risk_check',
                account_id=tx.sender_id,
                history=s_hist,
                before=tx_timestamp,
            )
            account_ev = evidence_store.add(tool_name='account_risk_check', tool_output=account_res)
            tool_results.append(('account_risk_check', account_res, account_ev.evidence_id))
            evidence_ids.append(account_ev.evidence_id)
        except Exception as exc:
            logger.error(f"account_risk_check tool error for account {tx.sender_id}: {exc}")
            account_res = {'error': str(exc)}
            tool_results.append(('account_risk_check', account_res, 'ev-error'))

        # Tool: rules_check (Deterministic rules)
        try:
            rules_res = run_tool(
                'rules_check',
                transaction_id=tx.transaction_id,
                sender_id=tx.sender_id,
                receiver_id=tx.receiver_id,
                amount=tx.amount,
                timestamp=tx_timestamp,
                sender_history=s_hist,
                receiver_history=r_hist,
                pair_history=p_hist,
            )
            rules_ev = evidence_store.add(tool_name='rules_check', tool_output=rules_res)
            tool_results.append(('rules_check', rules_res, rules_ev.evidence_id))
            evidence_ids.append(rules_ev.evidence_id)
        except Exception as exc:
            logger.error(f"rules_check tool error for txn {tx.transaction_id}: {exc}")
            rules_res = {'error': str(exc)}
            tool_results.append(('rules_check', rules_res, 'ev-error'))

        # 3. Signals & Score Combination via Deterministic Escalation
        fraud = fraud_res if 'error' not in fraud_res else {}
        anomaly = anomaly_res if 'error' not in anomaly_res else {}
        account_signal = account_res if 'error' not in account_res else {}
        rules_signal = rules_res if 'error' not in rules_res else {}

        fraud_prob = fraud.get('fraud_probability')
        anomaly_sc = anomaly.get('anomaly_score')
        account_sc = account_signal.get('risk_score')
        rule_level = rules_signal.get('rule_risk_level', 'LOW')

        all_signals = list(dict.fromkeys(
            (fraud.get('signals', []) or []) +
            (anomaly.get('signals', []) or []) +
            (account_signal.get('signals', []) or []) +
            (rules_signal.get('signals', []) or [])
        ))

        # Deterministic escalation:
        # Fraud thresholds: medium >= 0.00171, high >= 0.1325, critical >= 0.1562
        # Anomaly thresholds: medium >= 0.95, high >= 0.99, critical >= 0.999
        # Account thresholds: medium >= 0.655, high >= 0.750, critical >= 0.832
        is_crit = (
            (fraud_prob is not None and fraud_prob >= 0.156) or
            (anomaly_sc is not None and anomaly_sc >= 0.999) or
            rule_level == 'CRITICAL' or
            ('critical_anomaly_outlier' in all_signals) or
            ('elevated_fraud_probability' in all_signals and rule_level in {'HIGH', 'CRITICAL'})
        )
        is_high = (
            is_crit or
            (fraud_prob is not None and fraud_prob >= 0.132) or
            (anomaly_sc is not None and anomaly_sc >= 0.99 and (account_sc or 0.0) >= 0.65) or
            (rule_level == 'HIGH') or
            ('rapid_movement_through_accounts' in all_signals and (fraud_prob or 0.0) >= 0.01)
        )
        is_med = (
            is_high or
            (fraud_prob is not None and fraud_prob > 0.0025) or
            (anomaly_sc is not None and anomaly_sc >= 0.95) or
            (account_sc is not None and account_sc >= 0.655) or
            rule_level == 'MEDIUM'
        )

        if is_crit:
            risk_level = 'CRITICAL'
            overall_score = max(0.85, fraud_prob or 0.0, anomaly_sc or 0.0, account_sc or 0.0)
        elif is_high:
            risk_level = 'HIGH'
            overall_score = max(0.65, fraud_prob or 0.0, anomaly_sc or 0.0, account_sc or 0.0)
        elif is_med:
            risk_level = 'MEDIUM'
            overall_score = max(0.40, fraud_prob or 0.0, anomaly_sc or 0.0, account_sc or 0.0)
        else:
            risk_level = 'LOW'
            overall_score = min(0.20, max(0.02, fraud_prob or 0.0, (anomaly_sc or 0.0) * 0.2))

        overall_score = float(round(max(0.0, min(1.0, overall_score)), 4))

        # 4. Status determination & Verifier
        analysis_status = "completed"
        if any('error' in r for _, r, _ in tool_results):
            analysis_status = "partial_failure"

        # 5. Build Grounded Explanation from recorded tool evidence
        from backend.api.copilot import ToolCallResult, _build_grounded_answer
        tcr = [ToolCallResult(tool=t, result=r, evidence_id=e) for t, r, e in tool_results if e != 'ev-error']
        explanation = _build_grounded_answer(
            question=f"Analyze transaction {tx.transaction_id}",
            intent="transaction",
            tool_calls=tcr,
            risk_signals=all_signals
        )

        assessment = RiskAssessment(
            transaction_id=tx.transaction_id,
            fraud_probability=fraud.get('fraud_probability'),
            anomaly_score=anomaly.get('anomaly_score'),
            risk_score=overall_score,
            risk_level=risk_level,
            signals=all_signals,
            risk_types=["fraud"] if (fraud.get('fraud_probability') or 0.0) >= 0.132 else [],
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

        # 6. Verifier Check
        vr = verifier.verify_assessment(assessment, evidence_ids=evidence_ids)
        if not vr.ok:
            assessment.analysis_status = f"verification_failed: {', '.join(vr.issues)}"

        # 7. Persist Transaction (Safe now that features are computed without contamination)
        self.repository.upsert(tx)

        # 8. Create Alert & Case for HIGH / CRITICAL
        alert_id = None
        case_id = None
        if assessment.risk_level in ('HIGH', 'CRITICAL') and vr.ok:
            alert = alert_repository.create_or_get_alert(
                transaction_id=tx.transaction_id,
                risk_level=assessment.risk_level,
                risk_score=assessment.risk_score or 0.0,
                fraud_probability=assessment.fraud_probability,
                anomaly_score=assessment.anomaly_score,
                signals=assessment.signals,
                evidence_ids=assessment.evidence_ids,
            )
            alert_id = alert['alert_id']

            case = case_service.create_case(
                summary=f"Automated Case for {assessment.risk_level} Risk Transaction {tx.transaction_id}",
                status="OPEN",
                transaction_id=tx.transaction_id,
            )
            case_id = case['case_id']
            alert_repository.link_case(alert_id, case_id)

            assessment.explanation += f"\n\nAutomatically created Alert: {alert_id} and Case: {case_id}."
            assessment.explanation += f"\nAI GENERATED DRAFT: STR required for {tx.transaction_id} due to {assessment.risk_level} risk."

        # 9. Structured Inference Logging
        logger.info(
            f"[INFERENCE] txn={tx.transaction_id} "
            f"fraud_score={assessment.fraud_probability} anomaly_score={assessment.anomaly_score} "
            f"account_score={account_signal.get('risk_score')} risk_level={assessment.risk_level} "
            f"overall_score={assessment.risk_score} signals_count={len(all_signals)} "
            f"status={assessment.analysis_status} alert_id={alert_id} case_id={case_id} "
            f"verified={vr.ok}"
        )

        return assessment

    def account_risk(self, account_id: str) -> dict[str, Any]:
        history = self.repository.account_history(account_id)
        result = run_tool('account_risk_check', account_id=account_id, history=history)
        return result


risk_service = RiskService()

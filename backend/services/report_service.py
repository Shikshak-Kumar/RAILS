from __future__ import annotations

from datetime import datetime, timezone
import os
import time
from typing import Any
from uuid import uuid4

from backend.db.repositories.alert_repository import alert_repository
from backend.db.repositories.report_repository import report_repository
from backend.db.repositories.transaction_repository import transaction_repository
from backend.reports.generator import report_generator
from backend.schemas.reports import RegulatoryCitationItem, STRDraft, SupportingEvidenceItem
from backend.services.case_service import case_service
from backend.services.regulatory_rag_service import regulatory_rag_service
from backend.services.risk_service import risk_service
from backend.verification.verifier import verifier


class ReportService:
    def generate_str_draft(
        self,
        case_id: str,
        transaction_id: str | None = None,
        title: str | None = None,
        narrative: str | None = None,
    ) -> dict[str, Any]:
        t_start = time.perf_counter()

        t0 = time.perf_counter()
        case = case_service.get_case(case_id)
        if case.get('status') == 'NOT_FOUND':
            raise ValueError(f"Case {case_id} not found")
        t_case = (time.perf_counter() - t0) * 1000

        tx_id = transaction_id or case.get('transaction_id') or ''
        case_summary = case.get('summary', '') or case.get('description', '')

        t0 = time.perf_counter()
        tx = transaction_repository.get(tx_id) if tx_id else None
        t_tx = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        alert = alert_repository.get_alert_by_tx(tx_id) if tx_id else None
        canonical = risk_service.get_canonical_risk(tx_id, tx) if tx_id else {
            'risk_level': case.get('risk_level', 'LOW'),
            'risk_score': 0.0,
            'fraud_probability': 0.0,
            'anomaly_score': 0.0,
            'signals': [],
        }

        risk_level = alert.get('risk_level') if alert else canonical.get('risk_level', case.get('risk_level', 'LOW'))
        fraud_prob = float(alert.get('fraud_probability') if (alert and alert.get('fraud_probability') is not None) else canonical.get('fraud_probability', 0.0))
        anomaly_score = float(alert.get('anomaly_score') if (alert and alert.get('anomaly_score') is not None) else canonical.get('anomaly_score', 0.0))
        signals = list(alert.get('signals') if alert else canonical.get('signals', []))

        evidence_ids = [f"ev-case-{case_id}"]
        if tx_id:
            evidence_ids.append(f"ev-tx-{tx_id}")
        if alert and alert.get('evidence_ids'):
            evidence_ids.extend(alert['evidence_ids'])
        evidence_ids = list(dict.fromkeys(evidence_ids))

        supporting_evidence_items: list[SupportingEvidenceItem] = []
        for eid in evidence_ids:
            if 'case' in eid:
                purpose = "Case initialization and surveillance anomaly detection"
                source = "Case Management Engine"
            elif 'tx' in eid:
                purpose = "Transaction ledger transfer details and counterparty accounts"
                source = "Core Banking Ledger"
            else:
                purpose = "Model inference outputs and risk indicators"
                source = "Surveillance Risk Pipeline"
            supporting_evidence_items.append(
                SupportingEvidenceItem(evidence_id=eid, purpose=purpose, source=source)
            )
        t_ev = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        rag_res = regulatory_rag_service.search("FinCEN SAR filing Suspicious Activity Report BSA requirements", limit=2)
        raw_chunks = rag_res.get("chunks", []) if isinstance(rag_res, dict) else []
        regulatory_context_items: list[RegulatoryCitationItem] = []
        citation_ids: list[str] = []

        for chunk in raw_chunks:
            cid = chunk.get("chunk_id", "")
            if not cid:
                continue
            citation_ids.append(cid)
            summary_txt = chunk.get("chunk_text", "")
            if len(summary_txt) > 280:
                summary_txt = summary_txt[:277] + "..."
            regulatory_context_items.append(
                RegulatoryCitationItem(
                    citation_id=cid,
                    authority=chunk.get("authority", "FinCEN"),
                    document_name=chunk.get("document_name", "SAR Regulations"),
                    jurisdiction=chunk.get("jurisdiction", "US"),
                    section=chunk.get("section"),
                    page_number=chunk.get("page_number"),
                    summary=summary_txt,
                )
            )

        if citation_ids:
            v_res = verifier.verify_regulatory_retrieval(citation_ids)
            if not v_res.ok:
                regulatory_context_items = [
                    item for item in regulatory_context_items if item.citation_id in v_res.evidence_ids
                ]
                citation_ids = [c for c in citation_ids if c in v_res.evidence_ids]
        t_reg = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        institution = os.getenv("REPORTING_FINANCIAL_INSTITUTION") or os.getenv("FINANCIAL_INSTITUTION_NAME") or "Reporting Financial Institution: Not configured"

        if tx and tx.timestamp:
            if isinstance(tx.timestamp, datetime):
                tx_date = tx.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
            else:
                tx_date = str(tx.timestamp)
        else:
            tx_date = "Not available in source data"

        amount = float(tx.amount) if tx and tx.amount is not None else 0.0
        currency = str(tx.currency) if tx and tx.currency else "USD"
        payment_method = str(tx.transaction_type) if tx and tx.transaction_type else "Electronic Transfer"
        sender_account = str(tx.sender_id) if tx and tx.sender_id else (case_summary if "ACC" in case_summary else "Unknown Sender")
        receiver_account = str(tx.receiver_id) if tx and tx.receiver_id else "Unknown Receiver"

        risk_indicators = []
        for s in signals:
            if s == "new_counterparty":
                risk_indicators.append("new_counterparty: First recorded transaction between counterparties")
            elif s == "high_velocity":
                risk_indicators.append("high_velocity: Transaction velocity exceeds baseline historical frequency")
            elif s == "amount_outlier":
                risk_indicators.append("amount_outlier: Transfer amount deviates materially from account history")
            elif s == "rapid_drain":
                risk_indicators.append("rapid_drain: Rapid outflow of funds following significant deposit")
            elif s == "structuring":
                risk_indicators.append("structuring: Repeated transactions structured below reporting thresholds")
            else:
                risk_indicators.append(f"{s}: Surveillance typology indicator triggered")
        if not risk_indicators:
            risk_indicators = ["Surveillance rule threshold triggers"]

        report_id = f"rep-{uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        exec_summary = (
            f"Automated risk surveillance flagged transaction {tx_id or 'N/A'} associated with internal case "
            f"{case_id} for mandatory compliance review. Multi-model risk evaluation assigned a canonical "
            f"{risk_level} risk tier (fraud probability: {fraud_prob:.2%}, anomaly score: {anomaly_score:.3f}). "
            f"Observed behavioral signals include {', '.join(signals) if signals else 'surveillance threshold flags'}."
        )

        if narrative and len(narrative.strip()) > 30:
            suspicious_activity = narrative.strip()
        else:
            suspicious_activity = (
                f"On {tx_date}, an electronic transaction of {currency} {amount:,.2f} was recorded from "
                f"sender account {sender_account} to receiver account {receiver_account} via {payment_method}. "
                f"Surveillance detection systems identified pattern anomalies deviating from historical counterparties. "
                f"The transaction triggered flags: {', '.join(signals) if signals else 'elevated risk score'}, "
                f"warranting formalized suspicious activity review under BSA/AML standards."
            )

        tx_details = {
            "transaction_id": tx_id or "N/A",
            "date": tx_date,
            "amount": amount,
            "currency": currency,
            "payment_method": payment_method,
            "sender_account": sender_account,
            "receiver_account": receiver_account,
        }

        draft = STRDraft(
            report_id=report_id,
            case_id=case_id,
            report_type="STR",
            status="DRAFT",
            reporting_institution=institution,
            internal_case_id=case_id,
            transaction_id=tx_id or "N/A",
            transaction_date=tx_date,
            transaction_amount=amount,
            currency=currency,
            sender_account=sender_account,
            receiver_account=receiver_account,
            payment_method=payment_method,
            risk_level=risk_level,
            fraud_probability=fraud_prob,
            anomaly_score=anomaly_score,
            risk_signals=signals,
            executive_summary=exec_summary,
            suspicious_activity_description=suspicious_activity,
            transaction_details=tx_details,
            risk_indicators=risk_indicators,
            regulatory_context=regulatory_context_items,
            supporting_evidence=supporting_evidence_items,
            analyst_notes="Compliance review required. Review KYC files and source-of-funds documents prior to filing.",
            recommended_next_step="Conduct secondary compliance audit and submit for human officer approval.",
            generated_at=now_iso,
            evidence_ids=evidence_ids,
            regulatory_citation_ids=citation_ids,
        )

        report_title = title or f"STR Filing Draft — Case {case_id}"
        formatted_body = report_generator.format_text_report(
            title=report_title,
            body=suspicious_activity,
            structured_data=draft.model_dump(mode="json"),
        )
        t_gen = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        created_record = report_repository.create_report(
            case_id=case_id,
            title=report_title,
            body=formatted_body,
            report_id=report_id,
            report_type="STR",
            status="DRAFT",
            evidence_ids=evidence_ids,
            structured_data=draft.model_dump(mode="json"),
        )
        t_persist = (time.perf_counter() - t0) * 1000
        t_total = (time.perf_counter() - t_start) * 1000

        created_record["generation_metrics"] = {
            "case_retrieval_ms": round(t_case, 2),
            "transaction_retrieval_ms": round(t_tx, 2),
            "evidence_retrieval_ms": round(t_ev, 2),
            "regulatory_retrieval_ms": round(t_reg, 2),
            "generation_ms": round(t_gen, 2),
            "persistence_ms": round(t_persist, 2),
            "total_ms": round(t_total, 2),
        }
        return created_record


report_service = ReportService()

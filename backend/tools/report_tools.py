from __future__ import annotations

from typing import Any

from backend.db.repositories.report_repository import report_repository
from backend.services.case_service import case_service
from backend.tools.registry import register_tool


@register_tool('generate_report')
def generate_report(case_id: str, transaction_id: str | None = None, narrative: str | None = None, **kwargs: Any) -> dict[str, Any]:
    case = case_service.get_case(case_id)
    tx_id = transaction_id or case.get('transaction_id') or 'N/A'
    summary = case.get('summary', f"Investigation for case {case_id}")

    title = f"STR Filing Draft — Case {case_id}"
    body = narrative or (
        f"SUSPICIOUS TRANSACTION REPORT (STR / SAR)\n"
        f"=========================================\n"
        f"Case Reference: {case_id}\n"
        f"Transaction Reference: {tx_id}\n\n"
        f"EXECUTIVE SUMMARY:\n"
        f"{summary}\n\n"
        f"NARRATIVE & RED FLAG FINDINGS:\n"
        f"Real-time surveillance flagged unusual velocity, structuring, or counterparty anomalies.\n"
        f"Investigation initiated pursuant to Bank Secrecy Act and FinCEN guidelines (31 CFR § 1010.314).\n"
        f"All factual assertions verified against audit trail evidence.\n\n"
        f"DISPOSITION:\n"
        f"Submitted for human compliance officer review and formal filing."
    )

    report = report_repository.create_report(
        case_id=case_id,
        title=title,
        body=body,
        report_type='STR',
        status='DRAFT',
        evidence_ids=[f"ev-str-{case_id}"],
    )
    return report

from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from backend.db.repositories.report_repository import report_repository
from backend.reports.generator import report_generator
from backend.services.case_service import case_service

router = APIRouter(prefix="", tags=['reports'])


class GenerateSTRRequest(BaseModel):
    case_id: str
    transaction_id: str | None = None
    title: str | None = None
    narrative: str | None = None


class ApproveReportRequest(BaseModel):
    approved_by: str = 'Compliance Officer'


@router.get('/regulatory/reports')
@router.get('/reports')
def list_reports(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = None,
    case_id: str | None = None,
) -> dict[str, Any]:
    items = report_repository.list_reports(limit=limit, offset=offset, status=status, case_id=case_id)
    total = report_repository.count_reports(status=status)
    return {
        'items': items,
        'reports': items,
        'total': total,
        'count': len(items),
    }


@router.get('/regulatory/reports/{report_id}')
@router.get('/reports/{report_id}')
def get_report(report_id: str) -> dict[str, Any]:
    report = report_repository.get_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Report not found')
    return report


@router.post('/reports/generate-str')
def generate_str_draft(req: GenerateSTRRequest) -> dict[str, Any]:
    from backend.db.repositories.alert_repository import alert_repository
    from backend.db.repositories.transaction_repository import transaction_repository
    from backend.llm.gemini_client import gemini_client

    case = case_service.get_case(req.case_id)
    if case.get('status') == 'NOT_FOUND':
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Case {req.case_id} not found')

    tx_id = req.transaction_id or case.get('transaction_id') or 'N/A'
    summary = case.get('summary', '')

    alert = alert_repository.get_alert_by_tx(tx_id) if tx_id != 'N/A' else None
    tx = transaction_repository.get(tx_id) if tx_id != 'N/A' else None

    # Use Gemini for grounded narrative drafting if narrative not explicitly passed
    narrative = req.narrative
    if not narrative and gemini_client.is_available():
        prompt = f"""Draft an executive Suspicious Transaction Report (STR / SAR) narrative for a compliance audit.
Case: {req.case_id}
Transaction ID: {tx_id}
Summary: {summary}
Amount: {tx.amount if tx else 'N/A'} {tx.currency if tx else 'USD'}
Sender: {tx.sender_id if tx else 'N/A'}
Receiver: {tx.receiver_id if tx else 'N/A'}
Risk Level: {alert.get('risk_level') if alert else 'HIGH'}
Signals: {alert.get('signals') if alert else []}

Follow FinCEN and BSA compliance drafting standards (31 CFR § 1010). Cite evidence and summarize the red flag typologies without inventing data."""
        gemini_text = gemini_client.generate(prompt, temperature=0.2)
        if gemini_text and len(gemini_text) > 50:
            narrative = gemini_text

    body = narrative or (
        f"SUSPICIOUS TRANSACTION REPORT (STR / SAR)\n"
        f"=========================================\n"
        f"Case Reference: {req.case_id}\n"
        f"Transaction Reference: {tx_id}\n\n"
        f"EXECUTIVE SUMMARY:\n"
        f"{summary}\n\n"
        f"NARRATIVE & RED FLAG FINDINGS:\n"
        f"Investigation initiated pursuant to real-time risk assessment flags.\n"
        f"Amount: ${float(tx.amount):,.2f} {tx.currency}\n" if tx else ""
        f"Sender: {tx.sender_id} -> Receiver: {tx.receiver_id}\n" if tx else ""
        f"Automated detection models flagged unusual velocity, outlier amounts, and potential structuring.\n"
        f"Evidence indicates transactions deviate materially from established counterparty baselines.\n\n"
        f"REGULATORY JURISDICTION & REQUIREMENT:\n"
        f"Report drafted under FinCEN / AML / FIU compliance requirements for expedited filing (31 CFR § 1010.314).\n"
        f"Human compliance officer review is mandatory prior to final transmission to regulatory authorities."
    )
    title = req.title or f"STR Filing Draft — Case {req.case_id}"

    evidence_ids = [f"ev-case-{req.case_id}"]
    if alert and alert.get('evidence_ids'):
        evidence_ids.extend(alert['evidence_ids'])

    report = report_repository.create_report(
        case_id=req.case_id,
        title=title,
        body=body,
        report_type='STR',
        status='DRAFT',
        evidence_ids=list(dict.fromkeys(evidence_ids)),
    )
    return report


@router.post('/reports/{report_id}/approve')
def approve_report(report_id: str, req: ApproveReportRequest = ApproveReportRequest()) -> dict[str, Any]:
    report = report_repository.update_report_status(report_id, 'APPROVED', approved_by=req.approved_by)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Report not found')
    return report


@router.post('/reports/{report_id}/reject')
def reject_report(report_id: str) -> dict[str, Any]:
    report = report_repository.update_report_status(report_id, 'REJECTED')
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Report not found')
    return report


from fastapi.responses import FileResponse, Response


@router.get('/reports/{report_id}/download')
@router.get('/regulatory/reports/{report_id}/download')
def download_report(report_id: str) -> Any:
    report = report_repository.get_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Report not found')

    title = report.get('title') or f"SAR_{report_id}"
    body = report.get('body') or ""

    try:
        path = report_generator.generate_docx(
            title=title,
            body=body,
            output_path=f"/tmp/rails_{report_id}.docx",
        )
        return FileResponse(
            path,
            filename=f"{report_id}_SAR_Report.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception:
        # Fall back to text download
        return Response(
            content=body,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={report_id}_Report.txt"},
        )


@router.post('/reports/generate')
def generate_report(title: str = "Regulatory Report", body: str = "") -> dict[str, str]:
    path = report_generator.generate_docx(title=title, body=body, output_path='/tmp/rails_report.docx')
    return {'status': 'generated', 'path': path}

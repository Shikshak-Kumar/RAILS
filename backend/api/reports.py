from __future__ import annotations

from typing import Any
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from backend.db.repositories.report_repository import report_repository
from backend.reports.generator import report_generator
from backend.services.report_service import report_service

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
    norm_status = None if not status or status.upper() == 'ALL' else status.upper()
    items = report_repository.list_reports(limit=limit, offset=offset, status=norm_status, case_id=case_id)
    total = report_repository.count_reports(status=norm_status)
    return {
        'items': items,
        'reports': items,
        'total': total,
        'count': len(items),
        'limit': limit,
        'offset': offset,
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
    try:
        return report_service.generate_str_draft(
            case_id=req.case_id,
            transaction_id=req.transaction_id,
            title=req.title,
            narrative=req.narrative,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"STR generation error: {e}")


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


@router.get('/reports/{report_id}/download')
@router.get('/regulatory/reports/{report_id}/download')
def download_report(report_id: str) -> Any:
    report = report_repository.get_report(report_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Report not found')

    title = report.get('title') or f"SAR_{report_id}"
    body = report.get('body') or ""
    sd = report.get('structured_data')

    try:
        path = report_generator.generate_docx(
            title=title,
            body=body,
            structured_data=sd,
            output_path=f"/tmp/rails_{report_id}.docx",
        )
        return FileResponse(
            path,
            filename=f"{report_id}_SAR_Report.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    except Exception:
        text_content = report_generator.format_text_report(title=title, body=body, structured_data=sd)
        return Response(
            content=text_content,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename={report_id}_Report.txt"},
        )


@router.post('/reports/generate')
def generate_report(title: str = "Regulatory Report", body: str = "") -> dict[str, str]:
    path = report_generator.generate_docx(title=title, body=body, output_path='/tmp/rails_report.docx')
    return {'status': 'generated', 'path': path}

from __future__ import annotations

from fastapi import APIRouter

from backend.reports.generator import report_generator

router = APIRouter(prefix="", tags=['reports'])


@router.post('/reports/generate')
def generate_report(title: str, body: str) -> dict[str, str]:
    path = report_generator.generate_docx(title=title, body=body, output_path='/tmp/rails_report.docx')
    return {'status': 'generated', 'path': path}

from __future__ import annotations

from pathlib import Path
from typing import Any
import xml.sax.saxutils as saxutils
import zipfile


class ReportGenerator:
    def format_text_report(self, *, title: str, body: str, structured_data: dict[str, Any] | None = None) -> str:
        if not structured_data:
            return f"{title}\n{'=' * len(title)}\n\n{body}"

        sd = structured_data
        reg_ctx = sd.get('regulatory_context', [])
        reg_lines = []
        for r in reg_ctx:
            auth = r.get('authority', '')
            doc = r.get('document_name', '')
            sec = r.get('section') or ''
            page = f"Page {r.get('page_number')}" if r.get('page_number') else ''
            cid = r.get('citation_id', '')
            header_parts = [p for p in [auth, doc, sec, page, f"Citation: {cid}"] if p]
            reg_lines.append(f"  * [{' | '.join(header_parts)}]\n    {r.get('summary', '')}")
        reg_str = "\n".join(reg_lines) if reg_lines else "  No specific regulatory guidance cited."

        ev_items = sd.get('supporting_evidence', [])
        ev_lines = []
        for e in ev_items:
            ev_lines.append(f"  * {e.get('evidence_id', '')}: {e.get('purpose', '')}")
        ev_str = "\n".join(ev_lines) if ev_lines else "  No explicit evidence IDs recorded."

        signals = sd.get('risk_signals', []) or sd.get('risk_indicators', [])
        sig_str = "\n".join([f"  * {s}" for s in signals]) if signals else "  Surveillance baseline threshold triggers"

        lines = [
            "SUSPICIOUS ACTIVITY REPORT — DRAFT",
            "==================================",
            f"Report Status: {sd.get('status', 'DRAFT')}",
            f"Generated At:  {sd.get('generated_at', '')}",
            "",
            "1. CASE INFORMATION",
            "-------------------",
            f"Case ID:               {sd.get('case_id', '')}",
            f"Internal Case ID:      {sd.get('internal_case_id', '')}",
            f"Report ID:             {sd.get('report_id', '')}",
            f"Report Type:           {sd.get('report_type', 'STR')}",
            f"Reporting Institution: {sd.get('reporting_institution', 'Reporting Financial Institution: Not configured')}",
            "",
            "2. TRANSACTION INFORMATION",
            "--------------------------",
            f"Transaction ID:        {sd.get('transaction_id', '')}",
            f"Transaction Date:      {sd.get('transaction_date', 'Not available in source data')}",
            f"Amount:                {float(sd.get('transaction_amount', 0)):,.2f} {sd.get('currency', 'USD')}",
            f"Payment Method:        {sd.get('payment_method', 'Electronic')}",
            f"Sender Account:        {sd.get('sender_account', '')}",
            f"Receiver Account:      {sd.get('receiver_account', '')}",
            "",
            "3. RISK ASSESSMENT",
            "------------------",
            f"Risk Level:            {sd.get('risk_level', 'LOW')}",
            f"Fraud Probability:     {float(sd.get('fraud_probability', 0)):.2%}",
            f"Anomaly Score:         {float(sd.get('anomaly_score', 0)):.3f}",
            "",
            "4. RISK INDICATORS",
            "------------------",
            sig_str,
            "",
            "5. EXECUTIVE SUMMARY",
            "--------------------",
            sd.get('executive_summary', ''),
            "",
            "6. SUSPICIOUS ACTIVITY DESCRIPTION",
            "----------------------------------",
            sd.get('suspicious_activity_description', ''),
            "",
            "7. REGULATORY CONTEXT",
            "---------------------",
            reg_str,
            "",
            "8. SUPPORTING EVIDENCE",
            "----------------------",
            ev_str,
            "",
            "9. ANALYST REVIEW & NEXT STEPS",
            "------------------------------",
            sd.get('analyst_notes', 'Compliance review required.'),
            f"Recommended Next Step: {sd.get('recommended_next_step', 'Proceed with formal compliance review.')}",
            "",
            "10. HUMAN APPROVAL DISCLAIMER",
            "-----------------------------",
            "This report is a DRAFT. Human compliance review and approval are required before filing.",
            "Suspicious activity has not been legally established, and this document does not constitute a final legal conclusion."
        ]
        return "\n".join(lines)

    def generate_docx(
        self,
        *,
        title: str,
        body: str,
        structured_data: dict[str, Any] | None = None,
        output_path: str | Path,
    ) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        text_content = self.format_text_report(title=title, body=body, structured_data=structured_data)
        paragraphs = []
        for line in text_content.split("\n"):
            clean_line = saxutils.escape(line)
            if line.startswith("===") or line.startswith("---"):
                continue
            is_header = line.isupper() and len(line) > 3 and not line.startswith("  ")
            if is_header:
                p_xml = f"<w:p><w:pPr><w:b/></w:pPr><w:r><w:rPr><w:b/><w:sz w:val=\"24\"/></w:rPr><w:t>{clean_line}</w:t></w:r></w:p>"
            elif not line.strip():
                p_xml = "<w:p><w:r><w:t> </w:t></w:r></w:p>"
            else:
                p_xml = f"<w:p><w:r><w:sz w:val=\"20\"/><w:t>{clean_line}</w:t></w:r></w:p>"
            paragraphs.append(p_xml)

        body_xml = "".join(paragraphs)
        content = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    {body_xml}
  </w:body>
</w:document>
"""
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                '[Content_Types].xml',
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>'
            )
            archive.writestr(
                '_rels/.rels',
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>'
            )
            archive.writestr('word/document.xml', content)
        return str(output)


report_generator = ReportGenerator()

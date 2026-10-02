from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any


class ReportGenerator:
    def generate_docx(self, *, title: str, body: str, output_path: str | Path) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        content = f"""<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<w:document xmlns:w=\"http://schemas.openxmlformats.org/wordprocessingml/2006/main\">
  <w:body>
    <w:p><w:r><w:t>{title}</w:t></w:r></w:p>
    <w:p><w:r><w:t>{body}</w:t></w:r></w:p>
  </w:body>
</w:document>
"""
        with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
            archive.writestr('_rels/.rels', '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
            archive.writestr('word/document.xml', content)
        return str(output)


report_generator = ReportGenerator()

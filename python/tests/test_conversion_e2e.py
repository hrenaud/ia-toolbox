"""End-to-end tests for binary format conversions with real fixtures."""

import zipfile
from pathlib import Path

import pytest

from document_worker.conversion import convert_file


class TestEndToEndConversions:
    """End-to-end tests for declared binary formats with real fixture conversion."""

    def test_convert_docx_fixture(self, tmp_path):
        """Convert a real .docx file to Markdown."""
        # Create minimal DOCX using a simple ZIP structure
        source = tmp_path / "test.docx"
        with zipfile.ZipFile(source, 'w') as zf:
            zf.writestr('_rels/.rels',
                '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>')
            zf.writestr('word/document.xml',
                '<?xml version="1.0"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>Test</w:t></w:r></w:p></w:body></w:document>')
            zf.writestr('[Content_Types].xml',
                '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Default Extension="xml" ContentType="application/xml"/>'
                '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                '</Types>')

        result = convert_file(source, tmp_path)

        assert result.status == "success", f"DOCX: {result.error_code} - {result.message}"
        assert result.output_path is not None
        output = Path(result.output_path)
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert len(content) > 0

    def test_convert_pdf_fixture(self, tmp_path):
        """Convert a real .pdf file to Markdown."""
        pdf_bytes = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>
endobj
4 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
5 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Hello World) Tj
ET
endstream
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000244 00000 n
0000000333 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
427
%%EOF
"""

        source = tmp_path / "test.pdf"
        source.write_bytes(pdf_bytes)

        result = convert_file(source, tmp_path)

        assert result.status == "success", f"PDF: {result.error_code} - {result.message}"
        assert result.output_path is not None
        assert Path(result.output_path).exists()

    def test_convert_xlsx_fixture(self, tmp_path):
        """Convert a real .xlsx file to Markdown."""
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws["A1"] = "Name"
        ws["B1"] = "Value"
        ws["A2"] = "Test"
        ws["B2"] = "42"

        source = tmp_path / "test.xlsx"
        wb.save(str(source))

        result = convert_file(source, tmp_path)

        assert result.status == "success", f"XLSX: {result.error_code} - {result.message}"
        assert result.output_path is not None
        output = Path(result.output_path)
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "Name" in content or "name" in content.lower()

    def test_convert_xls_fixture(self, tmp_path):
        """Convert a real .xls file to Markdown."""
        try:
            import xlwt
        except ImportError:
            pytest.skip("xlwt not available")

        wb = xlwt.Workbook()
        ws = wb.add_sheet("Sheet1")
        ws.write(0, 0, "Name")
        ws.write(0, 1, "Value")
        ws.write(1, 0, "Test")
        ws.write(1, 1, 42)

        source = tmp_path / "test.xls"
        wb.save(str(source))

        result = convert_file(source, tmp_path)

        assert result.status == "success", f"XLS: {result.error_code} - {result.message}"
        assert result.output_path is not None
        assert Path(result.output_path).exists()

    def test_convert_pptx_fixture(self, tmp_path):
        """Convert a real .pptx file to Markdown."""
        try:
            from pptx import Presentation
        except ImportError:
            pytest.skip("python-pptx not available")

        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[0])
        title = slide.shapes.title
        title.text = "Test Slide"

        source = tmp_path / "test.pptx"
        prs.save(str(source))

        result = convert_file(source, tmp_path)

        assert result.status == "success", f"PPTX: {result.error_code} - {result.message}"
        assert result.output_path is not None
        output = Path(result.output_path)
        assert output.exists()
        content = output.read_text(encoding="utf-8")
        assert "Test Slide" in content or "test" in content.lower()

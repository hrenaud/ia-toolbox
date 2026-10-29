"""
Real conversions for every extension the catalog advertises.

The catalog test only asserts the catalog's own contents, so it passes whether
or not a converter works. That let the branch ship a catalog declaring
``.docx``, ``.pdf``, ``.xlsx``, ``.xls`` and ``.pptx`` as convertible while
markitdown's optional readers were not installed: every one of those
conversions failed with a generic ``processing_failed``.

These cases convert a real fixture through ``convert_file`` for each declared
extension, so adding a format to the catalog without a working reader fails the
suite. The parametrisation is driven by the catalog itself, and
``test_every_declared_format_has_a_fixture`` fails if a new format arrives
without one — a fixture may never be skipped away, because a skip is exactly
how the original defect stayed invisible.
"""

import json
import struct
import zipfile
from pathlib import Path

import pytest

from document_worker.conversion import convert_file
from document_worker.formats import supported_input_formats

TEXT = "Titre\n\nUn paragraphe de test.\n"

MINIMAL_PDF = b"""%PDF-1.4
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
(Titre) Tj
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


def _write_text(path: Path) -> None:
    path.write_text(TEXT, encoding="utf-8")


def _write_csv(path: Path) -> None:
    path.write_text("Titre,Valeur\npara,42\n", encoding="utf-8")


def _write_html(path: Path) -> None:
    path.write_text(
        "<html><body><h1>Titre</h1><p>para</p></body></html>", encoding="utf-8"
    )


def _write_json(path: Path) -> None:
    path.write_text(json.dumps({"Titre": "para"}), encoding="utf-8")


def _write_jsonl(path: Path) -> None:
    path.write_text('{"Titre":"para"}\n{"Titre":"autre"}\n', encoding="utf-8")


def _write_ipynb(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "cells": [
                    {
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": ["# Titre"],
                    }
                ],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        ),
        encoding="utf-8",
    )


def _write_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("Titre.txt", TEXT)


def _write_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
        )
        archive.writestr(
            "word/document.xml",
            '<?xml version="1.0"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>Titre</w:t></w:r></w:p></w:body></w:document>",
        )


def _write_pdf(path: Path) -> None:
    path.write_bytes(MINIMAL_PDF)


def _write_xlsx(path: Path) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    workbook.active["A1"] = "Titre"
    workbook.active["A2"] = "para"
    workbook.save(str(path))


def _write_xls(path: Path) -> None:
    """
    Write a legacy BIFF2 worksheet.

    No writer for the legacy format ships with the worker's dependencies, and
    xlwt is unmaintained, so the five records xlrd needs are emitted directly:
    BOF, DIMENSIONS, one LABEL, one NUMBER, EOF.
    """

    def record(opcode: int, payload: bytes) -> bytes:
        return struct.pack("<HH", opcode, len(payload)) + payload

    label = b"Titre"
    blank_attributes = b"\x00\x00\x00"
    path.write_bytes(
        record(0x0009, struct.pack("<HH", 0x0002, 0x0010))
        + record(0x0000, struct.pack("<HHHH", 0, 0, 2, 1))
        + record(
            0x0004,
            struct.pack("<HH", 0, 0)
            + blank_attributes
            + bytes([len(label)])
            + label,
        )
        + record(
            0x0003,
            struct.pack("<HH", 1, 0) + blank_attributes + struct.pack("<d", 42.0),
        )
        + record(0x000A, b"")
    )


def _write_pptx(path: Path) -> None:
    from pptx import Presentation

    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[5])
    slide.shapes.title.text = "Titre"
    presentation.save(str(path))


def _write_epub(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            '<?xml version="1.0"?>'
            '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
            '<rootfiles><rootfile full-path="content.opf"'
            ' media-type="application/oebps-package+xml"/></rootfiles></container>',
        )
        archive.writestr(
            "content.opf",
            '<?xml version="1.0"?>'
            '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id">'
            '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
            '<dc:identifier id="id">test</dc:identifier>'
            "<dc:title>Titre</dc:title><dc:language>fr</dc:language></metadata>"
            '<manifest><item id="p1" href="p1.xhtml" media-type="application/xhtml+xml"/></manifest>'
            '<spine><itemref idref="p1"/></spine></package>',
        )
        archive.writestr(
            "p1.xhtml",
            '<?xml version="1.0"?>'
            '<html xmlns="http://www.w3.org/1999/xhtml"><body><p>para</p></body></html>',
        )


# Each declared extension maps to a fixture writer and a substring the
# converted Markdown must contain, so a converter that silently produces an
# empty or wrong document fails too.
FIXTURES: dict[str, tuple[object, str]] = {
    ".txt": (_write_text, "Titre"),
    ".text": (_write_text, "Titre"),
    ".md": (_write_text, "Titre"),
    ".markdown": (_write_text, "Titre"),
    ".csv": (_write_csv, "Titre"),
    ".html": (_write_html, "Titre"),
    ".json": (_write_json, "Titre"),
    ".jsonl": (_write_jsonl, "Titre"),
    ".ipynb": (_write_ipynb, "Titre"),
    ".zip": (_write_zip, "Titre"),
    ".docx": (_write_docx, "Titre"),
    ".pdf": (_write_pdf, "Titre"),
    ".xlsx": (_write_xlsx, "Titre"),
    ".xls": (_write_xls, "Titre"),
    ".pptx": (_write_pptx, "Titre"),
    ".epub": (_write_epub, "para"),
}

DECLARED = [fmt.extension for fmt in supported_input_formats()]


def test_every_declared_format_has_a_fixture():
    """A format may not enter the catalog without an end-to-end conversion."""
    assert sorted(FIXTURES) == sorted(DECLARED)


@pytest.mark.parametrize("extension", DECLARED)
def test_declared_format_converts(extension, tmp_path):
    write_fixture, expected = FIXTURES[extension]
    source = tmp_path / f"fixture{extension}"
    write_fixture(source)
    destination = tmp_path / "out"
    destination.mkdir()

    result = convert_file(source, destination)

    assert result.status == "success", (
        f"{extension}: {result.error_code} - {result.message}"
    )
    output = Path(result.output_path)
    assert output.exists()
    assert expected in output.read_text(encoding="utf-8")

"""
Where a unit is, in a form the interface can translate.

A location is shown next to every detection on the review screen — "en-tête de
page 2", "diapositive 4, notes", "colonne courriel" — so it cannot be an
English sentence written by the worker, which is what it was at first. It is a
code, like every other string the adapters emit, with the one variable part
appended after a colon:

    document            no detail
    header:2            the part's number
    column:courriel     the column's name

The split is on the **first** colon only: a column can legitimately be named
"ville: livraison", and the user's own header is not something to rewrite for
the sake of a tidier grammar.

The codes themselves are the contract with the interface, and
``LOCATION_CODES`` is what ``src/features/anonymization/locationLabels.ts``
mirrors. A code added here without a French and English string there leaves a
user reading a bare identifier.
"""

import zipfile

import pytest

from document_worker.anonymization.formats import anonymization_adapter
from document_worker.anonymization.locations import LOCATION_CODES

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'

DOCUMENT = f"<w:document {W}><w:body><w:p><w:r><w:t>Jean Dupont</w:t></w:r></w:p></w:body></w:document>"
HEADER = f"<w:hdr {W}><w:p><w:r><w:t>Jean Dupont</w:t></w:r></w:p></w:hdr>"
SLIDE = f'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" {A}><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Jean Dupont</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'
SHEET = f'<worksheet {S}><sheetData><row><c t="inlineStr"><is><t>Jean Dupont</t></is></c></row></sheetData></worksheet>'


def extract(path):
    return anonymization_adapter(str(path)).extract(path)


def write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def package(tmp_path, name, parts):
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        for part, content in parts.items():
            archive.writestr(part, content)
    return path


class TestGrammar:
    """One shape, so the interface needs one parser and not a dictionary of them."""

    @staticmethod
    def code_of(location):
        return location.partition(":")[0]

    @pytest.mark.parametrize(
        ("name", "content"),
        [
            ("notes.txt", "Jean Dupont"),
            ("notes.md", "# Jean Dupont"),
            ("contacts.csv", "nom,courriel\nJean,jean@example.fr\n"),
            ("data.json", '{"nom": "Jean Dupont"}'),
            ("data.jsonl", '{"nom": "Jean"}\n{"nom": "Marie"}\n'),
            ("page.html", "<p>Jean Dupont</p>"),
            ("fiche.xml", "<nom>Jean Dupont</nom>"),
        ],
    )
    def test_every_location_starts_with_a_known_code(self, tmp_path, name, content):
        for unit in extract(write(tmp_path, name, content)).units:
            assert self.code_of(unit.location) in LOCATION_CODES, unit.location

    def test_an_office_package_follows_the_same_grammar(self, tmp_path):
        path = package(
            tmp_path,
            "doc.docx",
            {"word/document.xml": DOCUMENT, "word/header1.xml": HEADER},
        )

        for unit in extract(path).units:
            assert self.code_of(unit.location) in LOCATION_CODES, unit.location

    def test_a_column_name_containing_a_colon_is_kept_whole(self, tmp_path):
        """The header is the user's text, not ours to tidy."""
        path = write(tmp_path, "livraisons.csv", "ville: livraison\nBordeaux\n")

        assert extract(path).units[0].location == "column:ville: livraison"


class TestWhatTheDetailCarries:
    def test_a_part_number_is_the_detail(self, tmp_path):
        path = package(tmp_path, "deck.pptx", {"ppt/slides/slide7.xml": SLIDE})

        assert extract(path).units[0].location == "slide:7"

    def test_a_named_column_carries_its_name(self, tmp_path):
        path = write(tmp_path, "contacts.csv", "nom,courriel\nJean,jean@example.fr\n")

        assert extract(path).units[1].location == "column:courriel"

    def test_an_unnamed_column_carries_its_number(self, tmp_path):
        """A header cell can be empty, and a position is still something to show."""
        path = write(tmp_path, "contacts.csv", "nom,\nJean,jean@example.fr\n")

        assert extract(path).units[1].location == "column_number:2"

    def test_a_jsonl_line_carries_its_number(self, tmp_path):
        path = write(tmp_path, "data.jsonl", '{"nom": "Jean"}\n{"nom": "Marie"}\n')

        assert extract(path).units[1].location == "line:2"

    def test_a_whole_file_carries_no_detail(self, tmp_path):
        assert extract(write(tmp_path, "notes.txt", "Jean")).units[0].location == (
            "document"
        )


class TestCodeInventory:
    """
    The list is the contract, so it is checked against the adapters themselves.

    A rule whose code is not declared would reach the interface as a bare
    identifier, and a declared code no adapter emits is a string nobody reads.
    """

    def test_every_code_an_office_rule_emits_is_declared(self):
        from document_worker.anonymization.ooxml_adapters import (
            _DOCX_RULES,
            _PPTX_RULES,
            _XLSX_RULES,
        )

        for rules in (_DOCX_RULES, _PPTX_RULES, _XLSX_RULES):
            for rule in rules:
                assert rule.location.partition(":")[0] in LOCATION_CODES, rule.location

    def test_the_colon_is_reserved_for_the_detail(self):
        for code in LOCATION_CODES:
            assert ":" not in code

    def test_a_sheet_name_is_never_offered_for_rewriting(self, tmp_path):
        """
        The non-rewritable locations exist so the user can be told, not asked.

        Renaming a sheet turns every reference to it into `#REF!`, so the review
        screen shows these and never offers them.
        """
        workbook = f'<workbook {S}><sheets><sheet name="Jean Dupont" sheetId="1"/></sheets></workbook>'
        path = package(
            tmp_path,
            "comptes.xlsx",
            {"xl/workbook.xml": workbook, "xl/worksheets/sheet1.xml": SHEET},
        )

        frozen = {unit.location for unit in extract(path).units if not unit.rewritable}

        assert "sheet_names" in frozen

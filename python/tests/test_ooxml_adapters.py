"""
Tier B adapters: the Office packages.

A DOCX, XLSX or PPTX is a zip of XML parts. Only the parts holding text are
parsed; everything else — images, themes, charts, the relationship graph — is
copied byte for byte, which is what keeps the copy openable.

Fixtures here are built by hand rather than produced by a writer library. The
risk these tests exist for is our own handling of runs, namespaces and
whitespace, and a fixture written by python-pptx would hide the awkward shapes
real documents contain, starting with a name split across three runs.
"""

import zipfile

import pytest

from document_worker.anonymization.formats import anonymization_adapter
from document_worker.anonymization.model import AdapterError, Edit

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
A = 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
P = (
    'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"'
)
S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'

DOCUMENT = f"""<w:document {W}><w:body>
<w:p><w:r><w:t>Jean</w:t></w:r><w:r><w:t xml:space="preserve"> Dup</w:t></w:r>
<w:r><w:t>ont</w:t></w:r></w:p>
<w:p><w:r><w:t>Caen</w:t></w:r></w:p>
</w:body></w:document>"""

SLIDE = f"""<p:sld {P}><p:cSld><p:spTree>
<p:sp><p:nvSpPr><p:cNvPr id="2" name="Titre" descr="Photo de Jean"/></p:nvSpPr>
<p:txBody><a:p><a:r><a:t>Jean</a:t></a:r><a:r><a:t> Dupont</a:t></a:r></a:p></p:txBody>
</p:sp></p:spTree></p:cSld></p:sld>"""


def package(tmp_path, name, parts):
    path = tmp_path / name
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        for part, data in parts.items():
            archive.writestr(part, data)
    return path


def extract(path):
    return anonymization_adapter(str(path)).extract(path)


def run(path, edits, tmp_path):
    output = tmp_path / f"out{path.suffix}"
    anonymization_adapter(str(path)).apply(path, edits, output)
    return output


def unit_named(extraction, fragment):
    """The one unit whose id contains ``fragment``."""
    matches = [unit for unit in extraction.units if fragment in unit.id]
    assert len(matches) == 1, [unit.id for unit in extraction.units]
    return matches[0]


def part_of(path, name):
    with zipfile.ZipFile(path) as archive:
        return archive.read(name).decode()


class TestWordDocuments:
    def test_runs_of_a_paragraph_read_as_one_string(self, tmp_path):
        path = package(tmp_path, "doc.docx", {"word/document.xml": DOCUMENT})

        unit = unit_named(extract(path), "word/document.xml")

        assert unit.text == "Jean Dupont\nCaen"

    # The one shape that matters: Word splits a name across runs for reasons of
    # its own — a spell-check marker, an editing session — and a detector given
    # the runs separately finds nothing.
    def test_a_name_split_across_runs_is_replaced_in_the_first_run(self, tmp_path):
        path = package(tmp_path, "doc.docx", {"word/document.xml": DOCUMENT})
        unit = unit_named(extract(path), "word/document.xml")

        output = run(path, [Edit(unit.id, 0, 11, "[PERSONNE 1]")], tmp_path)

        document = part_of(output, "word/document.xml")
        assert "[PERSONNE 1]" in document
        assert "Jean" not in document
        assert "Caen" in document

    def test_paragraphs_are_not_fused_into_one_word(self, tmp_path):
        path = package(tmp_path, "doc.docx", {"word/document.xml": DOCUMENT})

        assert "DupontCaen" not in unit_named(extract(path), "word/document.xml").text

    @pytest.mark.parametrize(
        ("part", "fragment"),
        [
            ("word/header1.xml", "header"),
            ("word/footer1.xml", "footer"),
            ("word/footnotes.xml", "footnote"),
            ("word/endnotes.xml", "endnote"),
            ("word/comments.xml", "comment"),
        ],
    )
    def test_text_outside_the_body_is_its_own_unit(self, tmp_path, part, fragment):
        body = f"<w:hdr {W}><w:p><w:r><w:t>Jean Dupont</w:t></w:r></w:p></w:hdr>"
        path = package(
            tmp_path, "doc.docx", {"word/document.xml": DOCUMENT, part: body}
        )

        unit = unit_named(extract(path), part)

        assert unit.text == "Jean Dupont"
        assert fragment in unit.location.lower()

    def test_text_in_a_text_box_is_covered_by_the_body_unit(self, tmp_path):
        document = f"""<w:document {W}><w:body><w:p><w:r><w:txbxContent>
        <w:p><w:r><w:t>Jean Dupont</w:t></w:r></w:p>
        </w:txbxContent></w:r></w:p></w:body></w:document>"""
        path = package(tmp_path, "doc.docx", {"word/document.xml": document})

        assert "Jean Dupont" in unit_named(extract(path), "word/document.xml").text

    # Deleted text lives in w:delText, not w:t. It is left alone and reported:
    # a user who accepts the revisions later would otherwise find the personal
    # data back in the document.
    def test_tracked_changes_are_reported_and_left_alone(self, tmp_path):
        document = f"""<w:document {W}><w:body><w:p>
        <w:del><w:r><w:delText>Jean Dupont</w:delText></w:r></w:del>
        </w:p></w:body></w:document>"""
        path = package(tmp_path, "doc.docx", {"word/document.xml": document})

        extraction = extract(path)

        assert "tracked_changes_not_rewritten" in extraction.notes
        assert all("Jean Dupont" not in unit.text for unit in extraction.units)

    def test_document_properties_are_reported_and_left_alone(self, tmp_path):
        core = (
            '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/'
            'package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/">'
            "<dc:creator>Jean Dupont</dc:creator></cp:coreProperties>"
        )
        path = package(
            tmp_path,
            "doc.docx",
            {"word/document.xml": DOCUMENT, "docProps/core.xml": core},
        )

        assert "document_properties_not_rewritten" in extract(path).notes

    def test_a_replacement_needing_whitespace_says_so(self, tmp_path):
        document = f"<w:document {W}><w:body><w:p><w:r><w:t>Jean</w:t></w:r></w:p></w:body></w:document>"
        path = package(tmp_path, "doc.docx", {"word/document.xml": document})
        unit = unit_named(extract(path), "word/document.xml")

        output = run(path, [Edit(unit.id, 0, 4, " X ")], tmp_path)

        assert 'space="preserve"' in part_of(output, "word/document.xml")


class TestPackageIntegrity:
    IMAGE = b"\x89PNG\r\n\x1a\nnot really a png"

    def test_parts_we_do_not_touch_are_copied_byte_for_byte(self, tmp_path):
        path = package(
            tmp_path,
            "doc.docx",
            {"word/document.xml": DOCUMENT, "word/media/image1.png": self.IMAGE},
        )
        unit = unit_named(extract(path), "word/document.xml")

        output = run(path, [Edit(unit.id, 0, 11, "[P 1]")], tmp_path)

        with zipfile.ZipFile(output) as archive:
            assert archive.read("word/media/image1.png") == self.IMAGE

    def test_every_entry_of_the_original_is_present_in_the_copy(self, tmp_path):
        path = package(
            tmp_path,
            "doc.docx",
            {"word/document.xml": DOCUMENT, "word/media/image1.png": self.IMAGE},
        )

        output = run(path, [], tmp_path)

        with zipfile.ZipFile(path) as before, zipfile.ZipFile(output) as after:
            assert before.namelist() == after.namelist()

    def test_a_file_that_is_not_a_package_is_reported(self, tmp_path):
        path = tmp_path / "doc.docx"
        path.write_bytes(b"not a zip at all")

        with pytest.raises(AdapterError):
            extract(path)

    def test_a_package_without_the_expected_parts_is_reported(self, tmp_path):
        path = package(tmp_path, "doc.docx", {})

        with pytest.raises(AdapterError):
            extract(path)


class TestPresentations:
    def test_slide_runs_read_as_one_string(self, tmp_path):
        path = package(tmp_path, "deck.pptx", {"ppt/slides/slide1.xml": SLIDE})

        unit = unit_named(extract(path), "ppt/slides/slide1.xml")

        assert "Jean Dupont" in unit.text

    # Alt text is read aloud by assistive technology and routinely describes
    # who is in a photograph, so it is part of the document's personal data.
    def test_shape_alt_text_is_analyzed_and_rewritten(self, tmp_path):
        path = package(tmp_path, "deck.pptx", {"ppt/slides/slide1.xml": SLIDE})
        unit = unit_named(extract(path), "ppt/slides/slide1.xml")
        start = unit.text.index("Photo de Jean")

        output = run(path, [Edit(unit.id, start, start + 13, "[PHOTO]")], tmp_path)

        assert 'descr="[PHOTO]"' in part_of(output, "ppt/slides/slide1.xml")

    @pytest.mark.parametrize(
        ("part", "fragment"),
        [
            ("ppt/notesSlides/notesSlide1.xml", "notes"),
            ("ppt/slideLayouts/slideLayout1.xml", "layout"),
            ("ppt/slideMasters/slideMaster1.xml", "master"),
            ("ppt/comments/modernComment_1.xml", "comment"),
        ],
    )
    def test_speaker_notes_layouts_masters_and_comments_are_covered(
        self, tmp_path, part, fragment
    ):
        content = f"<root {A}><a:p><a:r><a:t>Jean Dupont</a:t></a:r></a:p></root>"
        path = package(
            tmp_path, "deck.pptx", {"ppt/slides/slide1.xml": SLIDE, part: content}
        )

        unit = unit_named(extract(path), part)

        assert unit.text == "Jean Dupont"
        assert fragment in unit.location.lower()

    def test_the_location_names_the_slide_number(self, tmp_path):
        path = package(tmp_path, "deck.pptx", {"ppt/slides/slide7.xml": SLIDE})

        assert "7" in unit_named(extract(path), "slide7").location


class TestSpreadsheets:
    SHARED = (
        f"<sst {S}><si><t>Jean Dupont</t></si><si><t>jean@example.fr</t></si></sst>"
    )
    SHEET = f"""<worksheet {S}><sheetData>
    <row r="1"><c r="A1" t="inlineStr"><is><t>Marie Martin</t></is></c>
    <c r="B1"><f>CONCATENATE("Jean"," Dupont")</f></c></row>
    </sheetData><headerFooter><oddHeader>&amp;LRapport de Jean</oddHeader></headerFooter>
    </worksheet>"""
    WORKBOOK = f'<workbook {S}><sheets><sheet name="Clients Dupont" sheetId="1"/></sheets></workbook>'

    def book(self, tmp_path):
        return package(
            tmp_path,
            "book.xlsx",
            {
                "xl/sharedStrings.xml": self.SHARED,
                "xl/worksheets/sheet1.xml": self.SHEET,
                "xl/workbook.xml": self.WORKBOOK,
            },
        )

    def test_shared_strings_are_one_unit(self, tmp_path):
        unit = unit_named(extract(self.book(tmp_path)), "sharedStrings")

        assert unit.text == "Jean Dupont\njean@example.fr"

    def test_a_shared_string_edit_rewrites_the_single_stored_copy(self, tmp_path):
        path = self.book(tmp_path)
        unit = unit_named(extract(path), "sharedStrings")

        output = run(path, [Edit(unit.id, 0, 11, "[PERSONNE 1]")], tmp_path)

        assert "[PERSONNE 1]" in part_of(output, "xl/sharedStrings.xml")

    # One shared string can be referenced by any number of cells, so a single
    # replacement changes all of them. The user is told rather than surprised.
    def test_the_shared_string_fan_out_is_reported(self, tmp_path):
        assert "xlsx_shared_strings_reused" in extract(self.book(tmp_path)).notes

    def test_inline_strings_and_header_text_are_covered(self, tmp_path):
        unit = unit_named(extract(self.book(tmp_path)), "worksheets/sheet1.xml|text")

        assert "Marie Martin" in unit.text
        assert "Rapport de Jean" in unit.text

    # A formula is code. Its string literals are shown to the user so nothing
    # is hidden, but rewriting one by offset is how a workbook stops opening.
    def test_formulas_are_analyzed_but_never_rewritten(self, tmp_path):
        path = self.book(tmp_path)
        unit = unit_named(extract(path), "sheet1.xml|formula")

        assert "Jean" in unit.text
        assert unit.rewritable is False
        with pytest.raises(ValueError):
            run(path, [Edit(unit.id, 0, 4, "X")], tmp_path)

    # Renaming a sheet silently breaks every formula and defined name that
    # refers to it, so the name is reported and left as it is.
    def test_sheet_names_are_reported_but_not_rewritten(self, tmp_path):
        unit = unit_named(extract(self.book(tmp_path)), "workbook.xml")

        assert "Clients Dupont" in unit.text
        assert unit.rewritable is False

"""
The pipeline between the protocol and the adapters.

Two calls, because the user decides in the middle: ``analyze_file`` reads a
document and reports what it found, ``anonymize_file`` takes back the subset the
user kept and writes a copy. The worker holds nothing between them, so every
test here starts from a path on disk.

Failures are ``AdapterError``, which already carries the code the protocol
reports. The codes are the contract with the UI and are asserted by name.
"""

import json
import zipfile

import pytest

from document_worker.anonymization import pipeline
from document_worker.anonymization.model import AdapterError
from document_worker.protocol import KeptDetection

SENTENCE = "Le dossier de Marie Lefebvre a été transmis à la mairie de Bordeaux.\n"

# An element with an attribute: the XML adapter reports attributes as text it
# does not analyze, which is the note these tests need to be deterministic.
FICHE = '<fiche ref="A1"><nom>Marie Lefebvre</nom></fiche>'

_S = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
WORKBOOK = (
    f'<workbook {_S}><sheets><sheet name="Clients" sheetId="1"/></sheets></workbook>'
)
SHEET = (
    f"<worksheet {_S}><sheetData><row>"
    '<c><f>CONCATENATE("Dossier de Marie Lefebvre")</f></c>'
    "</row></sheetData></worksheet>"
)


def source(tmp_path, name="dossier.txt", text=SENTENCE):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def workbook(tmp_path):
    """A spreadsheet whose only name sits inside a formula literal."""
    path = tmp_path / "comptes.xlsx"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("xl/workbook.xml", WORKBOOK)
        archive.writestr("xl/worksheets/sheet1.xml", SHEET)
    return path


def kept(analysis):
    return [
        KeptDetection(d.unit_id, d.start, d.end, d.entity_type)
        for d in analysis.detections
    ]


class TestAnalyze:
    def test_a_document_is_read_and_reported(self, tmp_path):
        analysis = pipeline.analyze_file(source(tmp_path))

        assert [unit.location for unit in analysis.units] == ["document"]
        assert "Marie Lefebvre" in [d.text for d in analysis.detections]

    def test_offsets_belong_to_the_unit_they_name(self, tmp_path):
        analysis = pipeline.analyze_file(source(tmp_path))
        texts = {unit.id: unit.text for unit in analysis.units}

        for found in analysis.detections:
            assert texts[found.unit_id][found.start : found.end] == found.text

    def test_notes_travel_with_the_analysis(self, tmp_path):
        """What the format does not analyze has to reach the user."""
        path = source(tmp_path, "fiche.xml", FICHE)

        assert "xml_attributes_not_analyzed" in pipeline.analyze_file(path).notes

    def test_nothing_is_written(self, tmp_path):
        path = source(tmp_path)

        pipeline.analyze_file(path)

        assert [item.name for item in tmp_path.iterdir()] == [path.name]

    @pytest.mark.parametrize(
        "name,code",
        [("missing.txt", "input_not_found"), ("report.pdf", "unsupported_format")],
    )
    def test_what_cannot_be_analyzed(self, tmp_path, name, code):
        if name != "missing.txt":
            source(tmp_path, name, "irrelevant")

        with pytest.raises(AdapterError) as failure:
            pipeline.analyze_file(tmp_path / name)

        assert failure.value.code == code


class TestAnonymize:
    def test_a_copy_is_written_beside_the_original(self, tmp_path):
        path = source(tmp_path)
        analysis = pipeline.analyze_file(path)

        written = pipeline.anonymize_file(path, tmp_path, kept(analysis))

        assert written.output_path.name == "dossier-anonymise.txt"
        assert "Marie Lefebvre" not in written.output_path.read_text(encoding="utf-8")
        assert path.read_text(encoding="utf-8") == SENTENCE

    def test_the_suffix_follows_the_language(self, tmp_path):
        path = source(tmp_path)
        analysis = pipeline.analyze_file(path)

        written = pipeline.anonymize_file(path, tmp_path, kept(analysis), language="en")

        assert written.output_path.name == "dossier-anonymized.txt"

    def test_an_existing_copy_is_never_overwritten(self, tmp_path):
        path = source(tmp_path)
        occupied = tmp_path / "dossier-anonymise.txt"
        occupied.write_text("earlier run", encoding="utf-8")
        analysis = pipeline.analyze_file(path)

        written = pipeline.anonymize_file(path, tmp_path, kept(analysis))

        assert written.output_path.name == "dossier-anonymise-2.txt"
        assert occupied.read_text(encoding="utf-8") == "earlier run"

    def test_the_mask_operator_hides_the_value(self, tmp_path):
        path = source(tmp_path)
        analysis = pipeline.analyze_file(path)

        written = pipeline.anonymize_file(
            path, tmp_path, kept(analysis), operator="mask"
        )

        copy = written.output_path.read_text(encoding="utf-8")
        assert "Marie Lefebvre" not in copy
        assert "•" in copy

    def test_only_what_the_user_kept_is_replaced(self, tmp_path):
        """Dropping a detection in the review screen has to mean something."""
        path = source(tmp_path)
        analysis = pipeline.analyze_file(path)
        one = [
            KeptDetection(d.unit_id, d.start, d.end, d.entity_type)
            for d in analysis.detections
            if d.text == "Marie Lefebvre"
        ]

        written = pipeline.anonymize_file(path, tmp_path, one)

        copy = written.output_path.read_text(encoding="utf-8")
        assert "Marie Lefebvre" not in copy
        assert "Bordeaux" in copy

    def test_keeping_nothing_writes_an_unchanged_copy(self, tmp_path):
        path = source(tmp_path)

        written = pipeline.anonymize_file(path, tmp_path, [])

        assert written.output_path.read_text(encoding="utf-8") == SENTENCE

    def test_structure_survives_the_rewrite(self, tmp_path):
        path = source(tmp_path, "people.json", '{"name": "Marie Lefebvre"}')
        analysis = pipeline.analyze_file(path)

        written = pipeline.anonymize_file(path, tmp_path, kept(analysis))

        assert json.loads(written.output_path.read_text(encoding="utf-8")) == {
            "name": "[PERSONNE 1]"
        }

    def test_notes_travel_with_the_copy(self, tmp_path):
        """A user must not believe a copy is clean when it is only partly clean."""
        path = source(tmp_path, "fiche.xml", FICHE)
        analysis = pipeline.analyze_file(path)

        written = pipeline.anonymize_file(path, tmp_path, kept(analysis))

        assert "xml_attributes_not_analyzed" in written.notes


class TestWhatIsRefused:
    def test_an_output_folder_that_is_not_there(self, tmp_path):
        path = source(tmp_path)

        with pytest.raises(AdapterError) as failure:
            pipeline.anonymize_file(path, tmp_path / "gone", [])

        assert failure.value.code == "invalid_output_directory"

    @pytest.mark.parametrize(
        "field,value",
        [("unit_id", "no-such-unit"), ("start", 9999), ("end", 99999)],
    )
    def test_detections_that_do_not_fit_the_document(self, tmp_path, field, value):
        """
        The document may have been edited while the user was reviewing it.

        Offsets computed against other content would corrupt the copy, so
        nothing is written and the user is told to analyze again.
        """
        path = source(tmp_path)
        analysis = pipeline.analyze_file(path)
        first = analysis.detections[0]
        item = KeptDetection(first.unit_id, first.start, first.end, first.entity_type)
        broken = KeptDetection(
            **{
                "unit_id": item.unit_id,
                "start": item.start,
                "end": item.end,
                "entity_type": item.entity_type,
                field: value,
            }
        )

        with pytest.raises(AdapterError) as failure:
            pipeline.anonymize_file(path, tmp_path, [broken])

        assert failure.value.code == "document_changed"
        assert list(tmp_path.iterdir()) == [path]

    def test_text_the_format_cannot_rewrite(self, tmp_path):
        """
        A formula literal is reported and never written back.

        The review screen does not offer it, so a request that keeps one is a
        bug on the other side of the protocol rather than a user's choice — and
        rewriting a formula by offset is how a workbook stops opening.
        """
        path = workbook(tmp_path)
        analysis = pipeline.analyze_file(path)
        frozen = {unit.id for unit in analysis.units if not unit.rewritable}
        inside = [d for d in analysis.detections if d.unit_id in frozen]
        assert inside, [unit.id for unit in analysis.units]

        with pytest.raises(AdapterError) as failure:
            pipeline.anonymize_file(
                path,
                tmp_path,
                [
                    KeptDetection(d.unit_id, d.start, d.end, d.entity_type)
                    for d in inside[:1]
                ],
            )

        assert failure.value.code == "not_rewritable"

    def test_an_unknown_operator(self, tmp_path):
        with pytest.raises(AdapterError) as failure:
            pipeline.anonymize_file(source(tmp_path), tmp_path, [], operator="encrypt")

        assert failure.value.code == "invalid_request"

    def test_the_source_is_never_the_destination(self, tmp_path):
        """No in-place mode, not even by collision."""
        path = source(tmp_path, "dossier-anonymise.txt")

        written = pipeline.anonymize_file(path, tmp_path, [])

        assert written.output_path != path
        assert path.read_text(encoding="utf-8") == SENTENCE

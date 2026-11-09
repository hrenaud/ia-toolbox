"""
Tier A adapters: formats whose text is the file itself.

The contract every adapter shares is two calls: ``extract`` gives the strings
to analyze, ``apply`` writes a copy with the edits in place. Nothing here needs
a model, so these tests run everywhere.

The recurring risk is the round trip. An anonymizer that silently re-encodes a
file, flips its line endings, or reorders its JSON keys has damaged a document
the user still has to work with. So the first test for each format is that a
copy with no edits comes back unchanged.
"""

import json

import pytest

from document_worker.anonymization.formats import anonymization_adapter
from document_worker.anonymization.model import Edit


def write(tmp_path, name, content, encoding="utf-8"):
    path = tmp_path / name
    path.write_bytes(content.encode(encoding) if isinstance(content, str) else content)
    return path


def run(path, edits, tmp_path):
    """Apply ``edits`` to ``path`` and return the resulting bytes."""
    adapter = anonymization_adapter(str(path))
    output = tmp_path / f"out{path.suffix}"
    adapter.apply(path, edits, output)
    return output.read_bytes()


def extract(path):
    return anonymization_adapter(str(path)).extract(path)


def unit_texts(extraction):
    return [unit.text for unit in extraction.units]


class TestPlainText:
    def test_the_whole_file_is_one_unit(self, tmp_path):
        path = write(tmp_path, "note.txt", "Jean Dupont habite à Caen.")

        extraction = extract(path)

        assert unit_texts(extraction) == ["Jean Dupont habite à Caen."]

    def test_a_copy_with_no_edits_is_byte_identical(self, tmp_path):
        content = "Jean\r\nMarie\r\n"
        path = write(tmp_path, "note.txt", content)

        assert run(path, [], tmp_path) == content.encode("utf-8")

    # Line endings are part of the document. Reading with translation on and
    # writing back would turn every CRLF into LF, which shows up as a diff on
    # every line of a file the user never meant to reformat.
    def test_windows_line_endings_survive_an_edit(self, tmp_path):
        path = write(tmp_path, "note.txt", "Jean\r\nMarie\r\n")
        [unit] = extract(path).units

        result = run(path, [Edit(unit.id, 0, 4, "[PERSONNE 1]")], tmp_path)

        assert result == b"[PERSONNE 1]\r\nMarie\r\n"

    @pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "cp1252"])
    def test_the_original_encoding_is_detected_and_reused(self, tmp_path, encoding):
        path = write(tmp_path, "note.txt", "Chère Amélie", encoding=encoding)
        [unit] = extract(path).units

        assert unit.text.endswith("Chère Amélie")
        assert run(path, [], tmp_path) == path.read_bytes()

    def test_an_undecodable_file_is_reported_rather_than_mangled(self, tmp_path):
        from document_worker.anonymization.model import AdapterError

        path = write(tmp_path, "note.txt", b"\xff\xfe\x00\x00rubbish\x00")

        with pytest.raises(AdapterError):
            extract(path)


class TestMarkdown:
    """Markdown syntax is structure, so the detector never sees it.

    Handing ``**Lieu :** Nantes, salle Loire`` to a model as-is was the earlier
    behaviour, and it cost twice: an email inside a fenced code block was
    offered for replacement although the documentation says code is not
    analyzed, and the syntax characters wrecked the sentences around them —
    ``salle`` came back as a person, ``Annexe`` as a location, and a table cell
    came back with its closing pipe inside the span.
    """

    def test_a_copy_with_no_edits_is_byte_identical(self, tmp_path):
        content = "# Titre\n\n| Nom   | Date |\n| ----- | ---- |\n| Jean  | 2026 |\n"
        path = write(tmp_path, "note.md", content)

        assert run(path, [], tmp_path) == content.encode("utf-8")

    def test_heading_and_emphasis_markers_are_not_analyzed(self, tmp_path):
        path = write(tmp_path, "note.md", "## Annexe\n\n**Lieu :** Nantes\n")

        [unit] = extract(path).units

        assert "#" not in unit.text
        assert "*" not in unit.text
        assert "Annexe" in unit.text
        assert "Lieu :" in unit.text
        assert "Nantes" in unit.text

    # Code and comments carry personal data like any other text — an address in
    # a snippet and a name in a review note are exactly the leaks a user is
    # anonymizing the document to remove. So the rule is the same everywhere:
    # the delimiters are structure and the content is text.
    def test_a_fenced_code_block_is_analyzed_without_its_fence(self, tmp_path):
        path = write(
            tmp_path,
            "note.md",
            'Script :\n\n```python\nOWNER = "admin@novagaia.fr"\n```\n\nFin.\n',
        )

        extraction = extract(path)
        [unit] = extraction.units

        assert "admin@novagaia.fr" in unit.text
        assert "```" not in unit.text
        assert "python" not in unit.text
        assert "markup_code_not_analyzed" not in extraction.notes

    def test_a_replacement_inside_a_fence_keeps_the_fence(self, tmp_path):
        content = 'Script :\n\n```python\nOWNER = "admin@novagaia.fr"\n```\n'
        path = write(tmp_path, "note.md", content)
        [unit] = extract(path).units
        start = unit.text.index("admin@novagaia.fr")

        result = run(
            path,
            [Edit(unit.id, start, start + len("admin@novagaia.fr"), "[COURRIEL 1]")],
            tmp_path,
        ).decode()

        assert '```python\nOWNER = "[COURRIEL 1]"\n```' in result

    def test_an_inline_code_span_is_analyzed_without_its_backticks(self, tmp_path):
        path = write(tmp_path, "note.md", "Écrire à `admin@novagaia.fr` demain.\n")

        [unit] = extract(path).units

        assert "admin@novagaia.fr" in unit.text
        assert "`" not in unit.text
        assert "demain" in unit.text

    def test_an_html_comment_is_analyzed_without_its_delimiters(self, tmp_path):
        path = write(tmp_path, "note.md", "Fin.\n\n<!-- relire avec Marie Vidal -->\n")

        extraction = extract(path)
        [unit] = extraction.units

        assert "Marie Vidal" in unit.text
        assert "<!--" not in unit.text
        assert "-->" not in unit.text

    def test_an_html_tag_is_still_structure(self, tmp_path):
        """A tag is markup, not prose: only comments and code change here."""
        path = write(tmp_path, "note.md", '<div class="Marie Vidal">Fin.</div>\n')

        [unit] = extract(path).units

        assert "Marie Vidal" not in unit.text
        assert "Fin." in unit.text

    # A table cell is a value, and the pipe beside it is not part of it. Feeding
    # the row as one string put the pipe inside the span, so replacing the name
    # deleted the cell boundary and broke the table.
    def test_table_cells_are_analyzed_without_their_pipes(self, tmp_path):
        path = write(
            tmp_path,
            "note.md",
            "| Porteur       | Échéance |\n| ------------- | -------- |\n"
            "| Claire Dubois | 2026     |\n",
        )

        [unit] = extract(path).units

        assert "|" not in unit.text
        assert "-------" not in unit.text
        assert "Claire Dubois" in unit.text

    def test_an_edit_lands_in_the_file_past_an_excluded_block(self, tmp_path):
        path = write(
            tmp_path,
            "note.md",
            "```\nadmin@novagaia.fr\n```\n\nContact : Jean Dupont\n",
        )
        [unit] = extract(path).units
        start = unit.text.index("Jean Dupont")

        result = run(
            path,
            [Edit(unit.id, start, start + len("Jean Dupont"), "[PERSONNE 1]")],
            tmp_path,
        )

        assert result.decode("utf-8") == (
            "```\nadmin@novagaia.fr\n```\n\nContact : [PERSONNE 1]\n"
        )

    def test_windows_line_endings_survive_an_edit(self, tmp_path):
        path = write(tmp_path, "note.md", "# Titre\r\n\r\nJean\r\n")
        [unit] = extract(path).units
        start = unit.text.index("Jean")

        result = run(path, [Edit(unit.id, start, start + 4, "[PERSONNE 1]")], tmp_path)

        assert result == b"# Titre\r\n\r\n[PERSONNE 1]\r\n"


class TestDelimitedText:
    SAMPLE = 'nom,courriel,montant\n"Dupont, Jean",jean@example.fr,42\nMarie,marie@example.fr,7\n'

    # One unit per column, not per cell: a column holds one kind of value, and
    # its header is the context that lifts recall far above what the values
    # alone give. Per-cell units would mean one model call per cell.
    def test_each_column_is_one_unit_carrying_its_header_as_context(self, tmp_path):
        path = write(tmp_path, "contacts.csv", self.SAMPLE)

        extraction = extract(path)

        assert len(extraction.units) == 3
        assert extraction.units[1].context == ("courriel",)
        assert "jean@example.fr" in extraction.units[1].text

    # Cells are joined by a newline that belongs to no cell, so the last word
    # of one row cannot fuse with the first of the next.
    def test_cells_of_a_column_are_joined_without_merging_values(self, tmp_path):
        path = write(tmp_path, "contacts.csv", self.SAMPLE)

        assert extract(path).units[0].text == "Dupont, Jean\nMarie"

    def test_the_header_row_is_not_part_of_the_analyzed_text(self, tmp_path):
        path = write(tmp_path, "contacts.csv", self.SAMPLE)

        assert "courriel" not in extract(path).units[1].text

    def test_the_location_names_the_column(self, tmp_path):
        path = write(tmp_path, "contacts.csv", self.SAMPLE)

        assert "courriel" in extract(path).units[1].location

    def test_a_tab_separated_file_keeps_its_delimiter(self, tmp_path):
        path = write(tmp_path, "contacts.tsv", "nom\tcourriel\nJean\tjean@example.fr\n")

        result = run(path, [], tmp_path)

        assert result == b"nom\tcourriel\nJean\tjean@example.fr\n"

    def test_an_edit_lands_in_the_right_cell(self, tmp_path):
        path = write(tmp_path, "contacts.csv", self.SAMPLE)
        unit = extract(path).units[1]

        result = run(path, [Edit(unit.id, 0, 15, "[COURRIEL 1]")], tmp_path).decode()

        assert "[COURRIEL 1]" in result
        assert "marie@example.fr" in result
        assert "jean@example.fr" not in result

    # A value that needed quoting still needs it after the edit, or the row
    # gains a column and the file stops parsing.
    def test_a_replacement_containing_the_delimiter_is_quoted(self, tmp_path):
        path = write(tmp_path, "contacts.csv", "nom\nJean\n")
        [unit] = extract(path).units

        result = run(path, [Edit(unit.id, 0, 4, "Dupont, Jean")], tmp_path).decode()

        assert '"Dupont, Jean"' in result

    def test_a_file_with_no_rows_beyond_the_header_yields_no_text(self, tmp_path):
        path = write(tmp_path, "contacts.csv", "nom,courriel\n")

        assert unit_texts(extract(path)) == ["", ""]

    # Where each cell starts and ends, so a column can be typed and replaced as
    # a whole rather than cell by cell. Only a tabular adapter reports this.
    def test_a_column_reports_the_span_of_each_of_its_cells(self, tmp_path):
        path = write(tmp_path, "contacts.csv", self.SAMPLE)

        [unit] = extract(path).units[:1]

        assert [unit.text[start:end] for start, end in unit.cells] == [
            "Dupont, Jean",
            "Marie",
        ]

    def test_a_cell_holding_a_newline_is_still_one_cell(self, tmp_path):
        """Splitting the column's text on newlines would cut this one in two."""
        path = write(tmp_path, "contacts.csv", 'nom\n"Jean\nDupont"\nMarie\n')

        [unit] = extract(path).units

        assert [unit.text[start:end] for start, end in unit.cells] == [
            "Jean\nDupont",
            "Marie",
        ]

    def test_a_missing_cell_is_reported_as_an_empty_span(self, tmp_path):
        path = write(tmp_path, "contacts.csv", "nom,courriel\nJean\n")

        assert extract(path).units[1].cells == ((0, 0),)


class TestJson:
    SAMPLE = '{"nom": "Jean Dupont", "age": 42, "contacts": ["jean@example.fr"]}'

    # Only string values are analyzed. Keys are schema, not content: rewriting
    # one would break whatever reads the file.
    def test_only_string_values_are_analyzed(self, tmp_path):
        path = write(tmp_path, "data.json", self.SAMPLE)

        [unit] = extract(path).units

        assert "Jean Dupont" in unit.text
        assert "jean@example.fr" in unit.text
        assert "42" not in unit.text

    def test_the_keys_are_offered_as_context(self, tmp_path):
        path = write(tmp_path, "data.json", self.SAMPLE)

        [unit] = extract(path).units

        assert "nom" in unit.context

    def test_an_edit_rewrites_the_value_and_leaves_the_key(self, tmp_path):
        path = write(tmp_path, "data.json", self.SAMPLE)
        [unit] = extract(path).units
        start = unit.text.index("Jean Dupont")

        result = json.loads(
            run(path, [Edit(unit.id, start, start + 11, "[PERSONNE 1]")], tmp_path)
        )

        assert result == {
            "nom": "[PERSONNE 1]",
            "age": 42,
            "contacts": ["jean@example.fr"],
        }

    def test_key_order_and_types_survive_the_round_trip(self, tmp_path):
        path = write(tmp_path, "data.json", self.SAMPLE)

        result = json.loads(run(path, [], tmp_path))

        assert list(result) == ["nom", "age", "contacts"]
        assert result["age"] == 42

    # Each line of a JSON Lines file is its own document, so a bad line is
    # reported without losing the rest.
    def test_each_jsonl_line_is_its_own_unit(self, tmp_path):
        path = write(tmp_path, "data.jsonl", '{"nom": "Jean"}\n{"nom": "Marie"}\n')

        extraction = extract(path)

        assert len(extraction.units) == 2
        assert extraction.units[1].location == "line:2"

    def test_a_jsonl_round_trip_keeps_one_document_per_line(self, tmp_path):
        content = '{"nom": "Jean"}\n{"nom": "Marie"}\n'
        path = write(tmp_path, "data.jsonl", content)

        assert run(path, [], tmp_path).decode().splitlines() == content.splitlines()

    def test_malformed_json_is_reported_rather_than_guessed(self, tmp_path):
        from document_worker.anonymization.model import AdapterError

        path = write(tmp_path, "data.json", '{"nom": "Jean"')

        with pytest.raises(AdapterError):
            extract(path)


class TestMarkupText:
    SAMPLE = (
        "<html><head><style>p{color:red}</style></head>"
        "<body><!-- note --><p>Cher <b>Jean</b> Dupont</p>"
        '<img src="p.png" alt="Photo de Jean"><script>var a=1</script></body></html>'
    )

    # Text split by inline markup is one string to the detector: "Jean" sits in
    # a <b> and "Dupont" outside it, and a detector given them separately finds
    # neither.
    def test_text_split_by_inline_markup_reads_as_one_string(self, tmp_path):
        path = write(tmp_path, "page.html", self.SAMPLE)

        [unit] = extract(path).units

        assert "Cher Jean Dupont" in unit.text

    def test_visible_attributes_are_analyzed(self, tmp_path):
        path = write(tmp_path, "page.html", self.SAMPLE)

        assert "Photo de Jean" in extract(path).units[0].text

    # Scripts and styles are not analyzed. Rewriting code by offset is how a
    # working page becomes a broken one, so they are reported instead.
    def test_script_and_style_are_excluded_and_reported(self, tmp_path):
        path = write(tmp_path, "page.html", self.SAMPLE)

        extraction = extract(path)

        assert "var a=1" not in extraction.units[0].text
        assert "color:red" not in extraction.units[0].text
        assert "markup_code_not_analyzed" in extraction.notes

    # A comment is prose, not code: a review note naming someone is exactly
    # what anonymizing a document is meant to remove, and Markdown already
    # treats one that way.
    def test_a_comment_is_analyzed_and_rewritable(self, tmp_path):
        path = write(
            tmp_path, "page.html", "<p>Fin</p><!-- relire avec Marie Vidal -->"
        )
        [unit] = extract(path).units
        start = unit.text.index("Marie Vidal")

        result = run(
            path,
            [Edit(unit.id, start, start + len("Marie Vidal"), "[PERSONNE 1]")],
            tmp_path,
        )

        assert b"<!-- relire avec [PERSONNE 1] -->" in result

    def test_an_edit_across_inline_markup_keeps_the_markup(self, tmp_path):
        path = write(tmp_path, "page.html", "<p>Cher <b>Jean</b> Dupont, bonjour</p>")
        [unit] = extract(path).units
        start = unit.text.index("Jean")

        result = run(path, [Edit(unit.id, start, start + 11, "[PERSONNE 1]")], tmp_path)

        assert b"<b>" in result
        assert b"Jean" not in result
        assert b"bonjour" in result

    def test_xml_text_nodes_are_analyzed_and_tags_are_preserved(self, tmp_path):
        path = write(tmp_path, "data.xml", "<r><nom>Jean</nom><age>42</age></r>")
        [unit] = extract(path).units
        start = unit.text.index("Jean")

        result = run(
            path, [Edit(unit.id, start, start + 4, "[P 1]")], tmp_path
        ).decode()

        assert "<nom>[P 1]</nom>" in result
        assert "<age>42</age>" in result

    # A replacement that starts or ends with a space is dropped by XML
    # whitespace handling unless the node says otherwise.
    def test_leading_whitespace_in_a_replacement_is_protected(self, tmp_path):
        path = write(tmp_path, "data.xml", "<r><nom>Jean</nom></r>")
        [unit] = extract(path).units

        result = run(path, [Edit(unit.id, 0, 4, " X ")], tmp_path).decode()

        assert 'xml:space="preserve"' in result

    def test_malformed_xml_is_reported(self, tmp_path):
        from document_worker.anonymization.model import AdapterError

        path = write(tmp_path, "data.xml", "<r><nom>Jean</r>")

        with pytest.raises(AdapterError):
            extract(path)


class TestSharedBehaviour:
    @pytest.mark.parametrize(
        ("name", "content"),
        [
            ("note.txt", "Jean"),
            ("contacts.csv", "nom\nJean\n"),
            ("data.json", '{"nom": "Jean"}'),
            ("data.xml", "<r>Jean</r>"),
        ],
    )
    def test_every_unit_has_an_id_and_a_location(self, tmp_path, name, content):
        path = write(tmp_path, name, content)

        for unit in extract(path).units:
            assert unit.id
            assert unit.location

    @pytest.mark.parametrize(
        ("name", "content"),
        [
            ("note.txt", "Jean"),
            ("contacts.csv", "nom\nJean\n"),
            ("data.json", '{"nom": "Jean"}'),
            ("data.xml", "<r>Jean</r>"),
        ],
    )
    def test_an_edit_for_an_unknown_unit_is_refused(self, tmp_path, name, content):
        path = write(tmp_path, name, content)

        with pytest.raises(ValueError):
            run(path, [Edit("no-such-unit", 0, 4, "X")], tmp_path)

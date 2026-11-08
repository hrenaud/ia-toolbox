"""
Typing a column as a whole, rather than cell by cell.

A column of a table is not prose: every cell in it holds the same kind of
value, which is a far stronger claim than anything a detector can make about a
single cell. So a column whose cells are mostly personal data is replaced
entirely — including the cells the model missed, which is where the leaks were.

Two measurements decide it and it takes both, so there is a test for each one
failing on its own: a column of comments that each mention somebody must stay
as it is, and so must a column of reference codes with one name among them. The
case that must be accepted is the column the model only half read — those
missed cells are the leak the whole module is here to close.
"""

from document_worker.anonymization import columns
from document_worker.anonymization.model import Detection, TextUnit


def column(*cells: str) -> TextUnit:
    """A column unit shaped exactly as the delimited adapter builds one."""
    text = "\n".join(cells)
    spans = []
    offset = 0
    for cell in cells:
        spans.append((offset, offset + len(cell)))
        offset += len(cell) + 1
    return TextUnit("column-0", text, "column:Nom", ("Nom",), cells=tuple(spans))


def found(unit: TextUnit, value: str, entity_type: str = "PERSON") -> Detection:
    """A detection over the first occurrence of ``value`` in ``unit``."""
    start = unit.text.index(value)
    return Detection(unit.id, start, start + len(value), entity_type, 0.85, value)


def spans(detections: list[Detection], unit: TextUnit) -> list[str]:
    return [unit.text[item.start : item.end] for item in detections]


class TestAColumnIsTypedAsAWhole:
    def test_every_cell_is_replaced_including_the_ones_the_model_missed(self):
        """The leak this closes: a name in one cell and not in the next."""
        unit = column("Claire Dubois", "Sophie Marchand", "Le Guen")
        detections = [found(unit, "Claire Dubois"), found(unit, "Sophie Marchand")]

        typed = columns.type_columns([unit], detections)

        assert spans(typed, unit) == ["Claire Dubois", "Sophie Marchand", "Le Guen"]

    def test_the_type_covering_the_most_characters_wins(self):
        """One cell read as a place does not make a column of places."""
        unit = column("Claire Dubois", "Sophie Marchand", "Nantes")
        detections = [
            found(unit, "Claire Dubois"),
            found(unit, "Sophie Marchand"),
            found(unit, "Nantes", "LOCATION"),
        ]

        typed = columns.type_columns([unit], detections)

        assert {item.entity_type for item in typed} == {"PERSON"}

    def test_a_column_of_sentences_keeps_its_own_detections(self):
        """A name inside a comment is a name, not a column of names."""
        unit = column(
            "Relire avec Sophie Marchand avant diffusion",
            "Adhésion à confirmer en fin de mois",
            "Dossier complet, rien à signaler ici",
        )
        detections = [found(unit, "Sophie Marchand")]

        typed = columns.type_columns([unit], detections)

        assert typed == detections

    def test_a_column_holding_one_name_among_codes_is_left_alone(self):
        """
        Each cell that was found is filled by what was found in it, so fill
        alone would retype this whole column of reference codes.
        """
        unit = column("ADH-001", "ADH-002", "Claire Dubois", "ADH-004", "ADH-005")
        detections = [found(unit, "Claire Dubois")]

        assert columns.type_columns([unit], detections) == detections

    def test_a_column_the_model_half_missed_is_still_typed(self):
        """
        What fill must not measure is recall. Six names found out of eight is
        the case this whole module exists for: the two it missed are the leak.
        """
        names = [
            "Claire Dubois",
            "Marc Lefèvre",
            "Sophie Marchand",
            "Thomas Nguyen",
            "Amina Benali",
            "Pierre Rousseau",
            "Le Guen",
            "Yann Le Bris",
        ]
        unit = column(*names)
        detections = [found(unit, name) for name in names[:6]]

        typed = columns.type_columns([unit], detections)

        assert spans(typed, unit) == names

    def test_a_column_with_no_detection_is_left_alone(self):
        unit = column("ADH-001", "ADH-002", "ADH-003")

        assert columns.type_columns([unit], []) == []

    def test_an_empty_cell_is_not_replaced(self):
        """There is nothing to hide in an empty cell, and an empty edit fails."""
        unit = column("Claire Dubois", "", "Sophie Marchand")
        detections = [found(unit, "Claire Dubois"), found(unit, "Sophie Marchand")]

        typed = columns.type_columns([unit], detections)

        assert spans(typed, unit) == ["Claire Dubois", "Sophie Marchand"]

    def test_the_spaces_around_a_cell_stay_out_of_the_replacement(self):
        unit = column("Claire Dubois", "  Sophie Marchand  ")
        detections = [found(unit, "Claire Dubois"), found(unit, "Sophie Marchand")]

        typed = columns.type_columns([unit], detections)

        assert spans(typed, unit) == ["Claire Dubois", "Sophie Marchand"]

    def test_a_cell_is_replaced_once_even_with_two_detections_in_it(self):
        """Two edits over one cell would overlap and stop the write."""
        unit = column("Claire Dubois, Nantes", "Sophie Marchand, Rennes")
        detections = [
            found(unit, "Claire Dubois"),
            found(unit, "Nantes", "LOCATION"),
            found(unit, "Sophie Marchand"),
            found(unit, "Rennes", "LOCATION"),
        ]

        typed = columns.type_columns([unit], detections)

        assert spans(typed, unit) == [
            "Claire Dubois, Nantes",
            "Sophie Marchand, Rennes",
        ]

    def test_a_detection_across_two_cells_goes_away_with_them(self):
        """Both cells are replaced whole, so the span it covered is gone."""
        unit = column("Claire Dubois", "Sophie Marchand")
        across = Detection(unit.id, 7, 20, "PERSON", 0.85, "Dubois\nSophie")
        detections = [found(unit, "Claire Dubois"), across]

        typed = columns.type_columns([unit], detections)

        assert across not in typed
        assert spans(typed, unit) == ["Claire Dubois", "Sophie Marchand"]

    def test_a_unit_that_is_not_a_column_is_untouched(self):
        """Prose has no cells, so nothing here applies to it."""
        unit = TextUnit("content", "Claire Dubois habite à Nantes.", "document")
        detections = [found(unit, "Claire Dubois")]

        assert columns.type_columns([unit], detections) == detections

    def test_each_cell_says_it_belongs_to_a_column_decision(self):
        """The review screen collapses these into one row on this flag."""
        unit = column("Claire Dubois", "Sophie Marchand")
        detections = [found(unit, "Claire Dubois")]

        typed = columns.type_columns([unit], detections)

        assert [item.column for item in typed] == [True, True]

    def test_a_cell_is_its_own_excerpt(self):
        """The context of a cell is its column's name, not the cell beside it."""
        unit = column("Claire Dubois", "Sophie Marchand")
        detections = [found(unit, "Claire Dubois")]

        typed = columns.type_columns([unit], detections)

        assert [item.excerpt for item in typed] == ["Claire Dubois", "Sophie Marchand"]

    def test_a_typed_cell_is_never_ranked_as_unlikely(self):
        """
        A one-word cell is the shape the model gets wrong in prose, and the
        reason those are ranked low. In a column it is the normal case, and the
        column itself is the evidence.
        """
        unit = column("Dubois", "Marchand")
        detections = [Detection(unit.id, 0, 6, "PERSON", 0.85, "Dubois", likely=False)]

        typed = columns.type_columns([unit], detections)

        assert all(item.likely for item in typed)

    def test_detections_of_other_units_come_back_untouched(self):
        unit = column("Claire Dubois", "Sophie Marchand")
        other = TextUnit("content", "Écrit par Yann Le Bris.", "document")
        elsewhere = found(other, "Yann Le Bris")

        typed = columns.type_columns(
            [unit, other], [found(unit, "Claire Dubois"), elsewhere]
        )

        assert elsewhere in typed

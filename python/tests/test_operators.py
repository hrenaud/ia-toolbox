"""
Turning detections into the text that replaces them.

Two operators ship: Replace, which puts a labelled placeholder in place of the
entity, and Mask, which keeps a short tail so a user can still tell two records
apart. Both are pure: they return edits and never touch a file.

The property that matters most is stability. The same person named in four
places must become the same placeholder in all four, or the document stops
making sense and the reader cannot follow who is who.
"""

import pytest

from document_worker.anonymization.model import Detection
from document_worker.anonymization.operators import mask, replace


def detection(text, entity_type="PERSON", unit_id="u", start=0):
    return Detection(
        unit_id=unit_id,
        start=start,
        end=start + len(text),
        entity_type=entity_type,
        score=0.9,
        text=text,
    )


class TestReplace:
    def test_a_detection_becomes_a_labelled_placeholder(self):
        [edit] = replace([detection("Jean Dupont")])

        assert edit.replacement == "[PERSONNE 1]"
        assert (edit.unit_id, edit.start, edit.end) == ("u", 0, 11)

    def test_the_same_value_gets_the_same_placeholder_everywhere(self):
        edits = replace(
            [
                detection("Jean Dupont", unit_id="a"),
                detection("Jean Dupont", unit_id="b", start=40),
            ]
        )

        assert [edit.replacement for edit in edits] == ["[PERSONNE 1]", "[PERSONNE 1]"]

    def test_different_values_get_different_numbers(self):
        edits = replace([detection("Jean"), detection("Marie", start=9)])

        assert [edit.replacement for edit in edits] == ["[PERSONNE 1]", "[PERSONNE 2]"]

    # Numbering restarts per entity type, so the first organisation is
    # "[ORGANISATION 1]" even when three people were seen first.
    def test_numbering_is_per_entity_type(self):
        edits = replace(
            [
                detection("Jean"),
                detection("Marie", start=9),
                detection("Novagaia", entity_type="ORGANIZATION", start=20),
            ]
        )

        assert edits[-1].replacement == "[ORGANISATION 1]"

    # Surrounding whitespace and case are not part of someone's identity. Two
    # spellings of the same name in the same document are the same person.
    def test_matching_ignores_case_and_surrounding_whitespace(self):
        edits = replace([detection("Jean Dupont"), detection("jean dupont ", start=20)])

        assert [edit.replacement for edit in edits] == ["[PERSONNE 1]", "[PERSONNE 1]"]

    def test_english_labels_are_used_when_asked(self):
        [edit] = replace([detection("Jean Dupont")], language="en")

        assert edit.replacement == "[PERSON 1]"

    # An entity type with no label of its own still produces a usable
    # placeholder rather than an exception, because a new recognizer must never
    # be able to break the write path.
    def test_an_unlabelled_entity_type_falls_back_to_its_own_name(self):
        [edit] = replace([detection("ZX-1", entity_type="CUSTOM_ID")])

        assert edit.replacement == "[CUSTOM_ID 1]"


class TestMask:
    def test_everything_but_a_short_tail_is_hidden(self):
        [edit] = mask([detection("0612345678", entity_type="PHONE_NUMBER")])

        assert edit.replacement == "••••••5678"

    # Never leave more than half of a short value readable: on a four-character
    # value, a four-character tail would be the value itself.
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("12345678", "••••5678"),
            ("1234", "••34"),
            ("123", "••3"),
            ("12", "•2"),
            ("1", "•"),
        ],
    )
    def test_the_tail_never_exceeds_half_the_value(self, value, expected):
        [edit] = mask([detection(value, entity_type="PHONE_NUMBER")])

        assert edit.replacement == expected

    def test_the_masked_value_keeps_the_length_of_the_original(self):
        [edit] = mask([detection("jean@example.fr", entity_type="EMAIL_ADDRESS")])

        assert len(edit.replacement) == len("jean@example.fr")


class TestBothOperators:
    @pytest.mark.parametrize("operator", [replace, mask], ids=["replace", "mask"])
    def test_an_empty_detection_list_produces_no_edits(self, operator):
        assert operator([]) == []

    @pytest.mark.parametrize("operator", [replace, mask], ids=["replace", "mask"])
    def test_the_span_of_the_detection_is_preserved_exactly(self, operator):
        [edit] = operator([detection("Jean", unit_id="slide-4", start=17)])

        assert (edit.unit_id, edit.start, edit.end) == ("slide-4", 17, 21)

"""
The mapping between a document's text and the places that text is stored.

Every adapter above plain text has the same problem: the string a detector
needs is one continuous run of characters, but the document keeps it in
fragments — OOXML runs split by formatting or editing history, HTML text split
by inline markup. A name is routinely stored as ``Jean`` + ` Dup` + ``ont``.

These tests pin the behaviour that makes replacement safe. Getting any of it
wrong puts a replacement at the wrong offset, which in an anonymization tool
means leaving personal data in the output while reporting success.
"""

import pytest

from document_worker.anonymization.model import Edit
from document_worker.anonymization.textmap import TextMap


def plan(pieces, edits):
    """Build a map over ``pieces`` and return the new text per segment key."""
    return TextMap.build(pieces).plan(edits)


class TestConcatenation:
    def test_text_is_the_fragments_in_order(self):
        text_map = TextMap.build([("a", "Jean"), ("b", " Dup"), ("c", "ont")])

        assert text_map.text == "Jean Dupont"

    # No separator is inserted between fragments. One inserted character shifts
    # every offset after it, which is exactly how a replacement lands on the
    # wrong word.
    def test_no_separator_is_inserted_between_fragments(self):
        text_map = TextMap.build([("a", "anti"), ("b", "constitution")])

        assert text_map.text == "anticonstitution"

    # A separator carries no key: it belongs to the text the detector sees, so
    # the last word of one paragraph does not fuse with the first of the next,
    # but it is not a place anything can be written back to.
    def test_a_keyless_separator_joins_the_text_without_being_writable(self):
        text_map = TextMap.build([("a", "Fin"), (None, "\n"), ("b", "Début")])

        assert text_map.text == "Fin\nDébut"
        assert text_map.plan([Edit("u", 0, 3, "X")]) == {"a": "X"}

    def test_empty_fragments_are_kept_so_their_keys_stay_addressable(self):
        text_map = TextMap.build([("a", ""), ("b", "Jean")])

        assert text_map.text == "Jean"
        assert text_map.plan([Edit("u", 0, 4, "X")]) == {"b": "X"}


class TestSingleFragmentEdits:
    def test_a_substring_edit_keeps_the_surrounding_text(self):
        assert plan(
            [("a", "Contact: jean@example.fr pour la suite")],
            [Edit("u", 9, 24, "[EMAIL 1]")],
        ) == {"a": "Contact: [EMAIL 1] pour la suite"}

    # Applying edits in the order given would invalidate every offset after the
    # first length change. They are applied from the highest offset down.
    def test_several_edits_in_one_fragment_are_applied_from_the_end(self):
        assert plan(
            [("a", "Jean et Marie")],
            [Edit("u", 0, 4, "[PERSONNE 1]"), Edit("u", 8, 13, "[PERSONNE 2]")],
        ) == {"a": "[PERSONNE 1] et [PERSONNE 2]"}

    def test_the_order_the_edits_arrive_in_does_not_matter(self):
        ascending = plan(
            [("a", "Jean et Marie")],
            [Edit("u", 0, 4, "[P 1]"), Edit("u", 8, 13, "[P 2]")],
        )
        descending = plan(
            [("a", "Jean et Marie")],
            [Edit("u", 8, 13, "[P 2]"), Edit("u", 0, 4, "[P 1]")],
        )

        assert ascending == descending == {"a": "[P 1] et [P 2]"}

    def test_untouched_fragments_are_absent_from_the_plan(self):
        assert plan([("a", "Jean"), ("b", " habite ici")], [Edit("u", 0, 4, "X")]) == {
            "a": "X"
        }


class TestEditsAcrossFragments:
    # The replacement goes entirely into the fragment where the entity starts,
    # so it inherits that fragment's formatting. Inventing formatting for a
    # replacement, or splitting it across runs, are both worse.
    def test_a_span_across_fragments_writes_into_the_first_and_empties_the_rest(
        self,
    ):
        assert plan(
            [("a", "Jean"), ("b", " Dup"), ("c", "ont")],
            [Edit("u", 0, 11, "[PERSONNE 1]")],
        ) == {"a": "[PERSONNE 1]", "b": "", "c": ""}

    def test_a_partial_span_keeps_the_text_outside_it(self):
        assert plan(
            [("a", "Cher Jean"), ("b", " Dupont, bonjour")],
            [Edit("u", 5, 16, "[PERSONNE 1]")],
        ) == {"a": "Cher [PERSONNE 1]", "b": ", bonjour"}

    def test_a_span_over_a_separator_leaves_the_separator_in_place(self):
        assert plan(
            [("a", "Jean"), (None, " "), ("b", "Dupont")],
            [Edit("u", 0, 11, "[PERSONNE 1]")],
        ) == {"a": "[PERSONNE 1]", "b": ""}

    def test_a_span_ending_exactly_at_a_boundary_does_not_touch_the_next(self):
        assert plan([("a", "Jean"), ("b", "Dupont")], [Edit("u", 0, 4, "X")]) == {
            "a": "X"
        }


class TestRejectedEdits:
    # A bad offset must stop the write, not silently corrupt the document. The
    # worker turns this into invalid_request.
    @pytest.mark.parametrize(
        "edit",
        [
            Edit("u", -1, 4, "X"),
            Edit("u", 0, 99, "X"),
            Edit("u", 4, 2, "X"),
            Edit("u", 3, 3, "X"),
        ],
        ids=["negative", "past the end", "reversed", "empty"],
    )
    def test_an_offset_outside_the_text_is_refused(self, edit):
        with pytest.raises(ValueError):
            plan([("a", "Jean")], [edit])

    def test_overlapping_edits_are_refused(self):
        with pytest.raises(ValueError):
            plan(
                [("a", "Jean Dupont")],
                [Edit("u", 0, 6, "X"), Edit("u", 4, 11, "Y")],
            )

    def test_an_edit_entirely_inside_a_separator_is_refused(self):
        with pytest.raises(ValueError):
            plan(
                [("a", "Jean"), (None, "\n\n"), ("b", "Marie")], [Edit("u", 4, 6, "X")]
            )

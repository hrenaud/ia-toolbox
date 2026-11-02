"""
Detection over text units, in French and English.

Two halves, deliberately separated. The pure half — check-key validation and
overlap resolution — is our own logic and is asserted exactly. The model half
asserts only plumbing: that a detection comes back with the right entity type
and offsets that land on the right characters. It never asserts a recall rate,
because a threshold on a model's behaviour turns a model upgrade into a red
build, and the number would be the model's property rather than ours.

The NIR fixtures are real in shape and synthetic in content: each check key is
computed from its own body, so they exercise the validation instead of a
hard-coded pair.
"""

import pytest

from document_worker.anonymization import detection, operators
from document_worker.anonymization.model import Detection, TextUnit

# Valid: body "1850578006084" gives check key 91.
VALID_NIR = "1850578006084 91"
# Same body, wrong key.
INVALID_NIR = "1850578006084 12"
# Corsica: department "2A" counts as 19, "2B" as 18.
CORSICA_A_NIR = "183052A123456 34"
CORSICA_B_NIR = "183052B123456 61"


def unit(text: str, context: tuple[str, ...] = ()) -> TextUnit:
    return TextUnit("content", text, "document", context)


def detect(text: str, context: tuple[str, ...] = ()) -> list[Detection]:
    return detection.detect([unit(text, context)])


def typed(detections: list[Detection], entity_type: str) -> list[Detection]:
    return [found for found in detections if found.entity_type == entity_type]


def made(
    start: int, end: int, entity_type: str = "PERSON", score: float = 0.5
) -> Detection:
    """A detection with no text behind it, for the pure resolution tests."""
    return Detection("content", start, end, entity_type, score, "x" * (end - start))


class TestNirValidation:
    """The check key is the whole point: 15 digits alone is not a NIR."""

    @pytest.mark.parametrize(
        "value", [VALID_NIR, CORSICA_A_NIR, CORSICA_B_NIR, VALID_NIR.replace(" ", "")]
    )
    def test_a_valid_number_passes(self, value: str):
        assert detection.nir_key_matches(value)

    @pytest.mark.parametrize(
        "value",
        [
            INVALID_NIR,
            "1850578006084 90",
            "123456789012345",
            "",
            "18505780060849",
            "1850578006084 9x",
            "183052C123456 34",
        ],
    )
    def test_anything_else_fails(self, value: str):
        assert not detection.nir_key_matches(value)

    def test_the_number_is_found_in_a_sentence(self):
        text = f"Son numéro de sécurité sociale est le {VALID_NIR}."

        found = typed(detect(text), "FR_NIR")

        assert [text[d.start : d.end] for d in found] == [VALID_NIR]

    def test_a_wrong_key_is_not_reported(self):
        """A bare 15-digit pattern would put this in front of the user."""
        assert typed(detect(f"Référence interne {INVALID_NIR}."), "FR_NIR") == []


class TestOverlapResolution:
    """Two recognizers hitting the same characters must yield one detection."""

    def test_the_longer_span_wins(self):
        kept = detection.resolve_overlaps([made(0, 5), made(0, 11)])

        assert [(d.start, d.end) for d in kept] == [(0, 11)]

    def test_the_longer_span_wins_even_when_it_starts_later(self):
        kept = detection.resolve_overlaps([made(0, 5), made(3, 20)])

        assert [(d.start, d.end) for d in kept] == [(3, 20)]

    def test_equal_spans_resolve_by_score(self):
        kept = detection.resolve_overlaps(
            [made(0, 5, "PERSON", 0.4), made(0, 5, "LOCATION", 0.85)]
        )

        assert [d.entity_type for d in kept] == ["LOCATION"]

    def test_touching_spans_do_not_overlap(self):
        """An end offset is exclusive, so (0,5) and (5,9) are two detections."""
        kept = detection.resolve_overlaps([made(0, 5), made(5, 9)])

        assert len(kept) == 2

    def test_the_same_offsets_in_different_units_never_conflict(self):
        other = Detection("other", 0, 5, "PERSON", 0.5, "xxxxx")

        kept = detection.resolve_overlaps([made(0, 5), other])

        assert len(kept) == 2

    def test_the_result_is_ordered_by_position(self):
        kept = detection.resolve_overlaps([made(20, 25), made(0, 5), made(10, 12)])

        assert [d.start for d in kept] == [0, 10, 20]

    def test_identical_detections_resolve_deterministically(self):
        """Equal span and equal score must still give one stable answer."""
        pair = [made(0, 5, "LOCATION", 0.5), made(0, 5, "PERSON", 0.5)]

        first = detection.resolve_overlaps(pair)
        second = detection.resolve_overlaps(list(reversed(pair)))

        assert [d.entity_type for d in first] == [d.entity_type for d in second]

    def test_nothing_is_invented(self):
        assert detection.resolve_overlaps([]) == []


class TestFrench:
    def test_a_person_and_a_place(self):
        text = "Le dossier de Marie Lefebvre a été transmis à la mairie de Bordeaux."

        found = detect(text)

        assert "Marie Lefebvre" in [
            text[d.start : d.end] for d in typed(found, "PERSON")
        ]
        assert "Bordeaux" in [text[d.start : d.end] for d in typed(found, "LOCATION")]

    def test_a_french_phone_number(self):
        text = "Vous pouvez me joindre au 06 12 34 56 78 à partir de 9h."

        found = typed(detect(text), "PHONE_NUMBER")

        assert [text[d.start : d.end].strip() for d in found] == ["06 12 34 56 78"]

    def test_an_iban(self):
        text = "Virement sur le compte FR7630006000011234567890189 avant vendredi."

        found = typed(detect(text), "IBAN_CODE")

        assert [text[d.start : d.end] for d in found] == ["FR7630006000011234567890189"]


class TestEnglish:
    def test_a_person_an_organization_and_an_email(self):
        text = "Invoice from Microsoft Corporation to Jane Doe, jane.doe@example.com."

        found = detect(text)

        assert "Jane Doe" in [text[d.start : d.end] for d in typed(found, "PERSON")]
        assert "Microsoft Corporation" in [
            text[d.start : d.end] for d in typed(found, "ORGANIZATION")
        ]
        assert "jane.doe@example.com" in [
            text[d.start : d.end] for d in typed(found, "EMAIL_ADDRESS")
        ]

    def test_a_credit_card(self):
        text = "Card 4111111111111111 was declined."

        found = typed(detect(text), "CREDIT_CARD")

        assert [text[d.start : d.end] for d in found] == ["4111111111111111"]


class TestBothLanguagesAtOnce:
    def test_a_mixed_document_is_covered_by_one_call(self):
        """Mixed-language documents are the norm here, not an edge case."""
        text = "Contact: Marie Lefebvre. Please forward to Jane Doe in London."

        names = [d.text for d in typed(detect(text), "PERSON")]

        assert "Marie Lefebvre" in names
        assert "Jane Doe" in names

    def test_the_same_span_is_not_reported_once_per_language(self):
        text = "jane.doe@example.com"

        assert len(typed(detect(text), "EMAIL_ADDRESS")) == 1


class TestWhatEveryDetectionCarries:
    def test_detections_name_their_unit(self):
        units = [
            TextUnit("column-0", "Marie Lefebvre", "column 0"),
            TextUnit("column-1", "jane.doe@example.com", "column 1"),
        ]

        found = detection.detect(units)

        assert {d.unit_id for d in found} == {"column-0", "column-1"}

    def test_offsets_are_in_the_unit_text(self):
        text = "Virement sur le compte FR7630006000011234567890189 avant vendredi."

        for found in detect(text):
            assert text[found.start : found.end] == found.text

    def test_a_score_is_kept(self):
        found = detect("jane.doe@example.com")

        assert all(0 < d.score <= 1 for d in found)

    def test_a_span_does_not_swallow_the_words_around_it(self):
        """
        The French model tags "de Marie Lefebvre", preposition included. Left
        alone, the replacement would delete a word the sentence needs and
        redact one that is not personal data.
        """
        text = "Le dossier de Marie Lefebvre a été transmis."

        found = typed(detect(text), "PERSON")

        assert [d.text for d in found] == ["Marie Lefebvre"]

    def test_an_empty_unit_yields_nothing(self):
        assert detection.detect([unit("")]) == []

    def test_no_units_yields_nothing_and_loads_no_model(self):
        assert detection.detect([]) == []


class TestEntityCoverage:
    """
    Every type we detect must have a placeholder in both languages.

    An unlabelled type falls back to its own name, so the test is the shape of
    that fallback: in French no label is the entity type itself, and in English
    none contains an underscore.
    """

    @pytest.mark.parametrize("entity_type", detection.ENTITY_TYPES)
    def test_every_detected_type_has_a_french_label(self, entity_type: str):
        detected = Detection("content", 0, 5, entity_type, 0.8, "value")

        [edit] = operators.replace([detected], language="fr")

        assert edit.replacement != f"[{entity_type} 1]"

    @pytest.mark.parametrize("entity_type", detection.ENTITY_TYPES)
    def test_every_detected_type_has_an_english_label(self, entity_type: str):
        detected = Detection("content", 0, 5, entity_type, 0.8, "value")

        [edit] = operators.replace([detected], language="en")

        assert "_" not in edit.replacement

    def test_us_specific_recognizers_are_not_loaded(self):
        """A US SSN pattern in a French document is a false positive factory."""
        found = detect("Reference 078-05-1120 on file.")

        assert typed(found, "US_SSN") == []

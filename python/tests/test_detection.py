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


class TestSpansNeverCrossALineBreak:
    """No value contains a newline, so no detection may either.

    An adapter separates the blocks it extracts with a line break the document
    does not own — a heading from the paragraph under it, one table cell from
    the next. The small French model happily runs a name across that break and
    returns "Claire Dubois\\nParticipants", and replacing that span writes the
    pseudonym into the first block and empties the second: the heading is gone.
    Splitting at the break keeps both halves instead of truncating to one.
    """

    def test_a_span_over_two_lines_becomes_one_span_per_line(self):
        text = "Claire Dubois\nParticipants"

        assert detection.line_spans(text, 0, len(text)) == [(0, 13), (14, 26)]

    def test_a_span_within_one_line_is_left_alone(self):
        assert detection.line_spans("Claire Dubois", 0, 13) == [(0, 13)]

    def test_a_line_holding_nothing_but_punctuation_is_dropped(self):
        text = "Claire\n . \nMarie"

        assert detection.line_spans(text, 0, len(text)) == [(0, 6), (11, 16)]

    def test_each_line_keeps_the_offsets_of_the_whole_text(self):
        text = "Titre\nl'Université \n Claire Dubois"
        spans = detection.line_spans(text, 6, len(text))

        assert [text[start:end] for start, end in spans] == [
            "l'Université",
            "Claire Dubois",
        ]


class TestANameCarriesACapital:
    """A proper noun is capitalised, in French as in English.

    The small model returns the words around a name as part of it — "la mairie
    de Rennes", "porte le numéro de sécurité" — and sometimes returns a run of
    ordinary words with no name in it at all. Cutting the lowercase words off
    the front leaves the value; a span with no capital left in it held no name
    to begin with.
    """

    def test_the_lowercase_words_in_front_are_cut_off(self):
        text = "la mairie de Rennes"

        assert detection.name_span(text, 0, len(text)) == (13, 19)

    def test_a_span_without_a_single_capital_is_dropped(self):
        text = "porte le numéro de sécurité"
        start, end = detection.name_span(text, 0, len(text))

        assert start == end

    def test_a_name_is_left_alone(self):
        assert detection.name_span("Claire Dubois", 0, 13) == (0, 13)

    def test_an_elided_article_is_cut_off_too(self):
        text = "l'antenne de Rennes"

        assert detection.name_span(text, 0, len(text)) == (13, 19)


class TestTheExcerptAroundAValue:
    """What the review screen shows so a decision can be made at all.

    "Loire" alone is unanswerable; "salle Loire — locaux de" is a room. A few
    words either side is what turns a list of values into a list of questions
    someone can actually answer.
    """

    def test_a_few_words_on_each_side(self):
        text = "Le dossier de Sophie Marchand est transféré à Rennes."

        assert detection.excerpt(text, 14, 29) == text

    def test_the_value_is_marked_inside_the_excerpt(self):
        text = "Le dossier de Sophie Marchand est transféré à Rennes."

        found = detection.excerpt(text, 14, 29)

        assert "Sophie Marchand" in found

    def test_a_long_line_is_cut_on_both_sides(self):
        text = f"{'mot ' * 30}Nantes{' mot' * 30}"
        start = text.index("Nantes")

        found = detection.excerpt(text, start, start + 6)

        assert found.startswith("…")
        assert found.endswith("…")
        assert "Nantes" in found
        assert len(found) < 100

    def test_the_cut_falls_between_words(self):
        """A half word reads as a typo and makes the excerpt harder to scan."""
        text = f"{'alpha ' * 20}Nantes{' omega' * 20}"
        start = text.index("Nantes")

        found = detection.excerpt(text, start, start + 6).strip("… ")

        assert found.startswith("alpha")
        assert found.endswith("omega")

    def test_a_line_break_is_shown_as_a_space(self):
        """The excerpt is one line in the review list, whatever it came from."""
        text = "Rédigé par :\nClaire Dubois\nParticipants"
        start = text.index("Claire")

        found = detection.excerpt(text, start, start + 13)

        assert "\n" not in found

    def test_every_detection_carries_one(self):
        found = detection.detect([unit("Le dossier de Sophie Marchand.")])

        assert all(item.excerpt for item in found)


class TestGuessingTheLanguage:
    """Which model reads the names, decided from the text itself.

    Running both models over one document was measured as the main source of
    noise: the English model on a French report is what returned "Claire
    Dubois" as an organization and a postcode as a date. The grammar words of
    each language are the cheapest signal that separates them, and spaCy
    already ships both lists.
    """

    def test_a_french_document(self):
        text = "Le dossier de Sophie Marchand est transféré à l'antenne de Rennes."

        assert detection.guess_language(text) == "fr"

    def test_an_english_document(self):
        text = "The file of Sophie Marchand was transferred to the Rennes office."

        assert detection.guess_language(text) == "en"

    def test_a_short_french_line(self):
        assert detection.guess_language("Facture de Jean Dupont") == "fr"

    def test_a_short_english_line(self):
        assert detection.guess_language("Invoice for John Smith") == "en"

    def test_a_text_with_no_grammar_at_all_falls_back_to_french(self):
        """A list of names says nothing; the default is the app's audience."""
        assert detection.guess_language("Dupont\nMartin\nDurand") == "fr"


class TestOnlyOneModelReadsTheNames:
    """Names come from one language; patterns come from both.

    An IBAN and a credit card are decided by a check digit, not by grammar,
    and Presidio ships no French credit card recognizer — so the pattern
    recognizers have to keep running in both languages. The models that guess
    at names are the ones that must not.
    """

    def test_the_other_model_does_not_contribute_names(self):
        text = "The file of Sophie Marchand was transferred to the Rennes office."

        found = detection.detect([unit(text)], language="fr")

        assert typed(found, "PERSON") == []

    def test_the_document_language_still_finds_its_names(self):
        text = "The file of Sophie Marchand was transferred to the Rennes office."

        found = detection.detect([unit(text)], language="en")

        assert "Sophie Marchand" in [item.text for item in found]

    def test_a_credit_card_is_found_whatever_the_language(self):
        text = "La carte 4111 1111 1111 1111 est résiliée."

        found = detection.detect([unit(text)], language="fr")

        assert typed(found, "CREDIT_CARD") != []


class TestAnAddressIsOneValue:
    """A postal address is one piece of personal data, not three.

    The model returns the street, the postcode and the town separately, and
    the house number not at all. Replacing each part on its own leaves "12
    [LIEU 3], [DATE 4] [LIEU 5]" in the copy: the number survives and the
    shape of the address is still legible. The pieces have to become one span,
    number included, before the user is ever asked about them.
    """

    def spans(self, text: str) -> list[tuple[str, str]]:
        found = detection.detect([unit(text)])
        return [(item.entity_type, item.text) for item in found]

    def test_street_postcode_and_town_become_one_location(self):
        text = "Son adresse est le 12 rue des Lilas, 44000 Nantes."

        assert ("LOCATION", "12 rue des Lilas, 44000 Nantes") in self.spans(text)

    def test_the_house_number_is_part_of_it(self):
        text = "Son adresse est le 12 rue des Lilas, 44000 Nantes."
        found = detection.detect([unit(text)])
        address = next(item for item in found if "Lilas" in item.text)

        assert text[address.start : address.end].startswith("12 ")

    def test_a_bare_town_is_left_alone(self):
        text = "La réunion a eu lieu à Nantes le 14 mars."

        assert ("LOCATION", "Nantes") in self.spans(text)

    def test_two_towns_in_a_list_are_not_merged(self):
        """No postcode and no house number: nothing says this is an address."""
        found = detection.merge_addresses(
            [
                Detection("c", 0, 6, "LOCATION", 0.85, "Nantes"),
                Detection("c", 8, 14, "LOCATION", 0.85, "Rennes"),
            ],
            {"c": "Nantes, Rennes"},
        )

        assert [item.text for item in found] == ["Nantes", "Rennes"]

    def test_a_postcode_anchors_the_merge(self):
        found = detection.merge_addresses(
            [Detection("c", 7, 13, "LOCATION", 0.85, "Nantes")],
            {"c": "44000, Nantes"},
        )

        assert [item.text for item in found] == ["44000, Nantes"]

    def test_the_merged_span_is_a_location(self):
        found = detection.merge_addresses(
            [
                Detection("c", 3, 16, "LOCATION", 0.85, "rue des Lilas"),
                Detection("c", 18, 23, "DATE_TIME", 0.85, "44000"),
            ],
            {"c": "12 rue des Lilas, 44000"},
        )

        assert [(item.entity_type, item.text) for item in found] == [
            ("LOCATION", "12 rue des Lilas, 44000")
        ]

    def test_a_line_break_stops_the_merge(self):
        """A span across a block boundary empties the block when rewritten."""
        found = detection.merge_addresses(
            [Detection("c", 13, 17, "LOCATION", 0.85, "Lieu")],
            {"c": "14 mars 2026\nLieu"},
        )

        assert [item.text for item in found] == ["Lieu"]

    def test_a_word_between_two_places_stops_the_merge(self):
        found = detection.merge_addresses(
            [
                Detection("c", 3, 16, "LOCATION", 0.85, "rue des Lilas"),
                Detection("c", 24, 30, "LOCATION", 0.85, "Nantes"),
            ],
            {"c": "12 rue des Lilas et aussi Nantes"},
        )

        assert len(found) == 2


class TestAFunctionWordIsNotAName:
    """ "Le" opening a sentence is an article, not an organization.

    The model tags the first capitalised token of a segment, and in French
    that token is very often "Le", "La" or "Les". No judgement is needed to
    rule those out, and spaCy already ships the list of them, so the one
    decision left is the acronym: "LE" in capitals can be a brand.
    """

    def test_a_capitalised_article_is_not_a_name(self):
        assert detection.is_function_word("Le") is True

    def test_an_english_function_word_is_not_a_name_either(self):
        assert detection.is_function_word("The") is True

    def test_an_ordinary_word_is_left_to_the_ranking(self):
        assert detection.is_function_word("Participants") is False

    def test_a_real_name_is_never_a_function_word(self):
        assert detection.is_function_word("Nantes") is False

    def test_an_acronym_survives(self):
        assert detection.is_function_word("LE") is False

    def test_several_words_are_never_a_function_word(self):
        assert detection.is_function_word("Le Mans") is False

    def test_the_article_is_not_reported(self):
        found = detect("Décisions\n\nLe dossier est transféré.")

        assert "Le" not in [item.text for item in found]


class TestLessLikelyNames:
    """A lone capitalised word opening a line is where the model guesses.

    A heading is one short segment with no sentence around it, so the model
    decides on the capital alone and calls "Participants" a person. The rule
    costs a cell holding nothing but a one-word name, which is why such a
    detection is still reported — ranked below the rest, never dropped.
    """

    def test_a_lone_word_opening_a_line_is_less_likely(self):
        text = "Nantes\nParticipants"

        assert detection.is_likely(text, 7, 19, "PERSON") is False

    def test_a_word_inside_a_line_is_likely(self):
        text = "Lieu : Nantes"

        assert detection.is_likely(text, 7, 13, "LOCATION") is True

    def test_two_words_opening_a_line_are_likely(self):
        text = "Claire Dubois"

        assert detection.is_likely(text, 0, 13, "PERSON") is True

    def test_only_names_are_ranked_this_way(self):
        text = "2026"

        assert detection.is_likely(text, 0, 4, "DATE_TIME") is True

    def test_every_detection_says_how_likely_it_is(self):
        found = detect("Le dossier de Marie Lefebvre est clos.")

        assert all(isinstance(item.likely, bool) for item in found)


class TestNamesAreReadLineByLine:
    """
    A unit's text is not prose, so the model must not be handed all of it.

    An adapter joins a heading, a paragraph and a table row with newlines, and
    none of them ends in a full stop. Given the whole thing at once, a small
    model reads one run-on sentence: names in the middle of it go unnoticed and
    headings come back as people. Patterns are the opposite case — a NIR is
    accepted on the strength of the words introducing it — so they keep the
    whole text.
    """

    def stub(self, monkeypatch) -> list[tuple[str, str]]:
        """Record (text, language) for each call, and report one name per call."""
        calls: list[tuple[str, str]] = []

        class Result:
            entity_type = "PERSON"
            score = 0.85
            start = 0

            def __init__(self, end: int):
                self.end = end

        class Analyzer:
            def analyze(self, text, language, context=None):
                calls.append((text, language))
                return [Result(len(text))] if text.strip() else []

        monkeypatch.setattr(detection, "_analyzer", lambda: Analyzer())
        return calls

    def test_the_model_is_given_one_line_at_a_time(self, monkeypatch):
        calls = self.stub(monkeypatch)

        detection.detect([unit("Participants\nClaire Dubois est là.")], language="fr")

        assert ("Participants", "fr") in calls
        assert ("Claire Dubois est là.", "fr") in calls

    def test_patterns_still_see_the_whole_text(self, monkeypatch):
        calls = self.stub(monkeypatch)
        text = "Participants\nClaire Dubois est là."

        detection.detect([unit(text)], language="fr")

        assert (text, "fr") in calls

    def test_offsets_come_back_in_the_unit_text(self, monkeypatch):
        self.stub(monkeypatch)
        text = "Participants\nClaire Dubois est là."

        found = detection.detect([unit(text)], language="fr")

        assert all(text[item.start : item.end] == item.text for item in found)
        # The second line, its full stop trimmed off like any other span's.
        assert "Claire Dubois est là" in [item.text for item in found]


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

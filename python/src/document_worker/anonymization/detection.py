"""
Finding personal data in a unit's text.

Presidio is the frame, and the parts of it that matter here are the parts the
review screen needs: a span, an entity type and a score per detection, plus
recognizers that validate rather than pattern-match. What this module adds is
the three decisions Presidio leaves open.

**Both languages, every time.** A document is analyzed in French and in
English and the results merged. Mixed-language documents are the norm for this
audience, and asking a user to declare a document's language is asking them to
be wrong about half of them.

**No country-specific recognizers.** ``countries=[]`` keeps the locale-agnostic
recognizers — email, IBAN, credit card, phone, date — and drops the national
identifier recognizers Presidio ships for a dozen other countries. A US social
security pattern loose on a French document is a false-positive factory, and a
review screen full of noise is one a user stops reading. The one national
identifier we want, the French NIR, is added here with its check key.

**Nothing is logged.** Detections are personal data; a log line containing one
is the leak this feature exists to prevent.
"""

import re
from collections.abc import Iterable
from functools import lru_cache

from document_worker.anonymization.model import Detection, TextUnit

ENTITY_TYPES = (
    "PERSON",
    "ORGANIZATION",
    "LOCATION",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "IBAN_CODE",
    "CREDIT_CARD",
    "FR_NIR",
    "DATE_TIME",
)

LANGUAGES = ("fr", "en")

_MODELS = {"fr": "fr_core_news_sm", "en": "en_core_web_sm"}

# Sex, year, month, department, commune, order number, check key. The month and
# department are left loose on purpose: a NIR issued with an unknown birth month
# uses values the calendar does not have, and the check key is what decides.
_NIR_PATTERN = r"\b[1-478]\s?\d{2}\s?\d{2}\s?(?:\d{2}|2[AB])\s?\d{3}\s?\d{3}\s?\d{2}\b"

_NIR_CONTEXT = ["sécurité sociale", "sécu", "nir", "insee", "assuré", "vitale"]

# Corsica predates the two-character department code, so 2A and 2B are worth 19
# and 18 when the key is computed.
_CORSICA = {"2A": "19", "2B": "18"}

_DEPARTMENT = slice(5, 7)

# Punctuation and whitespace a model sometimes leaves inside a span.
_EDGE = ' \t\n\r\xa0.,;:!?()[]{}"«»…'

# Types the model guesses at, as opposed to the ones a pattern decides.
_NAME_TYPES = frozenset({"PERSON", "ORGANIZATION", "LOCATION"})

# Where a capital is required. A person or an organization is named with one in
# both languages, so the words the model sweeps up in front of a name — "la
# mairie de Rennes" — are cut, and a span holding no capital at all — "porte le
# numéro de sécurité", "carte de service" — held no name to begin with.
#
# LOCATION is deliberately left out. An address is lowercase and still personal
# data: cutting "rue des Lilas" down to "Lilas" would leave the street in the
# copy, and the places the model gets wrong are single words anyway, which the
# ranking below already covers.
_CAPITALISED_TYPES = frozenset({"PERSON", "ORGANIZATION"})


def nir_key_matches(value: str) -> bool:
    """
    Whether a French social security number's check key is the right one.

    Arguments:
        value: The candidate, with or without the usual spacing.

    Returns:
        True when the last two digits are ``97 - body mod 97``.
    """
    compact = re.sub(r"\s", "", value).upper()
    if len(compact) != 15:
        return False

    body, key = compact[:13], compact[13:]
    department = _CORSICA.get(body[_DEPARTMENT], body[_DEPARTMENT])
    body = body[:5] + department + body[7:]
    if not (body.isdigit() and key.isdigit()):
        return False

    return 97 - int(body) % 97 == int(key)


def detect(
    units: Iterable[TextUnit], languages: Iterable[str] = LANGUAGES
) -> list[Detection]:
    """
    Find personal data in each unit, in its own offset space.

    Arguments:
        units: What an adapter's ``extract`` returned.
        languages: Languages to analyze in. Both, unless a caller has a reason.

    Returns:
        Detections with overlaps resolved, ordered by unit then position.
    """
    found: list[Detection] = []
    for unit in units:
        if not unit.text.strip():
            continue
        for language in languages:
            found.extend(_analyze(unit, language))
    return resolve_overlaps(found)


def resolve_overlaps(detections: Iterable[Detection]) -> list[Detection]:
    """
    Keep one detection per stretch of text.

    Two recognizers reading the same characters is normal — a phone number is
    also a run of digits — but two edits over one span would corrupt the
    replacement. The longer span wins, because it is the one that covers the
    whole value; between equal spans the higher score wins. Entity type breaks
    a remaining tie, so the same input always gives the same answer.

    Arguments:
        detections: Candidates, in any order.

    Returns:
        The kept detections, ordered by unit then position.
    """
    chosen: list[Detection] = []
    for candidate in sorted(
        detections,
        key=lambda d: (-(d.end - d.start), -d.score, d.unit_id, d.start, d.entity_type),
    ):
        if any(_overlaps(candidate, kept) for kept in chosen):
            continue
        chosen.append(candidate)
    return sorted(chosen, key=lambda d: (d.unit_id, d.start))


def _overlaps(one: Detection, other: Detection) -> bool:
    """End offsets are exclusive, so two touching spans do not overlap."""
    return (
        one.unit_id == other.unit_id and one.start < other.end and other.start < one.end
    )


def _analyze(unit: TextUnit, language: str) -> list[Detection]:
    # `entities=` is not passed on purpose. Not every type has a recognizer in
    # every language — Presidio ships no French credit card recognizer, and the
    # English pass covers it — and asking for one that is missing is a
    # deprecation warning today and an error in a later version. Filtering the
    # results is the same restriction without the per-language bookkeeping.
    results = _analyzer().analyze(
        unit.text,
        language=language,
        # A CSV header or a JSON key is the strongest signal available: a column
        # called "courriel" lifts recall far above what its values alone give.
        context=list(unit.context) or None,
    )
    found = []
    for result in results:
        if result.entity_type not in ENTITY_TYPES:
            continue
        for start, end in line_spans(unit.text, result.start, result.end):
            if result.entity_type in _CAPITALISED_TYPES:
                start, end = name_span(unit.text, start, end)
                if start == end:
                    continue
            found.append(
                Detection(
                    unit.id,
                    start,
                    end,
                    result.entity_type,
                    result.score,
                    unit.text[start:end],
                    is_likely(unit.text, start, end, result.entity_type),
                )
            )
    return found


def name_span(text: str, start: int, end: int) -> tuple[int, int]:
    """
    Narrow a span to the part of it that could be a name.

    Leading words with no capital are cut off, one at a time, because the model
    returns the words that introduce a name as part of it. A span where that
    leaves nothing never held a name.

    Arguments:
        text: The unit's text, which the offsets index into.
        start: Where the span starts.
        end: Where it ends, exclusive.

    Returns:
        The narrowed offsets, equal to each other if no capital was found.
    """
    while start < end and not text[start].isupper():
        space = text.find(" ", start, end)
        if space == -1:
            return start, start
        start = space + 1
        while start < end and text[start] == " ":
            start += 1
    return start, end


def is_likely(text: str, start: int, end: int, entity_type: str) -> bool:
    """
    Whether this detection has the shape the model usually gets right.

    One capitalised word opening a line is where a small model decides on the
    capital alone: a heading is a segment with no sentence around it, so
    "Participants" and "Décisions" come back as people. The same shape is also
    a table cell holding one name, which is why this ranks a detection rather
    than dropping it.

    Arguments:
        text: The unit's text, which the offsets index into.
        start: Where the span starts.
        end: Where it ends, exclusive.
        entity_type: Only the types a model guesses at are ranked.

    Returns:
        False for the shape above, True for everything else.
    """
    if entity_type not in _NAME_TYPES or " " in text[start:end]:
        return True
    return text[:start].rpartition("\n")[2].strip() != ""


def line_spans(text: str, start: int, end: int) -> list[tuple[int, int]]:
    """
    Cut a span at every line break in it, and narrow each piece to its value.

    No value we look for contains a newline, and the newlines in a unit's text
    are mostly not the document's: an adapter puts one between a heading and
    the paragraph under it, or between two table cells, so that the last word
    of one block cannot fuse with the first of the next. The small French model
    still runs a name across that break, and writing one replacement over the
    whole span empties the second block — the heading disappears.

    Splitting rather than truncating is what keeps both halves: a span reading
    "l'Université \\n Claire Dubois" holds one real name, and dropping either
    end would lose it.

    Arguments:
        text: The unit's text, which the offsets index into.
        start: Where the recognizer said the value starts.
        end: Where it said it ends, exclusive.

    Returns:
        The spans to report, in order. Empty if nothing is left of any of them.
    """
    spans = []
    for line_start, line in _lines_between(text, start, end):
        narrowed = _trim(text, line_start, line_start + len(line))
        if narrowed[0] != narrowed[1]:
            spans.append(narrowed)
    return spans


def _lines_between(text: str, start: int, end: int):
    """Yield (offset in ``text``, line) for each line the span touches."""
    offset = start
    for line in text[start:end].split("\n"):
        yield offset, line
        offset += len(line) + 1


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    """
    Narrow a span to the value itself.

    Arguments:
        text: The unit's text, which the offsets index into.
        start: Where the recognizer said the value starts.
        end: Where it said it ends, exclusive.

    Returns:
        The narrowed offsets, equal to each other if nothing is left.
    """
    while start < end and text[start] in _EDGE:
        start += 1
    while end > start and text[end - 1] in _EDGE:
        end -= 1

    return start, end


@lru_cache(maxsize=1)
def _analyzer():
    """
    The analyzer, built once per process.

    Loading two spaCy models takes seconds, so this is cached — and built
    lazily, because the import alone pulls a model loader that writes to stderr
    and must stay below the worker's output redirection.
    """
    from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_analyzer.recognizer_registry import RecognizerRegistry

    class NirRecognizer(PatternRecognizer):
        """The French NIR, accepted only when its check key is right."""

        def __init__(self, supported_language: str):
            super().__init__(
                supported_entity="FR_NIR",
                patterns=[Pattern("FR NIR", _NIR_PATTERN, 0.3)],
                context=_NIR_CONTEXT,
                supported_language=supported_language,
            )

        def validate_result(self, pattern_text: str):
            return nir_key_matches(pattern_text)

    languages = list(LANGUAGES)
    nlp_engine = NlpEngineProvider(
        nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [
                {"lang_code": language, "model_name": _MODELS[language]}
                for language in languages
            ],
        }
    ).create_engine()

    registry = RecognizerRegistry(supported_languages=languages)
    registry.load_predefined_recognizers(
        languages=languages, nlp_engine=nlp_engine, countries=[]
    )
    for language in languages:
        registry.add_recognizer(NirRecognizer(language))

    return AnalyzerEngine(
        registry=registry, nlp_engine=nlp_engine, supported_languages=languages
    )

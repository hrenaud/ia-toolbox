"""
Finding personal data in a unit's text.

Presidio is the frame, and the parts of it that matter here are the parts the
review screen needs: a span, an entity type and a score per detection, plus
recognizers that validate rather than pattern-match. What this module adds is
the three decisions Presidio leaves open.

**One language for the names, both for the patterns.** Running both models
over every document was measured as the main source of false positives: the
English model reading a French report returned people as organizations and a
postcode as a date. So the types a model guesses at come from the document's
own language, which is guessed from the text and which the user can correct.
The recognizers that validate rather than guess keep running in both
languages — a check digit does not care about grammar, and Presidio ships no
French credit card recognizer.

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
from dataclasses import replace
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

# A word, for weighing one language's grammar against the other's. Accented
# letters are in the class and digits are not: "où" is a French word and "2026"
# belongs to no language.
_WORD = re.compile(r"[a-z\xe0-\xff']+")

# The word after a name: one space, then a word. Hyphens and apostrophes are
# part of it, because "Marchand-Dupuis" and "O'Connor" are one surname. Whether
# it carries a capital is checked on the match, where "É" and "E" are the same
# question; a character class would have to spell out an alphabet.
_SURNAME = re.compile(r" (\w[\w'’-]*)")

# How much text to show on each side of a value in the review screen. A few
# words: enough to tell a street from a town, short enough that thirty of them
# stay scannable.
_AROUND = 40

# Types the model guesses at, as opposed to the ones a pattern decides.
_NAME_TYPES = frozenset({"PERSON", "ORGANIZATION", "LOCATION"})

# What only the document's own language may report. A date is in here because
# spaCy's NER is what produces most of them: the English model reading a French
# address returned the postcode "44000" as a date.
_MODEL_TYPES = _NAME_TYPES | {"DATE_TIME"}

# How Presidio labels the recognizer a result came from, and what it calls the
# NER model. The key is `RecognizerResult.RECOGNIZER_NAME_KEY`, spelled out here
# so that reading provenance does not cost the presidio import.
_RECOGNIZER_NAME = "recognizer_name"
_MODEL_RECOGNIZER = "SpacyRecognizer"

# The twelve French month names. They are what makes a date pattern safe: a
# budget table has figures in every shape but no month in it.
_MONTHS = (
    "janvier|f\xe9vrier|mars|avril|mai|juin|juillet|ao\xfbt|septembre|octobre"
    "|novembre|d\xe9cembre"
)

# A French date. A day or a year is required, so "le climat de mars" is not one.
# The numeric form needs both separators, which keeps "3.5" and "12 500" out.
_FRENCH_DATE_PATTERN = (
    r"(?i:"
    rf"\b\d{{1,2}}(?:er)?\s+(?:{_MONTHS})(?:\s+\d{{4}})?"
    rf"|\b(?:{_MONTHS})\s+\d{{4}}"
    r"|\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b"
    r")"
)

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


# A French postcode, and the shape the English pass reports as a date.
_POSTCODE = re.compile(r"\d{5}")

# What an address carries in front of a place name and the model never
# reports: a house number — "12", "12 bis", "3 ter" — or a postcode. Matched
# at the end of the text preceding the span, one step at a time, so that "12
# rue des Lilas" and "44000, Nantes" are both reached from the place name.
#
# No newline on either side: a span reaching across a block boundary is what
# `line_spans` exists to prevent, and rewriting one empties the next block.
_LEADING_NUMBER = re.compile(
    r"(?:\d{5}|\d{1,4}(?:[ \t]*(?:bis|ter))?)[ \t,]*\Z", re.IGNORECASE
)

# What may sit between two parts of one address, and nothing else: separators,
# and at most the postcode no model reports. "rue des Lilas, 44000 Nantes" is
# two detections with the postcode left between them, and the gap is the only
# place it can be read from.
_ADDRESS_GAP = re.compile(r"[ \t,]*(?:\d{5}[ \t,]*)?")


def merge_addresses(
    detections: Iterable[Detection], texts: dict[str, str]
) -> list[Detection]:
    """
    Join the parts of a postal address into one detection.

    The model reports a street, a postcode and a town as three values and the
    house number as none, so replacing them one by one leaves "12 [LIEU 3],
    [DATE 4] [LIEU 5]" in the copy: the number survives and the shape of the
    address is still legible. An address is one piece of personal data and has
    to be one decision.

    A run is only joined when something says "address" rather than "two places
    in a sentence": a postcode among the parts, or a house number in front of
    them. Without that anchor, "Nantes, Rennes" stays two values.

    Arguments:
        detections: Detections for all units, ordered by unit then position.
        texts: Each unit's text, by unit id, to read the gaps and the number.

    Returns:
        The detections with each address run replaced by the span covering it.
    """
    merged: list[Detection] = []
    run: list[Detection] = []

    def flush() -> None:
        if run:
            merged.extend(_join(run, texts))
        run.clear()

    for candidate in detections:
        if not _is_address_part(candidate):
            flush()
            merged.append(candidate)
            continue
        if run and not _joinable(run[-1], candidate, texts):
            flush()
        run.append(candidate)
    flush()
    return sorted(merged, key=lambda d: (d.unit_id, d.start))


def _is_address_part(detection: Detection) -> bool:
    """A town or a street, or the postcode a model sometimes calls a date."""
    return detection.entity_type == "LOCATION" or (
        detection.entity_type == "DATE_TIME"
        and _POSTCODE.fullmatch(detection.text.strip()) is not None
    )


def _joinable(left: Detection, right: Detection, texts: dict[str, str]) -> bool:
    """Whether only separators sit between two parts of one address."""
    if left.unit_id != right.unit_id:
        return False
    gap = texts.get(left.unit_id, "")[left.end : right.start]
    return _ADDRESS_GAP.fullmatch(gap) is not None


def _join(run: list[Detection], texts: dict[str, str]) -> list[Detection]:
    """
    Collapse a run into one LOCATION, or return it untouched.

    Adjacency alone is not an address: "Nantes, Rennes" is two places in a
    sentence. A postcode among the parts, or a house number in front of them,
    is what says otherwise — and the number is then part of the value, since
    leaving it behind is what keeps the address readable in the copy.
    """
    first, last = run[0], run[-1]
    text = texts.get(first.unit_id, "")

    start = first.start
    while (number := _LEADING_NUMBER.search(text[:start])) is not None:
        start = number.start()

    anchored = (
        start != first.start or _POSTCODE.search(text[start : last.end]) is not None
    )
    if not anchored:
        return list(run)

    return [_widen(run, text, start, last.end)]


def _widen(run: list[Detection], text: str, start: int, end: int) -> Detection:
    """One LOCATION covering the whole run, keeping the strongest score."""
    return Detection(
        run[0].unit_id,
        start,
        end,
        "LOCATION",
        max(part.score for part in run),
        text[start:end],
        True,
    )


@lru_cache(maxsize=len(LANGUAGES))
def _stop_words(language: str) -> frozenset[str]:
    """
    The words spaCy itself calls stop words.

    Writing this list by hand would be writing it wrong: the model that
    produces the false positives already ships the vocabulary that describes
    them. Imported here rather than at module level because the worker
    redirects its output before any spaCy import runs.
    """
    from spacy.util import get_lang_class

    return frozenset(get_lang_class(language).Defaults.stop_words)


@lru_cache(maxsize=1)
def _function_words() -> frozenset[str]:
    """Stop words in either language, for rejecting a span whatever the pass."""
    return frozenset().union(*(_stop_words(language) for language in LANGUAGES))


def guess_language(text: str) -> str:
    """
    Which of the supported languages a document is written in.

    Counting grammar words is enough here and costs nothing: a document carries
    dozens of them, they are the words a language cannot be written without,
    and the two lists are already loaded for rejecting false positives. A
    library would answer the same question for every language on earth, and we
    support two.

    Arguments:
        text: The extracted text, or enough of it to be representative.

    Returns:
        A language code from ``LANGUAGES``. French on a tie, including when the
        text holds no grammar at all — a bare list of names says nothing about
        its language, and French is what this audience writes.

    """
    words = _WORD.findall(text.casefold())
    counts = {
        language: sum(word in _stop_words(language) for word in words)
        for language in LANGUAGES
    }
    return max(LANGUAGES, key=lambda language: counts[language])


def is_function_word(value: str) -> bool:
    """
    Whether a span is one ordinary grammatical word rather than a name.

    The model tags the first capitalised token of a segment, and in French
    that token is very often "Le" — an article opening a sentence. No name is
    ever a single stop word, so this is the one case that can be dropped
    outright instead of ranked.

    An all-capitals span is kept: "LE" is a plausible brand, and a two-letter
    acronym is exactly the kind of value a user needs to be asked about.

    Arguments:
        value: The span's text.

    Returns:
        True when the span is a single stop word that is not an acronym.
    """
    word = value.strip()
    if not word or " " in word or word.isupper():
        return False
    return word.casefold() in _function_words()


def excerpt(text: str, start: int, end: int) -> str:
    """
    The value with a few words either side, on one line.

    A value on its own is often unanswerable: "Loire" could be the river, the
    department or, as it happens here, a meeting room. The surrounding words
    are what make the question decidable, and keeping them short is what keeps
    a list of thirty of them readable.

    Arguments:
        text: The unit's text.
        start: Where the value begins, in that text.
        end: Where it ends.

    Returns:
        One line, elided with "…" on each side that was cut.
    """
    left = _word_boundary(text, max(0, start - _AROUND), forward=True)
    right = _word_boundary(text, min(len(text), end + _AROUND), forward=False)
    around = " ".join(text[left:right].split())
    return f"{'…' if left > 0 else ''}{around}{'…' if right < len(text) else ''}"


def _word_boundary(text: str, cut: int, forward: bool) -> int:
    """
    Move a cut off the middle of a word.

    A half word reads as a typo rather than as an elision, which is exactly
    the doubt an excerpt exists to remove. A cut that lands at either end of
    the text is left alone: nothing was severed there.
    """
    if cut in (0, len(text)):
        return cut
    if forward:
        space = re.compile(r"\s").search(text, cut)
        return space.end() if space else cut
    space = max(text.rfind(" ", 0, cut), text.rfind("\n", 0, cut))
    return space if space > 0 else cut


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


def detect(units: Iterable[TextUnit], language: str | None = None) -> list[Detection]:
    """
    Find personal data in each unit, in its own offset space.

    Arguments:
        units: What an adapter's ``extract`` returned.
        language: The language the document is written in. Guessed from the
            text when not given, which is what happens until a user corrects
            it.

    Returns:
        Detections with overlaps resolved, ordered by unit then position.
    """
    # Read once: the language is decided from the whole document before the
    # first unit is analyzed, and `units` is only promised to be iterable.
    analyzed = [unit for unit in units if unit.text.strip()]
    texts = {unit.id: unit.text for unit in analyzed}
    language = language or guess_language("\n".join(texts.values()))

    found: list[Detection] = []
    for unit in analyzed:
        for pass_language in LANGUAGES:
            found.extend(_analyze(unit, pass_language, names=pass_language == language))
    # The excerpt is attached last, once the spans are final: widening an
    # address or dropping an overlap changes what the user is being shown.
    return [
        replace(item, excerpt=excerpt(texts[item.unit_id], item.start, item.end))
        for item in merge_addresses(resolve_overlaps(found), texts)
    ]


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


def _analyze(unit: TextUnit, language: str, names: bool) -> list[Detection]:
    # A CSV header or a JSON key is the strongest signal available: a column
    # called "courriel" lifts recall far above what its values alone give.
    context = list(unit.context) or None
    # `entities=` is not passed on purpose. Not every type has a recognizer in
    # every language — Presidio ships no French credit card recognizer, and the
    # English pass covers it — and asking for one that is missing is a
    # deprecation warning today and an error in a later version. Filtering the
    # results is the same restriction without the per-language bookkeeping.
    results = [
        (0, result)
        for result in _analyzer().analyze(unit.text, language=language, context=context)
        # The model's guesses from this call are dropped even in the names pass:
        # `_name_results` makes them again, from text the model can read.
        if not _from_model(result)
    ]
    if names:
        results.extend(_name_results(unit, language, context))

    found = []
    for offset, result in results:
        if result.entity_type not in ENTITY_TYPES:
            continue
        for start, end in line_spans(
            unit.text, offset + result.start, offset + result.end
        ):
            if result.entity_type in _CAPITALISED_TYPES:
                start, end = name_span(unit.text, start, end)
                if start == end:
                    continue
            if result.entity_type == "PERSON":
                end = surname_end(unit.text, start, end)
            if result.entity_type in _NAME_TYPES and is_function_word(
                unit.text[start:end]
            ):
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


def _name_results(unit: TextUnit, language: str, context: list[str] | None):
    """
    The model's own guesses, read one line at a time.

    A unit's text is not prose. An adapter joins a heading, a paragraph and a
    table row with newlines, and none of them ends in a full stop, so the whole
    text reads as one run-on sentence. A small model given that loses names in
    the middle of it — on the sample meeting report, a person named in a
    paragraph between two headings went unreported — and calls the headings
    people, having nothing but the capital to go on. One line is the largest
    piece of a unit we know reads as a sentence.

    The patterns keep the whole text instead: a NIR is accepted on the strength
    of the words that introduce it, and those can sit a line away.

    Arguments:
        unit: The unit being analyzed.
        language: The document's language. Only this one's model runs.
        context: The unit's own context words, passed through unchanged.

    Yields:
        (offset of the line in the unit's text, result) for each guess.
    """
    analyzer = _analyzer()
    for offset, line in _lines_between(unit.text, 0, len(unit.text)):
        if not line.strip():
            continue
        for result in analyzer.analyze(line, language=language, context=context):
            if _from_model(result):
                yield offset, result


def _from_model(result) -> bool:
    """
    Whether a result is the NER model's guess rather than a pattern's.

    Which pass a result belongs to is a question of where it came from, not of
    what it claims to be. The entity type used to stand in for provenance, until
    the French date pattern started reporting `DATE_TIME` — a type the model
    also reports — and the whole-text pass threw its results away.
    """
    name = (result.recognition_metadata or {}).get(_RECOGNIZER_NAME)
    return name == _MODEL_RECOGNIZER


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


def surname_end(text: str, start: int, end: int) -> int:
    """
    Widen a one-word name onto the capitalised word that follows it.

    The model stops at the first name often enough to matter — "relire avec
    Sophie Marchand" came back as "Sophie" — and half a name is a leak: the
    surname stayed in the anonymized copy and was never offered for review.
    The missing word is capitalised and sits right after the span, so it can be
    taken back without asking the model again.

    The three limits are what keep this from swallowing ordinary words. Only a
    span of one word is widened, since that is the failure's shape and a span
    the model read as two words is a name it read whole. Only one word is
    taken, so a job title after a full name stays out. And only a word directly
    after a single space, so a capital opening the next sentence stays out too.

    Arguments:
        text: The unit's text, which the offsets index into.
        start: Where the span starts.
        end: Where it ends, exclusive.

    Returns:
        The new end, unchanged when there is no surname to take.
    """
    if " " in text[start:end]:
        return end
    match = _SURNAME.match(text, end)
    if not match or not match[1][:1].isupper() or is_function_word(match[1]):
        return end
    return match.end()


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

    class FrenchDateRecognizer(PatternRecognizer):
        """French dates, which the French model has no category for.

        `fr_core_news_sm` labels only `LOC`, `MISC`, `ORG` and `PER`, so a date
        in a French document was never offered and stayed in the anonymized
        copy. The English model does report dates, hence French only here.
        """

        def __init__(self):
            super().__init__(
                supported_entity="DATE_TIME",
                patterns=[Pattern("French date", _FRENCH_DATE_PATTERN, 0.6)],
                supported_language="fr",
            )

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
    registry.add_recognizer(FrenchDateRecognizer())

    return AnalyzerEngine(
        registry=registry, nlp_engine=nlp_engine, supported_languages=languages
    )

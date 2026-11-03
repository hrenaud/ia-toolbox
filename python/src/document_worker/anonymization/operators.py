"""
What replaces a detected entity.

Both operators are pure functions from detections to edits. They hold the
mapping from source value to placeholder in memory for the length of one call
and never write it anywhere: a saved mapping would be a re-identification key,
which is the one artefact an anonymization tool must not leave on disk.
"""

from collections.abc import Iterable

from document_worker.anonymization.model import Detection, Edit

MASK_CHARACTER = "•"
VISIBLE_TAIL = 4

# Placeholders are read by a human in the anonymized copy, so they follow the
# document's language rather than Presidio's entity names. An entity type
# missing here falls back to its own name: a new recognizer must never be able
# to break the write path.
_LABELS = {
    "fr": {
        "PERSON": "PERSONNE",
        "ORGANIZATION": "ORGANISATION",
        "LOCATION": "LIEU",
        "EMAIL_ADDRESS": "COURRIEL",
        "PHONE_NUMBER": "TÉLÉPHONE",
        "IBAN_CODE": "IBAN",
        "CREDIT_CARD": "CARTE BANCAIRE",
        "FR_NIR": "NIR",
        "DATE_TIME": "DATE",
    },
    "en": {
        "PERSON": "PERSON",
        "ORGANIZATION": "ORGANIZATION",
        "LOCATION": "LOCATION",
        "EMAIL_ADDRESS": "EMAIL",
        "PHONE_NUMBER": "PHONE",
        "IBAN_CODE": "IBAN",
        "CREDIT_CARD": "CREDIT CARD",
        "FR_NIR": "NATIONAL ID",
        "DATE_TIME": "DATE",
    },
}


def replace(detections: Iterable[Detection], language: str = "fr") -> list[Edit]:
    """
    Replace each entity with a numbered placeholder such as ``[PERSONNE 1]``.

    The same value gets the same placeholder throughout the document, so a
    reader can still follow who is who. Matching ignores case and surrounding
    whitespace, because neither is part of someone's identity. Numbering
    restarts per entity type.

    Arguments:
        detections: Spans the user kept after review.
        language: Language of the placeholder labels, "fr" or "en".

    Returns:
        One edit per detection, in the order given.
    """
    labels = _LABELS.get(language, _LABELS["fr"])
    assigned: dict[tuple[str, str], int] = {}
    edits = []
    for detection in detections:
        label = labels.get(detection.entity_type, detection.entity_type)
        identity = (detection.entity_type, detection.text.strip().casefold())
        if identity not in assigned:
            assigned[identity] = (
                sum(
                    1
                    for entity_type, _ in assigned
                    if entity_type == detection.entity_type
                )
                + 1
            )
        edits.append(_edit(detection, f"[{label} {assigned[identity]}]"))
    return edits


def mask(detections: Iterable[Detection]) -> list[Edit]:
    """
    Hide each entity behind mask characters, keeping a short readable tail.

    The tail is what lets a user check a record against something they already
    hold — the last digits of a phone number — so it is kept, but never beyond
    half the value: on a four-character value, a four-character tail would be
    the value itself. The masked text keeps the original length, so layout and
    column widths survive.

    Arguments:
        detections: Spans the user kept after review.

    Returns:
        One edit per detection, in the order given.
    """
    edits = []
    for detection in detections:
        tail = min(VISIBLE_TAIL, len(detection.text) // 2)
        hidden = MASK_CHARACTER * (len(detection.text) - tail)
        edits.append(
            _edit(detection, hidden + detection.text[len(detection.text) - tail :])
        )
    return edits


def _edit(detection: Detection, replacement: str) -> Edit:
    return Edit(detection.unit_id, detection.start, detection.end, replacement)

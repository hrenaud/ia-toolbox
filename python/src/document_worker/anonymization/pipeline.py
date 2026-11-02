"""
The two calls the protocol makes, and everything between them.

Anonymization is two round trips because the user decides in the middle:
``analyze_file`` reports what a document contains, ``anonymize_file`` takes back
the subset the user kept and writes a copy. Nothing is held between them. The
document is read twice, which is the point — a document edited or moved while
the user was reviewing it is noticed at write time instead of producing a copy
of content that no longer exists.

Failures are ``AdapterError``, which already carries the code the UI translates.
No failure carries a path, a detection or a library message.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from document_worker.anonymization.model import AdapterError, Detection, TextUnit
from document_worker.protocol import KeptDetection

# The copy's name says what it is, in the user's language, and keeps the source
# extension: an anonymized DOCX is still a DOCX.
_SUFFIXES = {"fr": "-anonymise", "en": "-anonymized"}

_STALE = "The document changed since it was analyzed. Analyze it again, then retry."


@dataclass(frozen=True)
class Analysis:
    """What a document contains, for the user to judge."""

    units: list[TextUnit]
    detections: list[Detection]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class Written:
    """The copy that was written, and what it does not cover."""

    output_path: Path
    notes: tuple[str, ...]


def analyze_file(input_path: Path) -> Analysis:
    """
    Read a document and report the personal data in it. Writes nothing.

    Arguments:
        input_path: Absolute path to the document to analyze.

    Returns:
        The units, the detections in them, and the notes about content that is
        not analyzed.

    Raises:
        AdapterError: The document cannot be read in this format.
    """
    from document_worker.anonymization.detection import detect

    adapter = _adapter_for(input_path)
    extraction = adapter.extract(input_path)
    return Analysis(
        units=extraction.units,
        # Units the format never rewrites are analyzed too. Their detections are
        # shown and not offered for replacement, which is the whole reason the
        # user can be told a formula still holds a name.
        detections=detect(extraction.units),
        notes=extraction.notes,
    )


def anonymize_file(
    input_path: Path,
    output_directory: Path,
    kept: Iterable[KeptDetection],
    operator: str = "replace",
    language: str = "fr",
) -> Written:
    """
    Write an anonymized copy, replacing only what the user kept.

    Arguments:
        input_path: The document, read again here and never written to.
        output_directory: Where the copy goes.
        kept: The detections the user kept, in their units' offset spaces.
        operator: "replace" or "mask".
        language: Language of the placeholders and of the copy's name.

    Returns:
        The path written and the notes about content the copy does not cover.

    Raises:
        AdapterError: The document or the folder cannot be used, or the kept
            detections no longer fit the document.
    """
    from document_worker.anonymization import operators

    if operator not in ("replace", "mask"):
        raise AdapterError("invalid_request", "Choose a supported operator.")

    adapter = _adapter_for(input_path)
    if not output_directory.is_dir():
        raise AdapterError(
            "invalid_output_directory", "Select an existing output folder."
        )

    extraction = adapter.extract(input_path)
    detections = _resolve(extraction.units, kept)
    edits = (
        operators.replace(detections, language=language)
        if operator == "replace"
        else operators.mask(detections)
    )

    output_path = _output_path(output_directory, input_path, language)
    try:
        adapter.apply(input_path, edits, output_path)
    except ValueError as error:
        # The document was read a second time and the offsets no longer fit it.
        output_path.unlink(missing_ok=True)
        raise AdapterError("document_changed", _STALE) from error
    except OSError as error:
        output_path.unlink(missing_ok=True)
        raise AdapterError(
            "write_failed", "Could not write to the output folder."
        ) from error

    return Written(output_path, extraction.notes)


def _adapter_for(input_path: Path):
    """Return the adapter for this document, or say why there is none."""
    if not input_path.is_file():
        raise AdapterError("input_not_found", "Select an existing readable file.")

    # A protected package fails every reader generically, so it is recognised
    # from its own bytes rather than reported as an unreadable file.
    from document_worker.conversion import (
        PASSWORD_PROTECTED_MESSAGE,
        is_protected_package,
    )

    if is_protected_package(input_path):
        raise AdapterError("password_protected", PASSWORD_PROTECTED_MESSAGE)

    from document_worker.anonymization.formats import anonymization_adapter

    adapter = anonymization_adapter(input_path)
    if adapter is None:
        raise AdapterError(
            "unsupported_format", "Choose a format the anonymizer can rewrite."
        )
    return adapter


def _resolve(units: list[TextUnit], kept: Iterable[KeptDetection]) -> list[Detection]:
    """
    Turn the kept detections back into detections of this document.

    The text comes from the document rather than from the request, because the
    operators need it — Replace numbers placeholders per distinct value, Mask
    keeps a tail — and a request that could assert what a span contains could
    assert something the document does not say.

    Raises:
        AdapterError: A detection names a unit that is not there, or offsets
            outside it, or text this format does not rewrite.
    """
    by_id = {unit.id: unit for unit in units}
    resolved = []
    for item in kept:
        unit = by_id.get(item.unit_id)
        if unit is None or item.end > len(unit.text):
            raise AdapterError("document_changed", _STALE)
        if not unit.rewritable:
            raise AdapterError(
                "not_rewritable", "This text cannot be rewritten in this format."
            )
        resolved.append(
            Detection(
                unit.id,
                item.start,
                item.end,
                item.entity_type,
                1.0,
                unit.text[item.start : item.end],
            )
        )
    return resolved


def _output_path(output_directory: Path, source: Path, language: str) -> Path:
    """
    Name the copy, never taking a name that is already on disk.

    An existing file is never overwritten and the source is never written to.
    """
    stem = f"{source.stem}{_SUFFIXES[language]}"
    candidate = output_directory / f"{stem}{source.suffix}"
    counter = 2
    while candidate.exists():
        candidate = output_directory / f"{stem}-{counter}{source.suffix}"
        counter += 1
    return candidate

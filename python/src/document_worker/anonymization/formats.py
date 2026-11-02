"""
Which formats the anonymizer accepts, and which adapter handles each.

This catalog is deliberately separate from the conversion catalog in
``document_worker.formats``. Converting a format to Markdown and rewriting it
in place are different capabilities: PDF converts and cannot be rewritten with
its layout intact. Announcing a format we cannot anonymize is the worst failure
available here, because the user finds out only after handing over a file they
believed was handled. The spec records the reasoning for every exclusion.
"""

from dataclasses import dataclass
from pathlib import Path

# Formats whose text is the file itself. One adapter family, no packaging.
_TEXT_FORMATS = (
    (".txt", "Text"),
    (".text", "Text"),
    (".md", "Markdown"),
    (".markdown", "Markdown"),
    (".csv", "CSV"),
    (".tsv", "TSV"),
    (".json", "JSON"),
    (".jsonl", "JSON Lines"),
    (".xml", "XML"),
    (".html", "HTML"),
    (".htm", "HTML"),
)

# OOXML packages: a zip of XML parts, rewritten part by part.
_OOXML_FORMATS = (
    (".docx", "Word Document"),
    (".xlsx", "Excel Spreadsheet"),
    (".pptx", "PowerPoint"),
)


@dataclass(frozen=True)
class AnonymizationFormat:
    """A format the anonymizer can read and rewrite."""

    extension: str
    label: str


def supported_anonymization_formats() -> list[AnonymizationFormat]:
    """Return the catalog, extensions dotted and lowercase as in conversion."""
    return [
        AnonymizationFormat(extension, label)
        for extension, label in _TEXT_FORMATS + _OOXML_FORMATS
    ]


def anonymization_adapter(path: str | Path):
    """
    Return the adapter for ``path``, or None if the format is not supported.

    Adapter modules are imported here rather than at module scope, so listing
    the formats costs nothing and no parser is loaded until a document of that
    kind actually arrives.
    """
    extension = Path(path).suffix.lower()

    if extension in dict(_TEXT_FORMATS):
        from document_worker.anonymization import text_adapters

        return text_adapters.adapter_for(extension)

    if extension in dict(_OOXML_FORMATS):
        from document_worker.anonymization import ooxml_adapters

        return ooxml_adapters.adapter_for(extension)

    return None

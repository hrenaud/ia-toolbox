"""Format catalog and metadata for supported document types."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FormatInfo:
    """Metadata for a supported input format."""

    extension: str
    label: str
    requires_optional_component: bool


def supported_input_formats() -> list[FormatInfo]:
    """
    Return the catalog of supported input formats.

    Each format corresponds to a converter available in markitdown 0.1.6.
    Local-file converters are included; remote service and OCR-dependent
    formats are excluded.
    """
    return [
        FormatInfo(".txt", "Text", False),
        FormatInfo(".csv", "CSV", False),
        FormatInfo(".html", "HTML", False),
        FormatInfo(".json", "JSON", False),
        FormatInfo(".jsonl", "JSON Lines", False),
        FormatInfo(".epub", "EPUB", False),
        FormatInfo(".docx", "Word Document", False),
        FormatInfo(".xlsx", "Excel Spreadsheet", False),
        FormatInfo(".xls", "Excel 97-2003", False),
        FormatInfo(".pptx", "PowerPoint", False),
        FormatInfo(".pdf", "PDF", False),
        FormatInfo(".ipynb", "Jupyter Notebook", False),
        FormatInfo(".zip", "ZIP Archive", False),
    ]

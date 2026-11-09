"""
The catalog of formats the anonymizer accepts.

This list is independent of the conversion catalog. A format that converts to
Markdown is not necessarily a format we can rewrite in place: PDF converts and
cannot be rewritten. Announcing a format we cannot anonymize is the worst
failure available here, because the user learns it only after handing over a
file they believed was handled.
"""

from document_worker.anonymization.formats import (
    anonymization_adapter,
    supported_anonymization_formats,
)


class TestCatalog:
    # Extensions carry their leading dot, as in the conversion catalog, so the
    # UI can compare the two lists without normalising either.
    def test_every_entry_is_a_lowercase_dotted_extension_with_a_label(self):
        for entry in supported_anonymization_formats():
            assert entry.extension.startswith(".")
            assert entry.extension == entry.extension.lower()
            assert entry.label

    def test_extensions_are_unique(self):
        extensions = [entry.extension for entry in supported_anonymization_formats()]

        assert len(extensions) == len(set(extensions))

    # Tier A, the formats whose text is the file itself.
    def test_plain_text_and_structured_text_formats_are_offered(self):
        extensions = {entry.extension for entry in supported_anonymization_formats()}

        assert {
            ".txt",
            ".md",
            ".csv",
            ".tsv",
            ".json",
            ".jsonl",
            ".xml",
            ".html",
        } <= extensions

    # Tier B, the OOXML packages.
    def test_the_office_formats_are_offered(self):
        extensions = {entry.extension for entry in supported_anonymization_formats()}

        assert {".docx", ".xlsx", ".pptx"} <= extensions

    # PDF converts to Markdown but cannot be rewritten while preserving its
    # layout, so it is deliberately absent. The spec records the reasoning for
    # every format left out.
    def test_formats_we_cannot_rewrite_are_absent(self):
        extensions = {entry.extension for entry in supported_anonymization_formats()}

        assert extensions.isdisjoint(
            {".pdf", ".odt", ".doc", ".xls", ".ppt", ".png", ".jpg", ".epub", ".zip"}
        )


class TestDispatch:
    # The guard that makes the catalog honest: anything announced must resolve
    # to an adapter that can actually be loaded.
    def test_every_announced_format_resolves_to_an_adapter(self):
        for entry in supported_anonymization_formats():
            assert anonymization_adapter(f"name{entry.extension}") is not None

    def test_the_extension_is_matched_case_insensitively(self):
        assert anonymization_adapter("Rapport.DOCX") is not None

    def test_an_unsupported_extension_resolves_to_nothing(self):
        assert anonymization_adapter("scan.pdf") is None

    def test_a_file_without_an_extension_resolves_to_nothing(self):
        assert anonymization_adapter("LISEZMOI") is None

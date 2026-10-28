"""Document conversion using MarkItDown."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConversionResult:
    """Result of a document conversion attempt."""

    status: str  # "success" or "error"
    output_path: str | None = None
    error_code: str | None = None
    message: str | None = None


def convert_file(input_path: Path, output_directory: Path) -> ConversionResult:
    """
    Convert a document file to Markdown.

    Converts the input file to Markdown and writes it to the output directory.
    If <stem>.md already exists, uses <stem> (2).md, then (3), etc.

    Arguments:
        input_path: Absolute path to the input file.
        output_directory: Absolute path to the directory for output.

    Returns:
        ConversionResult with status, output_path (if success), or error_code and message.
    """
    # Validate inputs
    if not input_path.is_file():
        return ConversionResult(
            status="error",
            error_code="input_not_found",
            message="Select an existing readable file.",
        )

    if not output_directory.is_dir():
        return ConversionResult(
            status="error",
            error_code="invalid_output_directory",
            message="Select an existing output folder.",
        )

    # Check if format is supported
    from document_worker.formats import supported_input_formats

    supported_exts = {fmt.extension for fmt in supported_input_formats()}
    if input_path.suffix.lower() not in supported_exts:
        return ConversionResult(
            status="error",
            error_code="unsupported_format",
            message="Choose a supported file format.",
        )

    # Perform conversion (import here to preserve output isolation)
    try:
        from markitdown import MarkItDown
        from markitdown.converters import (
            CsvConverter,
            DocxConverter,
            EpubConverter,
            HtmlConverter,
            IpynbConverter,
            PdfConverter,
            PlainTextConverter,
            PptxConverter,
            XlsConverter,
            XlsxConverter,
            ZipConverter,
        )

        # Create converter with only local file converters
        converter = MarkItDown(enable_builtins=False, enable_plugins=False)

        # Register converters
        converter.register_converter(PlainTextConverter())
        converter.register_converter(CsvConverter())
        converter.register_converter(HtmlConverter())
        converter.register_converter(EpubConverter())
        converter.register_converter(DocxConverter())
        converter.register_converter(XlsConverter())
        converter.register_converter(XlsxConverter())
        converter.register_converter(PptxConverter())
        converter.register_converter(PdfConverter())
        converter.register_converter(IpynbConverter())
        converter.register_converter(ZipConverter(markitdown=converter))

        # Convert the file
        result = converter.convert_local(input_path)
        text_content = result.text_content

    except Exception:  # noqa: BLE001 - isolate each file and never expose library exceptions
        # Do not expose exception details
        return ConversionResult(
            status="error",
            error_code="processing_failed",
            message="Could not process this file. Check file and folder access, then retry.",
        )

    # Find the next available output filename
    output_path = _find_available_output_path(output_directory, input_path.stem)

    # Write the output
    try:
        with output_path.open("w", encoding="utf-8") as f:
            f.write(text_content)
    except OSError:
        # Clean up partial write
        output_path.unlink(missing_ok=True)
        return ConversionResult(
            status="error",
            error_code="write_failed",
            message="Could not write to the output folder.",
        )

    return ConversionResult(
        status="success",
        output_path=str(output_path),
    )


def _find_available_output_path(output_directory: Path, stem: str) -> Path:
    """
    Find the next available numbered filename for the given stem.

    If <stem>.md exists, tries <stem> (2).md, then (3), etc.

    Arguments:
        output_directory: Directory to create output in.
        stem: The input file stem (filename without extension).

    Returns:
        A Path object for the available output file (not yet created).
    """
    # Try the base name first
    output_path = output_directory / f"{stem}.md"
    if not output_path.exists():
        return output_path

    # Try numbered names
    counter = 2
    while True:
        output_path = output_directory / f"{stem} ({counter}).md"
        if not output_path.exists():
            return output_path
        counter += 1

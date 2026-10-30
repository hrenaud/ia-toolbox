"""Document conversion using MarkItDown."""

from dataclasses import dataclass
from pathlib import Path

PASSWORD_PROTECTED_MESSAGE = (
    "This file is protected by a password. Remove the protection in the "
    "original application, save a copy, then retry."
)

# An encrypted OOXML document is not the ZIP archive its extension promises:
# MS-OFFCRYPTO wraps the package in an OLE2 compound file holding an
# EncryptedPackage stream, whose name the directory stores as UTF-16LE.
_COMPOUND_FILE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ENCRYPTED_PACKAGE_STREAM = "EncryptedPackage".encode("utf-16-le")

# .xls is excluded on purpose: Excel 97-2003 is legitimately a compound file,
# so the magic proves nothing there and a readable workbook would be rejected.
_PACKAGE_EXTENSIONS = frozenset({".docx", ".xlsx", ".pptx"})

# Office writes the directory early: the marker sat at offset 1152 in a 35 KB
# document and 8320 in a 643 KB one, so the head read is what actually matches.
# The compound-file format allows the directory at the end too, which the tail
# read covers for a file written by some other tool. Reading two bounded windows
# keeps the check cheap on a large document.
_SNIFF_WINDOW = 64 * 1024

# Reader exceptions are matched by name so that no reader has to be imported
# here, which would break the output isolation this module depends on.
_PASSWORD_ERROR_NAMES = frozenset({"PDFPasswordIncorrect", "PDFEncryptionError"})


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

    # A protected package fails every reader generically, so it is recognised
    # from its own bytes before conversion is attempted.
    if _is_protected_package(input_path):
        return ConversionResult(
            status="error",
            error_code="password_protected",
            message=PASSWORD_PROTECTED_MESSAGE,
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

    except Exception as error:  # noqa: BLE001 - isolate each file and never expose library exceptions
        # A password failure gets its own code: "check file and folder access"
        # is wrong advice for a file that is readable but encrypted.
        if _is_password_error(error):
            return ConversionResult(
                status="error",
                error_code="password_protected",
                message=PASSWORD_PROTECTED_MESSAGE,
            )

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


def _is_protected_package(input_path: Path) -> bool:
    """
    Report whether a DOCX/XLSX/PPTX is a password-protected package.

    Only the compound-file magic together with the EncryptedPackage stream name
    is accepted as proof. A legacy .doc renamed to .docx carries the magic but
    not the stream, and must stay an ordinary unreadable file.

    Arguments:
        input_path: Absolute path to the input file.

    Returns:
        True when the file is an encrypted Office package.
    """
    if input_path.suffix.lower() not in _PACKAGE_EXTENSIONS:
        return False

    try:
        with input_path.open("rb") as handle:
            head = handle.read(_SNIFF_WINDOW)
            if not head.startswith(_COMPOUND_FILE_MAGIC):
                return False
            if _ENCRYPTED_PACKAGE_STREAM in head:
                return True
            handle.seek(max(0, input_path.stat().st_size - _SNIFF_WINDOW))
            return _ENCRYPTED_PACKAGE_STREAM in handle.read(_SNIFF_WINDOW)
    except OSError:
        return False


def _is_password_error(error: BaseException) -> bool:
    """
    Report whether a conversion failure was a reader's password rejection.

    MarkItDown wraps a converter failure in FileConversionException and keeps
    the original in ``attempts[*].exc_info``, so the reader's exception is not
    on the usual ``__cause__`` chain and both ends have to be walked.

    Arguments:
        error: The exception raised by the conversion attempt.

    Returns:
        True when a reader reported an encrypted or password-protected file.
    """
    pending: list[object] = [error]
    seen: set[int] = set()

    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))

        name = item.__name__ if isinstance(item, type) else type(item).__name__
        if name in _PASSWORD_ERROR_NAMES:
            return True

        if isinstance(item, BaseException):
            pending.extend(
                related
                for related in (item.__cause__, item.__context__)
                if related is not None
            )
            for attempt in getattr(item, "attempts", None) or ():
                pending.extend(getattr(attempt, "exc_info", None) or ())

    return False


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

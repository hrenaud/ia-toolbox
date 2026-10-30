"""
Password-protected documents must fail with their own error code.

Every reader failure previously collapsed into ``processing_failed`` with a
message about file and folder access. For a password-protected document that
advice is wrong: nothing is unreadable and no permission is missing, so the
user has no way to learn what to do. The same masking is how five formats with
missing readers stayed invisible until packaging.
"""

import io
import struct
import zipfile
from pathlib import Path

import pytest

from document_worker.conversion import convert_file

# A compound file keeps stream names as UTF-16LE in its directory entries.
COMPOUND_FILE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ENCRYPTED_PACKAGE_STREAM = "EncryptedPackage".encode("utf-16-le")
ENCRYPTION_INFO_STREAM = "EncryptionInfo".encode("utf-16-le")

OOXML_EXTENSIONS = [".docx", ".xlsx", ".pptx"]


def write_encrypted_pdf(path: Path) -> None:
    """
    Write a genuinely encrypted PDF.

    The trailer references a standard security handler whose ``/O`` and ``/U``
    values authenticate no password, so a reader trying the empty password
    fails the way it would on a real protected document. No dependency here can
    produce an encrypted PDF, so the bytes are emitted directly with computed
    cross-reference offsets.
    """
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>",
        b"<< /Filter /Standard /V 1 /R 2 /O <"
        + b"ab" * 16
        + b"> /U <"
        + b"cd" * 16
        + b"> /P -1 >>",
    ]

    buffer = io.BytesIO()
    buffer.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(buffer.tell())
        buffer.write(b"%d 0 obj\n" % number + body + b"\nendobj\n")

    start_xref = buffer.tell()
    buffer.write(b"xref\n0 %d\n" % (len(objects) + 1))
    buffer.write(b"0000000000 65535 f \n")
    for offset in offsets:
        buffer.write(b"%010d 00000 n \n" % offset)

    identifier = b"01" * 16
    buffer.write(
        b"trailer\n<< /Size %d /Root 1 0 R /Encrypt 4 0 R /ID [<%s> <%s>] >>\n"
        % (len(objects) + 1, identifier, identifier)
    )
    buffer.write(b"startxref\n%d\n%%%%EOF\n" % start_xref)
    path.write_bytes(buffer.getvalue())


def write_protected_package(path: Path, payload_size: int = 0) -> None:
    """
    Write a compound file carrying the streams MS-OFFCRYPTO mandates.

    An encrypted OOXML document is not the ZIP archive its extension promises:
    the package is wrapped in an OLE2 compound file alongside an
    ``EncryptionInfo`` descriptor. ``payload_size`` pushes the directory entries
    past a body of that size, covering the layout the format permits even though
    Office itself writes the directory near the start.
    """
    path.write_bytes(
        COMPOUND_FILE_MAGIC
        + b"\x00" * 504
        + b"\x00" * payload_size
        + ENCRYPTION_INFO_STREAM
        + b"\x00" * 64
        + ENCRYPTED_PACKAGE_STREAM
        + b"\x00" * 64
    )


def write_legacy_compound_file(path: Path) -> None:
    """Write a compound file with no encryption streams, as a renamed .doc is."""
    path.write_bytes(COMPOUND_FILE_MAGIC + b"\x00" * 1024)


def write_readable_docx(path: Path) -> None:
    """Write the smallest DOCX the reader accepts."""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>',
        )
        archive.writestr(
            "word/document.xml",
            '<?xml version="1.0"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>Titre</w:t></w:r></w:p></w:body></w:document>",
        )


def write_protected_legacy_xls(path: Path) -> None:
    """
    Write a BIFF8 workbook announcing a FilePass record.

    Legacy Excel is itself a compound file, so the detection used for the
    ZIP-based formats cannot apply here. This fixture exists to pin that
    exclusion rather than to claim the case is handled.
    """
    path.write_bytes(
        COMPOUND_FILE_MAGIC
        + b"\x00" * 504
        + struct.pack("<HH", 0x002F, 2)
        + b"\x01\x00"
        + ENCRYPTED_PACKAGE_STREAM
    )


def convert(source: Path, tmp_path: Path):
    destination = tmp_path / "out"
    destination.mkdir(exist_ok=True)
    return convert_file(source, destination), destination


class TestPasswordProtectedDetection:
    """A protected document is named as such instead of failing generically."""

    def test_encrypted_pdf_is_reported_as_password_protected(self, tmp_path):
        source = tmp_path / "protected.pdf"
        write_encrypted_pdf(source)

        result, _ = convert(source, tmp_path)

        assert result.status == "error"
        assert result.error_code == "password_protected"

    @pytest.mark.parametrize("extension", OOXML_EXTENSIONS)
    def test_protected_package_is_reported_as_password_protected(
        self, extension, tmp_path
    ):
        source = tmp_path / f"protected{extension}"
        write_protected_package(source)

        result, _ = convert(source, tmp_path)

        assert result.status == "error"
        assert result.error_code == "password_protected"

    def test_detection_survives_a_payload_before_the_directory(self, tmp_path):
        """
        The directory may follow the payload instead of preceding it.

        Word, Excel and PowerPoint all write it early, so this case covers the
        layout the format permits but those applications do not produce.
        """
        source = tmp_path / "large.docx"
        write_protected_package(source, payload_size=256 * 1024)

        result, _ = convert(source, tmp_path)

        assert result.error_code == "password_protected"


class TestPasswordProtectedDetectionLimits:
    """Detection must not claim a password where it cannot prove one."""

    def test_compound_file_without_encryption_streams_is_not_claimed(self, tmp_path):
        """A legacy .doc renamed to .docx is unreadable, not protected."""
        source = tmp_path / "renamed.docx"
        write_legacy_compound_file(source)

        result, _ = convert(source, tmp_path)

        assert result.status == "error"
        assert result.error_code == "processing_failed"

    def test_legacy_xls_is_never_claimed_as_protected(self, tmp_path):
        """Excel 97-2003 is legitimately a compound file, so the magic proves nothing."""
        source = tmp_path / "protected.xls"
        write_protected_legacy_xls(source)

        result, _ = convert(source, tmp_path)

        assert result.error_code != "password_protected"

    def test_readable_docx_still_converts(self, tmp_path):
        """The sniff must not reject the ZIP archive a real DOCX is."""
        source = tmp_path / "plain.docx"
        write_readable_docx(source)

        result, _ = convert(source, tmp_path)

        assert result.status == "success", f"{result.error_code} - {result.message}"


class TestPasswordProtectedReporting:
    """The failure leaves the document alone and says something useful."""

    def test_source_is_preserved_and_no_output_is_written(self, tmp_path):
        source = tmp_path / "protected.docx"
        write_protected_package(source)
        original = source.read_bytes()

        result, destination = convert(source, tmp_path)

        assert result.output_path is None
        assert source.read_bytes() == original
        assert list(destination.iterdir()) == []

    def test_message_is_actionable_and_leaks_nothing(self, tmp_path):
        source = tmp_path / "protected.pdf"
        write_encrypted_pdf(source)

        result, _ = convert(source, tmp_path)

        assert "password" in result.message.lower()
        assert str(source) not in result.message
        assert "Traceback" not in result.message

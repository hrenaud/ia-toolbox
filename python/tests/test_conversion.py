"""Test document conversion using the MarkItDown adapter."""

import json
from pathlib import Path

from document_worker.conversion import convert_file


class TestConversionSuccess:
    """Test successful conversions for each supported format."""

    def test_convert_plain_text(self, tmp_path):
        """Convert a plain text file to markdown."""
        source = tmp_path / "test.txt"
        source.write_text("Hello, world!\n", encoding="utf-8")

        result = convert_file(source, tmp_path)

        assert result.status == "success"
        assert result.output_path is not None
        assert result.error_code is None
        assert result.message is None

        output = Path(result.output_path)
        assert output.exists()
        assert output.suffix == ".md"
        assert "Hello, world!" in output.read_text(encoding="utf-8")
        # Source should be untouched
        assert source.read_text() == "Hello, world!\n"

    def test_convert_csv_to_markdown_table(self, tmp_path):
        """Convert a CSV file to markdown table."""
        source = tmp_path / "data.csv"
        source.write_text("Name,Age\nAlice,30\nBob,25\n", encoding="utf-8")

        result = convert_file(source, tmp_path)

        assert result.status == "success"
        output = Path(result.output_path)
        content = output.read_text(encoding="utf-8")
        assert "Name" in content
        assert "Age" in content
        assert "Alice" in content

    def test_convert_html_to_markdown(self, tmp_path):
        """Convert an HTML file to markdown."""
        source = tmp_path / "page.html"
        source.write_text(
            "<html><body><h1>Title</h1><p>Content here.</p></body></html>",
            encoding="utf-8",
        )

        result = convert_file(source, tmp_path)

        assert result.status == "success"
        output = Path(result.output_path)
        content = output.read_text(encoding="utf-8")
        assert "Title" in content or "title" in content.lower()

    def test_convert_json_to_markdown(self, tmp_path):
        """Convert a JSON file (treated as plain text initially)."""
        source = tmp_path / "data.json"
        data = {"name": "test", "value": 42}
        source.write_text(json.dumps(data), encoding="utf-8")

        result = convert_file(source, tmp_path)

        # JSON falls back to plain text converter
        assert result.status == "success"
        output = Path(result.output_path)
        assert "test" in output.read_text(encoding="utf-8")

    def test_convert_jsonl_to_markdown(self, tmp_path):
        """Convert a JSONL file (newline-delimited JSON)."""
        source = tmp_path / "data.jsonl"
        source.write_text('{"id": 1}\n{"id": 2}\n', encoding="utf-8")

        result = convert_file(source, tmp_path)

        assert result.status == "success"
        output = Path(result.output_path)
        content = output.read_text(encoding="utf-8")
        assert "id" in content.lower()

    def test_convert_markdown_file(self, tmp_path):
        """Convert a Markdown file to markdown (identity conversion)."""
        source = tmp_path / "readme.md"
        source.write_text("# Title\n\nSome **bold** text.\n", encoding="utf-8")

        result = convert_file(source, tmp_path)

        assert result.status == "success"
        assert result.output_path is not None
        output = Path(result.output_path)
        assert output.exists()
        assert output.suffix == ".md"
        content = output.read_text(encoding="utf-8")
        assert "Title" in content
        # Source should be untouched
        assert source.read_text() == "# Title\n\nSome **bold** text.\n"

    def test_output_uses_input_stem(self, tmp_path):
        """Output filename should be based on input stem with .md extension."""
        source = tmp_path / "report.txt"
        source.write_text("test", encoding="utf-8")

        result = convert_file(source, tmp_path)

        assert result.status == "success"
        output = Path(result.output_path)
        assert output.name == "report.md"

    def test_output_numbering_when_name_occupied(self, tmp_path):
        """When <stem>.md exists, use <stem> (2).md, then (3), etc."""
        source = tmp_path / "report.txt"
        source.write_text("new content", encoding="utf-8")
        existing1 = tmp_path / "report.md"
        existing1.write_text("existing", encoding="utf-8")

        result = convert_file(source, tmp_path)

        assert result.status == "success"
        output = Path(result.output_path)
        assert output.name == "report (2).md"
        assert output.read_text(encoding="utf-8") == "new content"
        # Both files should exist
        assert existing1.exists()
        assert existing1.read_text() == "existing"

    def test_output_numbering_multiple_occupied(self, tmp_path):
        """When (2) is occupied, try (3), etc."""
        source = tmp_path / "doc.txt"
        source.write_text("third", encoding="utf-8")
        (tmp_path / "doc.md").write_text("first", encoding="utf-8")
        (tmp_path / "doc (2).md").write_text("second", encoding="utf-8")

        result = convert_file(source, tmp_path)

        assert result.status == "success"
        output = Path(result.output_path)
        assert output.name == "doc (3).md"


class TestConversionErrors:
    """Test error handling in conversions."""

    def test_source_file_not_found(self, tmp_path):
        """Should error gracefully if source doesn't exist."""
        missing = tmp_path / "missing.txt"

        result = convert_file(missing, tmp_path)

        assert result.status == "error"
        assert result.error_code is not None
        assert result.message is not None
        assert result.output_path is None

    def test_output_directory_not_found(self, tmp_path):
        """Should error gracefully if output directory doesn't exist."""
        source = tmp_path / "test.txt"
        source.write_text("test", encoding="utf-8")
        missing_dir = tmp_path / "missing"

        result = convert_file(source, missing_dir)

        assert result.status == "error"
        assert result.error_code is not None

    def test_unsupported_format(self, tmp_path):
        """Should reject unsupported file formats."""
        source = tmp_path / "test.xyz"
        source.write_text("test", encoding="utf-8")

        result = convert_file(source, tmp_path)

        assert result.status == "error"
        assert result.error_code == "unsupported_format"
        # Source should be untouched
        assert source.read_text() == "test"

    def test_corrupt_file_handling(self, tmp_path):
        """Should handle corrupt files gracefully."""
        source = tmp_path / "corrupt.csv"
        # Create a file that CSV parser might struggle with
        source.write_bytes(b"\xff\xfe\x00\x00")

        result = convert_file(source, tmp_path)

        # Should either convert or error gracefully, not crash
        assert result.status in ("success", "error")
        if result.status == "error":
            assert result.error_code is not None
            assert "Traceback" not in (result.message or "")

    def test_source_file_preserved(self, tmp_path):
        """Source file should never be modified."""
        source = tmp_path / "original.txt"
        original_content = "original content"
        source.write_text(original_content, encoding="utf-8")

        convert_file(source, tmp_path)

        assert source.read_text() == original_content
        # We check it wasn't truncated or deleted
        assert source.is_file()


class TestOfficeAndPdfFormats:
    """Test Office and PDF format support in catalog."""

    def test_office_formats_are_declared(self):
        """Office formats should be in the catalog."""
        from document_worker.formats import supported_input_formats

        formats = supported_input_formats()
        extensions = {fmt.extension for fmt in formats}

        office_formats = {".docx", ".xlsx", ".xls", ".pptx"}
        assert office_formats.issubset(extensions)

    def test_pdf_format_is_declared(self):
        """PDF format should be in the catalog."""
        from document_worker.formats import supported_input_formats

        formats = supported_input_formats()
        extensions = {fmt.extension for fmt in formats}
        assert ".pdf" in extensions

    def test_epub_format_is_declared(self):
        """EPUB format should be in the catalog."""
        from document_worker.formats import supported_input_formats

        formats = supported_input_formats()
        extensions = {fmt.extension for fmt in formats}
        assert ".epub" in extensions


class TestErrorMessages:
    """Test that error messages are user-safe (no exception details)."""

    def test_error_message_is_user_safe(self, tmp_path):
        """Error messages should be user-friendly, not stack traces."""
        source = tmp_path / "missing.txt"

        result = convert_file(source, tmp_path)

        assert result.status == "error"
        # Message should not contain Python exception details
        message = result.message or ""
        assert "Traceback" not in message
        assert "Exception" not in message
        assert "<" not in message  # No stack frames

    def test_unreadable_file_error(self, tmp_path):
        """Should handle permission errors gracefully."""
        source = tmp_path / "restricted.txt"
        source.write_text("secret", encoding="utf-8")

        # Make it unreadable
        source.chmod(0o000)

        try:
            result = convert_file(source, tmp_path)
            assert result.status == "error"
            assert result.error_code is not None
        finally:
            # Cleanup: restore permissions
            source.chmod(0o644)

    def test_write_failed_read_only_directory(self, tmp_path):
        """Should handle write failures (e.g., read-only output directory)."""
        source = tmp_path / "test.txt"
        source.write_text("content", encoding="utf-8")

        # Create a read-only subdirectory to write to
        output_dir = tmp_path / "readonly"
        output_dir.mkdir()

        result = convert_file(source, output_dir)
        # Success before making read-only
        assert result.status == "success"

        # Now make directory read-only and try again with a new source file
        output_dir.chmod(0o555)
        source2 = tmp_path / "test2.txt"
        source2.write_text("content2", encoding="utf-8")

        try:
            result = convert_file(source2, output_dir)

            # Should fail with write_failed error code
            assert result.status == "error"
            assert result.error_code == "write_failed"
            assert result.output_path is None
            # Message should be user-safe
            message = result.message or ""
            assert "Traceback" not in message
            assert "OSError" not in message
            assert "Exception" not in message
            # No partial file should be left behind
            assert not (output_dir / "test2.md").exists()
        finally:
            # Cleanup: restore permissions so temp directory can be cleaned
            output_dir.chmod(0o755)

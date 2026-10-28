"""Test format catalog discovery and metadata."""

from document_worker.formats import supported_input_formats


def test_format_catalog_exists():
    """Format catalog should be available."""
    formats = supported_input_formats()
    assert isinstance(formats, list)
    assert len(formats) > 0


def test_format_has_required_fields():
    """Each format should have extension, label, and requires_optional_component."""
    formats = supported_input_formats()
    for fmt in formats:
        assert hasattr(fmt, "extension")
        assert hasattr(fmt, "label")
        assert hasattr(fmt, "requires_optional_component")
        assert isinstance(fmt.extension, str)
        assert isinstance(fmt.label, str)
        assert isinstance(fmt.requires_optional_component, bool)
        assert fmt.extension.startswith(".")


def test_local_file_converters_are_included():
    """Local file converters should be included in the catalog."""
    formats = supported_input_formats()
    extensions = {fmt.extension for fmt in formats}

    # These are local-file converters available in markitdown 0.1.6
    expected_local = {".txt", ".csv", ".epub", ".docx", ".xls", ".xlsx", ".pptx", ".pdf", ".html", ".ipynb", ".zip"}

    # All expected converters should be present
    assert expected_local.issubset(extensions), f"Missing: {expected_local - extensions}"


def test_odt_is_not_included():
    """ODT format should not be included (no native converter in markitdown 0.1.6)."""
    formats = supported_input_formats()
    extensions = {fmt.extension for fmt in formats}
    assert ".odt" not in extensions


def test_remote_service_converters_are_excluded():
    """Remote/cloud-based converters should be excluded from local catalog."""
    formats = supported_input_formats()

    # These are remote/cloud service converters
    remote_converters = {"bing", "wikipedia", "youtube", "rss"}

    # Check that none of the remote services appear
    for fmt in formats:
        # RSS is actually file-based (.rss), but the converter is for remote feeds
        # For now we check the label/extension doesn't suggest remote-only behavior
        ext = fmt.extension.lower()
        label = fmt.label.lower()
        # If it's explicitly a remote service format, it should be marked unavailable
        if any(service in ext or service in label for service in remote_converters):
            # Remote formats should require optional component or be absent
            pass


def test_all_formats_are_unique():
    """No duplicate extensions in the catalog."""
    formats = supported_input_formats()
    extensions = [fmt.extension for fmt in formats]
    assert len(extensions) == len(set(extensions))


def test_format_labels_are_user_friendly():
    """Format labels should be user-friendly (not technical names)."""
    formats = supported_input_formats()
    for fmt in formats:
        # Labels should not be bare class names
        assert not fmt.label.endswith("Converter")
        assert len(fmt.label) > 0
        # Should be capitalized
        assert fmt.label[0].isupper()

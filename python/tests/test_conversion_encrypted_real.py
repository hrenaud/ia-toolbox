"""
Detection checked against documents Word, Excel and PowerPoint actually wrote.

``test_conversion_encrypted.py`` builds its compound files by hand, so it can
only prove that the detection agrees with the author's reading of MS-OFFCRYPTO.
That is the weaker claim: a hand-built fixture and the code that reads it come
from the same mental model, so both can be wrong together. The files in
``fixtures/`` were saved by the real applications.

A fixture may never be skipped away. If the directory is incomplete the suite
fails rather than passing quietly, because a skip is how a comparable defect
stayed invisible for a whole task cycle.
"""

from pathlib import Path

import pytest

from document_worker.conversion import convert_file

FIXTURES = Path(__file__).parent / "fixtures"

# Every OOXML format the detection claims to cover must be represented here.
PROTECTED_FIXTURES = [
    "password-protected.docx",
    "password-protected.xlsx",
    "password-protected.pptx",
]


def test_every_protected_fixture_is_present():
    """The guarantee is the files themselves; a missing one is a failure."""
    missing = [name for name in PROTECTED_FIXTURES if not (FIXTURES / name).is_file()]

    assert missing == []


@pytest.mark.parametrize("name", PROTECTED_FIXTURES)
def test_real_protected_document_is_reported_as_password_protected(name, tmp_path):
    source = FIXTURES / name

    result = convert_file(source, tmp_path)

    assert result.status == "error", f"{name} converted unexpectedly"
    assert result.error_code == "password_protected"
    assert result.output_path is None
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("name", PROTECTED_FIXTURES)
def test_real_protected_document_is_an_encrypted_package(name):
    """
    Pin what each fixture is, so a replacement cannot weaken the suite.

    A document merely locked against editing stays an ordinary ZIP archive and
    converts correctly; swapping one in here would leave the parametrised cases
    above testing nothing. The first .xlsx offered for this suite was exactly
    that file.
    """
    head = (FIXTURES / name).read_bytes()[:8]

    assert head == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1", (
        f"{name} is not a compound file, so it is not encrypted"
    )

"""
What the frozen worker must carry.

PyInstaller finds imports; it does not find data files a library loads by name
at runtime. A spaCy model is a *package of data*, and presidio builds its
recognizer registry by walking modules, so neither survives freezing on import
analysis alone. The failure mode is the worst one available: the binary starts,
answers ``list_anonymization_formats``, and dies on the first ``analyze`` with
no message, because the worker redirects its own stderr.

So the spec file is asserted against the source of truth it has to agree with —
``detection._MODELS`` — rather than against a copy of the list kept here.
"""

from pathlib import Path

import pytest

from document_worker.anonymization.detection import _MODELS

SPEC = Path(__file__).resolve().parents[1] / "packaging" / "worker.spec"


@pytest.fixture(scope="module")
def spec_source() -> str:
    return SPEC.read_text(encoding="utf-8")


@pytest.mark.parametrize("model", sorted(set(_MODELS.values())))
def test_every_detection_model_is_collected(spec_source: str, model: str):
    """A model the detector loads by name must be packaged by that name."""
    assert model in spec_source


@pytest.mark.parametrize("package", ["spacy", "presidio_analyzer"])
def test_the_detection_libraries_are_collected(spec_source: str, package: str):
    """spaCy loads data by path and presidio discovers recognizers by module."""
    assert f'"{package}"' in spec_source

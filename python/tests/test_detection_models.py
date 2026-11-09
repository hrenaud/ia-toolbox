"""
The spaCy models the detection tests need must be installed, not assumed.

A model-dependent test that skips when no model is present is not a gate: it
reports green on an environment where detection has never run. These two
assertions are what make the detection suite's results mean something, so they
fail loudly rather than skipping.

The models are pinned in the ``dev`` dependency group of pyproject.toml, which
``uv sync --locked`` installs in CI and ``uv run pytest`` installs locally. The
small models are deliberate: they are what the suite asserts _plumbing_
against — entity types, offsets, overlap resolution. Recall figures belong to a
larger model and are measured, not asserted, because a recall threshold in a
test turns a model upgrade into a red build.
"""

import pytest
import spacy

REQUIRED_MODELS = ("fr_core_news_sm", "en_core_web_sm")


@pytest.mark.parametrize("name", REQUIRED_MODELS)
def test_required_model_is_installed(name: str):
    """Both languages must be available before any detection test runs."""
    assert name in spacy.util.get_installed_models()


@pytest.mark.parametrize("name", REQUIRED_MODELS)
def test_required_model_loads(name: str):
    """Installed is not enough: a truncated download imports and then fails."""
    assert spacy.load(name).lang in ("fr", "en")


def test_absence_is_detectable():
    """Guard the guard: the check must be able to fail."""
    assert "xx_model_that_does_not_exist" not in spacy.util.get_installed_models()

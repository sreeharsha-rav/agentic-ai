"""Unit tests for `nlp/keywords.py`.

New relative to the original (which tested keyword extraction only
indirectly through `context_builder`/`document_aligner`) -- since this
scaffold factors YAKE usage into one shared module, it earns direct unit
tests: graceful degradation when YAKE is unavailable, empty input handling,
and top-N/ngram-size respecting the configured parameters.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="nlp/keywords.py not yet implemented")
def test_extract_returns_empty_list_for_empty_text():
    ...


@pytest.mark.skip(reason="nlp/keywords.py not yet implemented")
def test_degrades_to_empty_list_when_yake_unavailable():
    ...

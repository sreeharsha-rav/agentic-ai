"""Tests DocumentAligner's scoring helpers as staticmethods, called on the
class itself -- no instance is ever constructed, so sentence-transformers is
never loaded.
"""

from __future__ import annotations

import pytest

from meeting_pipeline.document_aligner import DocumentAligner


# -- _keyword_jaccard ---------------------------------------------------


def test_keyword_jaccard_empty_inputs():
    assert DocumentAligner._keyword_jaccard([], ["a", "b"]) == 0.0
    assert DocumentAligner._keyword_jaccard(["a"], []) == 0.0
    assert DocumentAligner._keyword_jaccard([], []) == 0.0


def test_keyword_jaccard_identical():
    assert DocumentAligner._keyword_jaccard(["a", "b"], ["a", "b"]) == 1.0


def test_keyword_jaccard_disjoint():
    assert DocumentAligner._keyword_jaccard(["a", "b"], ["c", "d"]) == 0.0


def test_keyword_jaccard_partial_overlap():
    assert DocumentAligner._keyword_jaccard(["a", "b"], ["b", "c"]) == pytest.approx(1 / 3)


# -- _ocr_overlap_score ---------------------------------------------------


def test_ocr_overlap_empty_chunk_text():
    assert DocumentAligner._ocr_overlap_score({"titles": ["architecture"]}, [], "") == 0.0


def test_ocr_overlap_chunk_with_no_qualifying_tokens():
    # "an", "on", "it" are all < 3 chars -- token_set() extracts nothing.
    assert DocumentAligner._ocr_overlap_score(None, [], "an on it") == 0.0


def test_ocr_overlap_full_title_containment_gets_boosted():
    hierarchy = {"titles": ["architecture diagram"], "content": []}
    chunk_text = "architecture diagram overview details more text here"
    score = DocumentAligner._ocr_overlap_score(hierarchy, [], chunk_text)
    assert score == pytest.approx(0.90)


def test_ocr_overlap_title_below_containment_threshold_does_not_boost():
    hierarchy = {"titles": ["architecture diagram"], "content": []}
    # Only "architecture" appears in the chunk, "diagram" does not -> 0.5
    # overlap, below the default 0.60 title_containment_threshold.
    chunk_text = "architecture overview details more text here"
    score = DocumentAligner._ocr_overlap_score(hierarchy, [], chunk_text)
    assert score == 0.0


def test_ocr_overlap_content_forward_and_backward_ratio():
    visual_texts = ["cache layer redis pubsub"]
    chunk_text = "cache layer only"
    score = DocumentAligner._ocr_overlap_score(None, visual_texts, chunk_text)
    # forward = |{cache,layer}| / 4 = 0.5 ; backward = |{cache,layer}| / 3 = 0.667
    assert score == pytest.approx(2 / 3, abs=1e-6)


def test_ocr_overlap_capped_at_one():
    hierarchy = {"titles": ["architecture diagram"], "content": []}
    chunk_text = "architecture diagram overview"
    # An inflated boost (> 1.0) must still be clamped by the final min(...).
    score = DocumentAligner._ocr_overlap_score(
        hierarchy, [], chunk_text, title_containment_threshold=0.60, title_containment_boost=2.0
    )
    assert score == 1.0


def test_ocr_overlap_tolerates_none_visual_hierarchy():
    score = DocumentAligner._ocr_overlap_score(None, ["some text here"], "some text here again")
    assert score > 0.0


def test_ocr_overlap_skips_short_visual_lines():
    # Both visual lines are < 5 chars and must be skipped entirely.
    score = DocumentAligner._ocr_overlap_score(None, ["hi", "ok"], "completely unrelated chunk text")
    assert score == 0.0

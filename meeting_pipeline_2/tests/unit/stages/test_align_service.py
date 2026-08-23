"""Unit tests for `stages/align/` (scoring / ingestion / service).

Port reference: `../../../meeting_pipeline/tests/test_scoring.py` and
`test_document_chunking.py`. `scoring.py`'s functions are pure and testable
with plain strings/lists -- no model loading required. Each `ingestion/*.py`
ingester is testable against a small real file of its format (see
tests/fixtures/), independent of the embedding/scoring logic in `service.py`.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="stages/align/scoring.py not yet implemented")
def test_title_containment_dominates_ocr_overlap_score():
    ...


@pytest.mark.skip(reason="stages/align/scoring.py not yet implemented")
def test_keyword_jaccard_is_zero_for_disjoint_sets():
    ...


@pytest.mark.skip(reason="stages/align/ingestion/text_ingester.py not yet implemented")
def test_markdown_ingestion_prepends_header_breadcrumb():
    ...


@pytest.mark.skip(reason="stages/align/service.py not yet implemented")
def test_stage2_falls_back_to_top_stage1_candidate_when_none_promoted():
    ...

"""Contract test for Step 5's final artifact schema, run against small
committed fixtures. Needs the real all-MiniLM-L6-v2 embedding model, so it's
gated behind MEETING_PIPELINE_RUN_SLOW=1 and never runs by default.
"""

from __future__ import annotations

import json
import os

import pytest

from meeting_pipeline.config import OCRConfig
from meeting_pipeline.document_aligner import DocumentAligner

pytestmark = [pytest.mark.slow, pytest.mark.integration]

requires_slow = pytest.mark.skipif(
    os.environ.get("MEETING_PIPELINE_RUN_SLOW") != "1",
    reason="set MEETING_PIPELINE_RUN_SLOW=1 to run (downloads the sentence-transformers model on first use)",
)

EXPECTED_ALIGNED_KEYS = {
    "topic_id",
    "start_time",
    "end_time",
    "duration_sec",
    "speakers",
    "transcript",
    "primary_frame",
    "has_document_alignment",
    "primary_linked_document",
    "highest_confidence_score",
    "sections_matched",
    "all_high_confidence_documents",
}


@requires_slow
def test_document_alignment_against_fixtures(tmp_path, fixtures_dir):
    context_path = fixtures_dir / "meeting_context.sample.json"
    docs_dir = fixtures_dir / "docs"

    aligner = DocumentAligner(output_dir=str(tmp_path), ocr_config=OCRConfig(enabled=False))
    aligned_path = aligner.run(str(context_path), str(docs_dir))

    assert (tmp_path / "aligned_context.json").exists()
    assert (tmp_path / "aligned_context_intermediate_detailed.json").exists()

    with open(aligned_path, encoding="utf-8") as f:
        aligned = json.load(f)

    for entry in aligned:
        assert set(entry.keys()) == EXPECTED_ALIGNED_KEYS

    by_id = {e["topic_id"]: e for e in aligned}

    # topic_000 discusses Redis caching / API gateway -- should align with
    # sample_reference.md's "System Architecture" section.
    assert by_id["topic_000"]["has_document_alignment"] is True
    assert by_id["topic_000"]["primary_linked_document"] == "sample_reference.md"
    assert by_id["topic_000"]["highest_confidence_score"] > 0

    # topic_001 discusses lunch orders and holiday scheduling -- unrelated
    # to the reference document, must not be aligned.
    assert by_id["topic_001"]["has_document_alignment"] is False
    assert by_id["topic_001"]["primary_linked_document"] is None

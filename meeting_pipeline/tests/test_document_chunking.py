"""Tests DocumentAligner._ingest_text as a staticmethod against tmp_path
files. Chosen over _ingest_pdf/_ingest_docx/_ingest_pptx for the default
test tier because it needs no third-party library at all (no fitz/docx/pptx),
just the stdlib + text_cleaning.normalize_whitespace.
"""

from __future__ import annotations

from meeting_pipeline.document_aligner import DocumentAligner

MARKDOWN_WITH_HEADERS = """\
# Architecture

This is the first block of content under architecture heading which is long enough.

## Caching

This second block explains caching strategy and is also sufficiently long for the gate.

### Redis

Tiny.

Another block after a tiny one, again long enough content to pass the twenty five character gate here.
"""


def test_ingest_text_breadcrumbs_and_header_hierarchy(tmp_path):
    path = tmp_path / "doc.md"
    path.write_text(MARKDOWN_WITH_HEADERS, encoding="utf-8")

    chunks = DocumentAligner._ingest_text(path, min_chars=25)

    # The two markdown header lines themselves ("# Architecture", "## Caching",
    # "### Redis") and the standalone "Tiny." paragraph are all <= 25 chars
    # and must be dropped as their own blocks -- leaving exactly 3 kept chunks.
    assert len(chunks) == 3

    assert chunks[0]["section_hierarchy"] == "Architecture"
    assert chunks[0]["text"].startswith("[Architecture]\n")
    assert "first block of content" in chunks[0]["text"]

    assert chunks[1]["section_hierarchy"] == "Architecture > Caching"
    assert chunks[1]["text"].startswith("[Architecture > Caching]\n")

    # h3 accumulates on top of h1/h2; this is also the file's final,
    # unterminated block (no trailing blank line after it) -- must still be
    # flushed after the loop ends.
    assert chunks[2]["section_hierarchy"] == "Architecture > Caching > Redis"
    assert "Another block after a tiny one" in chunks[2]["text"]

    # chunk_id counter is 0-based and only increments on kept blocks -- no
    # gaps despite 3 too-short blocks being skipped in between.
    assert [c["chunk_id"] for c in chunks] == ["doc_block_0", "doc_block_1", "doc_block_2"]
    # page_or_slide is 1-based.
    assert [c["page_or_slide"] for c in chunks] == [1, 2, 3]
    assert all(c["source"] == "doc.md" for c in chunks)


def test_ingest_text_no_headers_falls_back_to_stem(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text(
        "Just a plain paragraph without any markdown headers present here at all.\n",
        encoding="utf-8",
    )
    chunks = DocumentAligner._ingest_text(path, min_chars=25)
    assert len(chunks) == 1
    assert chunks[0]["section_hierarchy"] == "notes"
    assert chunks[0]["text"].startswith("[notes]\n")


def test_ingest_text_respects_min_chars_threshold(tmp_path):
    path = tmp_path / "short.md"
    path.write_text("Too short.\n", encoding="utf-8")
    assert DocumentAligner._ingest_text(path, min_chars=25) == []


def test_ingest_text_empty_file(tmp_path):
    path = tmp_path / "empty.md"
    path.write_text("", encoding="utf-8")
    assert DocumentAligner._ingest_text(path, min_chars=25) == []

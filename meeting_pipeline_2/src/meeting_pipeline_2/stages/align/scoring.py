"""Pure scoring-signal functions for document alignment: keyword Jaccard and
OCR text overlap (with title-containment boost).

Port reference: `_keyword_jaccard()` and `_ocr_overlap_score()` (both already
`@staticmethod`s with no instance state) in
`meeting_pipeline/document_aligner.py`. Kept as free functions here for the
same reason the original made them static: they're pure functions of their
arguments, directly unit-testable with plain strings/lists, no
`DocumentAligner` instance (and therefore no `sentence-transformers` model
load) required to exercise them.

The semantic-cosine signal is NOT here -- it depends on the injected
`EmbeddingProvider` and lives in `service.py`, which is the orchestration
layer that actually calls `.encode()`.
"""

from __future__ import annotations


def keyword_jaccard(keywords_a: list[str], keywords_b: list[str]) -> float:
    """Jaccard similarity between two keyword sets.

    TODO: port from `document_aligner.py::_keyword_jaccard()`.
    """
    raise NotImplementedError


def ocr_overlap_score(
    visual_titles: list[str],
    visual_content: list[str],
    chunk_text: str,
    *,
    title_containment_threshold: float,
    title_containment_boost: float,
) -> float:
    """Visual-to-document match score: title containment (weighted heavily)
    plus general content token overlap.

    TODO: port from `document_aligner.py::_ocr_overlap_score()`, using
    `text.cleaning.token_set()` for tokenization.
    """
    raise NotImplementedError


def composite_score(
    semantic: float,
    ocr_overlap: float,
    keyword_overlap: float,
    *,
    ocr_boost_weight: float,
    keyword_boost_weight: float,
) -> float:
    """``min(semantic + ocr_boost_weight*ocr_overlap + keyword_boost_weight*keyword_overlap, 1.0)``.

    TODO: port the inline formula repeated at both the document-level and
    chunk-level scoring sites in `document_aligner.py::align()` -- factored
    into one function here since it's the exact same formula both times.
    """
    raise NotImplementedError

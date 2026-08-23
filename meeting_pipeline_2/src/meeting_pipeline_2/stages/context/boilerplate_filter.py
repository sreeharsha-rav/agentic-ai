"""Meeting-wide OCR boilerplate detection: identifies static UI chrome
(recurring participant names, persistent app title bars) by document
frequency across all of a meeting's OCR'd frames, without hardcoding any
specific string.

Port reference: the boilerplate-token computation + `_clean_and_dedup()`
closure in `meeting_pipeline/context_builder.py::build_matchable_context()`.
Pulled out into its own module because "detect and strip recurring noise" is
a self-contained algorithm over token frequency + Jaccard similarity, testable
with plain string lists -- no OCR engine or video required.
"""

from __future__ import annotations


def find_boilerplate_tokens(
    frame_ocr_tokens: dict[str, set[str]],
    *,
    boilerplate_document_frequency: float,
    min_frames_for_boilerplate: int,
) -> set[str]:
    """Any token appearing on more than `boilerplate_document_frequency` of
    all OCR'd frames is treated as static UI chrome.

    TODO: port from the document-frequency loop in
    `context_builder.py::build_matchable_context()`.
    """
    raise NotImplementedError


def clean_and_dedup(
    text_list: list[str],
    *,
    boilerplate_tokens: set[str],
    dedup_jaccard_threshold: float,
) -> list[str]:
    """Strip boilerplate tokens, drop text that fails the meaningful-text
    quality gate, then drop near-duplicates (Jaccard token-set similarity)
    within the list.

    TODO: port from the `_clean_and_dedup()` closure in
    `context_builder.py::build_matchable_context()`. Uses
    `text.cleaning.is_meaningful_text()` and `text.cleaning.token_set()`.
    """
    raise NotImplementedError

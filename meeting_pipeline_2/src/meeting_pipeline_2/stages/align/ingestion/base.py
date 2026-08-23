"""Shared helpers for document ingesters.

Port reference: the `min_chars` chunk-length gating pattern repeated across
every `_ingest_*` method in `meeting_pipeline/document_aligner.py`. Factored
here since every ingester needs "keep this chunk only if its text exceeds a
minimum length" -- a good candidate for one shared helper instead of
duplicating the check five times.
"""

from __future__ import annotations

from ....core.models import DocumentChunk


def keep_if_long_enough(chunk: DocumentChunk, min_chars: int) -> DocumentChunk | None:
    """Return `chunk` if its text exceeds `min_chars`, else `None`.

    TODO: port the `len(text) > min_chars` gating used throughout
    `document_aligner.py`'s `_ingest_*` methods.
    """
    raise NotImplementedError

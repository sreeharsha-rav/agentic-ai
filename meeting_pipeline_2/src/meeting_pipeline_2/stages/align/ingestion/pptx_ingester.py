"""`.pptx` reference document ingestion: one chunk per slide.

Port reference: `meeting_pipeline/document_aligner.py::_ingest_pptx()`.
Import `pptx` (python-pptx) lazily inside `ingest()`, and -- uniquely among
the ingesters -- catch `ImportError` there specifically and return `[]`
with a warning log rather than propagating, since python-pptx is the one
ingestion dependency treated as fully optional in the original.
"""

from __future__ import annotations

from pathlib import Path

from ....core.interfaces import DocumentIngester
from ....core.models import DocumentChunk


class PptxIngester(DocumentIngester):
    """TODO: port from `document_aligner.py::_ingest_pptx()`, including the
    soft-fail-on-missing-python-pptx behavior."""

    def __init__(self, *, min_chunk_chars: int = 20) -> None:
        self.min_chunk_chars = min_chunk_chars

    def ingest(self, path: Path) -> list[DocumentChunk]:
        raise NotImplementedError

"""`.md`/`.txt` reference document ingestion: blank-line-delimited blocks
with `#`/`##`/`###` header-breadcrumb tracking.

Port reference: `meeting_pipeline/document_aligner.py::_ingest_text()` in
full, including the header-hierarchy state machine that prepends a
`[H1 > H2 > H3]` breadcrumb to every child block.
"""

from __future__ import annotations

from pathlib import Path

from ....core.interfaces import DocumentIngester
from ....core.models import DocumentChunk


class TextIngester(DocumentIngester):
    """TODO: port from `document_aligner.py::_ingest_text()`."""

    def __init__(self, *, min_chunk_chars: int = 25) -> None:
        self.min_chunk_chars = min_chunk_chars

    def ingest(self, path: Path) -> list[DocumentChunk]:
        raise NotImplementedError

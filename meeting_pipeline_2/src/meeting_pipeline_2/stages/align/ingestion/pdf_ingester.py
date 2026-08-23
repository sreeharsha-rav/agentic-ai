"""`.pdf` reference document ingestion: one chunk per page.

Port reference: `meeting_pipeline/document_aligner.py::_ingest_pdf()`.
Import `fitz` (PyMuPDF) lazily inside `ingest()`.
"""

from __future__ import annotations

from pathlib import Path

from ....core.interfaces import DocumentIngester
from ....core.models import DocumentChunk


class PDFIngester(DocumentIngester):
    """TODO: port from `document_aligner.py::_ingest_pdf()` -- open with
    `fitz.open(str(path))`, one `DocumentChunk` per page via
    `page.get_text()`, normalized via `text.cleaning.normalize_whitespace()`.
    """

    def __init__(self, *, min_chunk_chars: int = 30) -> None:
        self.min_chunk_chars = min_chunk_chars

    def ingest(self, path: Path) -> list[DocumentChunk]:
        raise NotImplementedError

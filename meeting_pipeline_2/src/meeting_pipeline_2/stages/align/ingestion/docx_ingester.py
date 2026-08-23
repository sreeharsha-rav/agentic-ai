"""`.docx` reference document ingestion: paragraph groups split on blank
paragraphs.

Port reference: `meeting_pipeline/document_aligner.py::_ingest_docx()`.
Import `docx` (python-docx) lazily inside `ingest()`. Note the original's
documented quirk: only the mid-document flush (on a blank paragraph)
enforces `min_chunk_chars`; the final end-of-document flush does not --
preserve that as-is rather than "fixing" it, per that method's own comment.
"""

from __future__ import annotations

from pathlib import Path

from ....core.interfaces import DocumentIngester
from ....core.models import DocumentChunk


class DocxIngester(DocumentIngester):
    """TODO: port from `document_aligner.py::_ingest_docx()`."""

    def __init__(self, *, min_chunk_chars: int = 30) -> None:
        self.min_chunk_chars = min_chunk_chars

    def ingest(self, path: Path) -> list[DocumentChunk]:
        raise NotImplementedError

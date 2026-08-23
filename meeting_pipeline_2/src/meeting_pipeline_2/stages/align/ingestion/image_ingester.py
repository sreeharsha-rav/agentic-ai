"""Image (`.png`/`.jpg`/`.jpeg`) reference document ingestion via OCR.

Port reference: `meeting_pipeline/document_aligner.py::_ingest_image()`.
Reuses `stages.context.ocr.engine.OCREngine` -- the same OCR implementation
used for video keyframes in Step 4, so an image reference document (a
diagram, an exported slide, a whiteboard photo) is treated identically to a
video frame.
"""

from __future__ import annotations

from pathlib import Path

from ....core.interfaces import DocumentIngester, OCRBackend
from ....core.models import DocumentChunk


class ImageIngester(DocumentIngester):
    """TODO: port from `document_aligner.py::_ingest_image()` -- OCR via the
    injected `OCRBackend`, clean via `text.cleaning.clean_ocr_text()`, keep
    as one chunk if the cleaned text exceeds `min_chunk_chars`.
    """

    def __init__(self, ocr_backend: OCRBackend, *, min_chunk_chars: int = 20) -> None:
        self._ocr_backend = ocr_backend
        self.min_chunk_chars = min_chunk_chars

    def ingest(self, path: Path) -> list[DocumentChunk]:
        raise NotImplementedError

"""Interfaces (ports) that decouple orchestration and stages from concrete
implementations.

Two kinds of interface live here:

1. **Stage interfaces** (`Transcriber`, `FrameExtractor`, `ContextBuilder`,
   `DocumentAligner`) -- what `pipeline/orchestrator.py` depends on. It
   never imports a stage's concrete class from `stages/`; it type-hints
   against these `Protocol`s instead. This is what makes the orchestrator
   testable with fake stages and lets a stage's internals be freely
   restructured.
2. **Shared-infra interfaces** (`EmbeddingProvider`, `OCRBackend`,
   `KeywordExtractor`, `DocumentIngester`) -- what stages depend on instead
   of importing (e.g.) `sentence_transformers` directly. This is the
   extension point for swapping a backend/model/format without touching
   the stage logic that uses it (see docs/architecture.md's extension-points
   table).

`typing.Protocol` is used rather than `abc.ABC` so real implementations
don't need to explicitly subclass anything -- structural typing keeps
`stages/` decoupled from `core/` at runtime, not just at the type level.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from .models import AlignedTopic, ArtifactPaths, DocumentChunk, SpatialOCRResult, Topic


# ---------------------------------------------------------------------------
# Stage interfaces -- one per pipeline stage
# ---------------------------------------------------------------------------


@runtime_checkable
class Transcriber(Protocol):
    """Step 0. Implemented by `stages/transcribe/service.py`."""

    def run(self, video_path: Path, paths: ArtifactPaths) -> Path:
        """Extract audio, transcribe it, write a VTT file. Returns its path."""
        ...


@runtime_checkable
class FrameExtractor(Protocol):
    """Steps 1-3. Implemented by `stages/frames/service.py`."""

    def run(self, video_path: Path, transcript_path: Path, paths: ArtifactPaths) -> Path:
        """Extract + dedup keyframes. Returns the frame log's path."""
        ...


@runtime_checkable
class ContextBuilder(Protocol):
    """Step 4. Implemented by `stages/context/service.py`."""

    def run(self, frame_log_path: Path, frames_dir: Path, paths: ArtifactPaths) -> list[Topic]:
        """OCR keyframes, cluster segments into topics, return the topics."""
        ...


@runtime_checkable
class DocumentAligner(Protocol):
    """Step 5. Implemented by `stages/align/service.py`."""

    def run(self, topics: list[Topic], documents: list[Path], paths: ArtifactPaths) -> list[AlignedTopic]:
        """Ingest reference documents, align topics against them."""
        ...


# ---------------------------------------------------------------------------
# Shared-infra interfaces -- what stages depend on instead of a concrete lib
# ---------------------------------------------------------------------------


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Wraps whatever embedding model/service is configured.

    `context/` (optional, for topic-boundary drift) and `align/` (required,
    for semantic scoring) both depend on this instead of constructing a
    `SentenceTransformer` themselves -- see `nlp/embeddings.py` for the
    default local implementation.
    """

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Return one normalized embedding vector per input text."""
        ...


@runtime_checkable
class KeywordExtractor(Protocol):
    """Wraps whatever keyword-extraction method is configured (default: YAKE).

    See `nlp/keywords.py`.
    """

    def extract(self, text: str) -> list[str]:
        ...


@runtime_checkable
class OCRBackend(Protocol):
    """One OCR engine implementation (RapidOCR/PaddleOCR/EasyOCR/Tesseract).

    Implemented once per backend under `stages/context/ocr/backends/`, tried
    in priority order by `stages/context/ocr/engine.py`. Adding a 5th backend
    means adding one new file that satisfies this protocol -- see
    docs/architecture.md.
    """

    def extract_spatial(self, image_path: Path) -> SpatialOCRResult:
        """Return OCR text decomposed into titles/content/details, if this
        backend supports bounding-box output -- else flat text in `content`.
        """
        ...


@runtime_checkable
class DocumentIngester(Protocol):
    """One reference-document format ingester (.pdf/.docx/.pptx/.md/.txt/image).

    Implemented once per format under `stages/align/ingestion/`. Adding a new
    supported format means adding one new file that satisfies this protocol
    and registering its extension in `stages/align/service.py`.
    """

    def ingest(self, path: Path) -> list[DocumentChunk]:
        ...

"""`CompositeDocumentAligner`: implements `core.interfaces.DocumentAligner`.

Port reference: `meeting_pipeline/document_aligner.py::DocumentAligner`,
specifically `ingest_documents()` + `align()` (two-stage: document-level then
section-level scoring) + `save()`. Orchestrates the `ingestion/` dispatch
table, `scoring.py`'s pure signal functions, and the shared
`nlp.embeddings`/`nlp.keywords` providers.
"""

from __future__ import annotations

from pathlib import Path

from ...config.schema import AlignmentConfig
from ...core.interfaces import DocumentAligner, EmbeddingProvider, KeywordExtractor, OCRBackend
from ...core.models import AlignedTopic, ArtifactPaths, Topic
from .ingestion.docx_ingester import DocxIngester
from .ingestion.image_ingester import ImageIngester
from .ingestion.pdf_ingester import PDFIngester
from .ingestion.pptx_ingester import PptxIngester
from .ingestion.text_ingester import TextIngester

_INGESTER_BY_EXTENSION = {
    ".pdf": PDFIngester,
    ".docx": DocxIngester,
    ".pptx": PptxIngester,
    ".md": TextIngester,
    ".txt": TextIngester,
    ".png": ImageIngester,
    ".jpg": ImageIngester,
    ".jpeg": ImageIngester,
}


class CompositeDocumentAligner(DocumentAligner):
    """Default `DocumentAligner` implementation: two-stage
    (document-level -> section-level) composite scoring.

    TODO: port the `run()` body from `DocumentAligner.run()`:
      1. Ingest every document by dispatching on extension via
         `_INGESTER_BY_EXTENSION`; build per-document profiles (title +
         headers + first ~3000 chars) alongside the full chunk list.
      2. Batch-embed all document profiles and all topic `searchable_query`
         strings via `self._embeddings`; compute the topic x document
         similarity matrix.
      3. Stage 1: per topic, score every document via
         `scoring.composite_score(semantic, ocr_overlap, keyword_overlap, ...)`;
         keep candidates >= `similarity_threshold`; promote candidates >=
         `stage1_promote_threshold` (or fall back to the single top
         candidate if none qualify).
      4. Stage 2: per promoted document, embed its chunks, score each the
         same way, track the best chunk score; combine with the Stage 1
         score via the configured weights; keep as a confirmed
         `DocumentMatch` if the combined score clears
         `high_confidence_threshold`.
      5. Return `AlignedTopic` objects and write both
         `aligned_context_intermediate_detailed.json` and
         `aligned_context.json` via `storage.json_store`.
    """

    def __init__(
        self,
        config: AlignmentConfig,
        *,
        embedding_provider: EmbeddingProvider,
        keyword_extractor: KeywordExtractor,
        ocr_backend: OCRBackend,
    ) -> None:
        self.config = config
        self._embeddings = embedding_provider
        self._keywords = keyword_extractor
        self._ocr_backend = ocr_backend

    def run(self, topics: list[Topic], documents: list[Path], paths: ArtifactPaths) -> list[AlignedTopic]:
        raise NotImplementedError

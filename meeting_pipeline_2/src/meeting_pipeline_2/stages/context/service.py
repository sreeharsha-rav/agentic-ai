"""`DefaultContextBuilder`: implements `core.interfaces.ContextBuilder`.

Port reference: `meeting_pipeline/context_builder.py::MeetingContextBuilder`,
specifically `run()` (= `build_frame_aligned_timeline()` +
`build_topics()` + `build_matchable_context()` + `save()`). This service
orchestrates: `ocr.engine.OCREngine` (this stage's own OCR cache),
`topic_clustering.build_topics()`, `boilerplate_filter.py`, and the shared
`nlp.keywords`/`nlp.embeddings` providers -- each of which is independently
testable in isolation from this orchestration.
"""

from __future__ import annotations

from pathlib import Path

from ...config.schema import ContextConfig, OCRConfig
from ...core.interfaces import ContextBuilder, EmbeddingProvider, KeywordExtractor
from ...core.models import ArtifactPaths, Topic
from .ocr.engine import OCREngine


class DefaultContextBuilder(ContextBuilder):
    """Default `ContextBuilder` implementation.

    TODO: port the `run()` body from `MeetingContextBuilder.run()`:
      1. Load the frame log; for each unique linked frame file, OCR once
         (cache by filename -- see
         ../../../../meeting_pipeline/docs/context_stage.md section 5.1)
         via `self._ocr_engine.extract_spatial()`.
      2. Assemble the per-segment clean timeline.
      3. `topic_clustering.build_topics(...)`, using `self._embeddings` if
         `config.embeddings_enabled`.
      4. `boilerplate_filter.find_boilerplate_tokens(...)` once across the
         whole meeting, then per topic: aggregate transcript by speaker,
         `boilerplate_filter.clean_and_dedup(...)` the visual text,
         `self._keywords.extract(...)`, assemble `searchable_query`.
      5. Write `meeting_timeline_clean.json` / `meeting_context.json` /
         `meeting_context_for_matching.jsonl` via `storage.json_store`.
      6. Return the list of `Topic` objects.
    """

    def __init__(
        self,
        config: ContextConfig,
        ocr_config: OCRConfig,
        *,
        embedding_provider: EmbeddingProvider | None,
        keyword_extractor: KeywordExtractor,
    ) -> None:
        self.config = config
        self._ocr_engine = OCREngine(ocr_config)
        self._embeddings = embedding_provider
        self._keywords = keyword_extractor

    def run(self, frame_log_path: Path, frames_dir: Path, paths: ArtifactPaths) -> list[Topic]:
        raise NotImplementedError

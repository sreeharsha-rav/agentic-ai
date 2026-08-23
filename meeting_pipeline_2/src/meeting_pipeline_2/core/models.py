"""Domain data models shared across every stage.

These mirror the JSON shapes documented in
`../meeting_pipeline/docs/outputs.md` -- keep them in sync with that
reference as fields are ported over. Every model here is a plain
`@dataclass`: no methods that do I/O or call a model/backend, so any stage's
unit tests can construct these directly without touching the filesystem.

TODO: as each stage is implemented, flesh out the dataclass this section
stubs, matching the corresponding JSON schema in outputs.md exactly (field
names are load-bearing -- they're serialized to the pipeline's on-disk
artifacts).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


# ---------------------------------------------------------------------------
# Step 0: TRANSCRIBE
# ---------------------------------------------------------------------------


@dataclass
class TranscriptCue:
    """One WebVTT cue: a single timed caption, pre-speaker-chunk-merging.

    Port reference: the per-segment loop in
    `meeting_pipeline/audio_transcriber.py::transcribe()`.
    """

    index: int
    start_sec: float
    end_sec: float
    text: str


# ---------------------------------------------------------------------------
# Steps 1-3: FRAMES
# ---------------------------------------------------------------------------


@dataclass
class SpeechChunk:
    """A merged same-speaker speech chunk, parsed out of the VTT transcript.

    Port reference: `meeting_pipeline/transcript.py::parse_vtt_chunks()`.
    """

    start_sec: float
    end_sec: float
    speaker: str
    text: str


@dataclass
class FrameLogEntry:
    """One row of the unified frame log (`hybrid_enriched_log.json`).

    Port reference: the dict literals built in
    `meeting_pipeline/hybrid_extractor.py::_extract_audio_anchored()` and
    `_scan_gaps()`.
    """

    source: str  # "audio" | "gap"
    start_sec: float
    end_sec: float
    speaker: str | None
    text: str | None
    frame_files: list[str] = field(default_factory=list)
    is_duplicate: bool = False


# ---------------------------------------------------------------------------
# Step 4: CONTEXT
# ---------------------------------------------------------------------------


@dataclass
class SpatialOCRResult:
    """OCR text decomposed by screen geometry into titles/content/details.

    Port reference: `SpatialLayoutExtractor.decompose()` in
    `meeting_pipeline/ocr_engine.py`, to be re-homed at
    `stages/context/ocr/spatial_layout.py`.
    """

    titles: list[str] = field(default_factory=list)
    content: list[str] = field(default_factory=list)
    details: list[str] = field(default_factory=list)
    flat_text: str = ""


@dataclass
class Topic:
    """One topic cluster: a group of chronological speech segments plus
    their aggregated multimodal context.

    Port reference: the context dict built in
    `meeting_pipeline/context_builder.py::build_matchable_context()`.
    """

    topic_id: str
    start_sec: float
    end_sec: float
    speakers: list[str]
    transcript_aggregated: str
    visual_titles: list[str] = field(default_factory=list)
    visual_content: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    frame_files: list[str] = field(default_factory=list)
    searchable_query: str = ""


# ---------------------------------------------------------------------------
# Step 5: ALIGN
# ---------------------------------------------------------------------------


@dataclass
class DocumentChunk:
    """One ingested unit of a reference document (a page/slide/paragraph
    group/markdown block/OCR'd image).

    Port reference: the chunk dicts returned by each `_ingest_*` method in
    `meeting_pipeline/document_aligner.py`, to be re-homed at
    `stages/align/ingestion/*.py`.
    """

    chunk_id: str
    source: str
    text: str
    section_hierarchy: str | None = None
    keywords: list[str] = field(default_factory=list)


@dataclass
class DocumentMatch:
    """A confirmed topic-to-document alignment.

    Port reference: entries appended to `topic_matched_docs` in
    `meeting_pipeline/document_aligner.py::align()`.
    """

    document: str
    combined_score: float
    highest_confidence_score: float
    sections_matched: list[str] = field(default_factory=list)


@dataclass
class AlignedTopic:
    """A `Topic` plus its resolved document alignment(s).

    Port reference: entries in `clean_aligned` in
    `meeting_pipeline/document_aligner.py::save()`.
    """

    topic: Topic
    matches: list[DocumentMatch] = field(default_factory=list)

    @property
    def has_document_alignment(self) -> bool:
        return bool(self.matches)


# ---------------------------------------------------------------------------
# Cross-cutting
# ---------------------------------------------------------------------------


@dataclass
class ArtifactPaths:
    """Resolved on-disk paths for one pipeline run's artifacts.

    Built by `storage/artifact_paths.py`, consumed by `pipeline/orchestrator.py`
    and every stage's `service.py`. Centralizing this is what lets a stage
    stay ignorant of the overall on-disk layout -- it's handed exactly the
    paths it needs.
    """

    output_dir: Path
    audio_path: Path
    transcript_path: Path
    frames_dir: Path
    frame_log_path: Path
    context_path: Path
    aligned_path: Path

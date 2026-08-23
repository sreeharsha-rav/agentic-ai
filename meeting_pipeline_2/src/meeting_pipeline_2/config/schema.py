"""Configuration dataclasses -- the full set of tunable values, grouped by
the stage/shared-component they configure.

Port reference: `meeting_pipeline/config.py`'s six dataclasses
(`TranscriptionConfig`, `FrameExtractionConfig`, `OCRConfig`, `ContextConfig`,
`AlignmentConfig`, `RuntimeConfig`) and their exact tuned default values --
copy those defaults verbatim, this scaffold does not change any algorithm's
behavior. See `../../meeting_pipeline/docs/configuration.md` for the
field-by-field reference to port from.

Each section below should end up owned by the layer that actually reads it:
- `TranscriptionConfig`   -> stages/transcribe/
- `FrameExtractionConfig` -> stages/frames/
- `OCRConfig`             -> stages/context/ocr/ (also read by stages/align/
                             for image-document ingestion)
- `ContextConfig`         -> stages/context/
- `AlignmentConfig`       -> stages/align/
- `EmbeddingConfig`       -> nlp/embeddings.py (NEW: previously duplicated as
                             embedding_model/embedding_device/embedding_batch_size
                             fields on both ContextConfig and AlignmentConfig
                             in the original -- factor out once, both stages
                             reference the same section)
- `RuntimeConfig`         -> logging_utils.py
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TranscriptionConfig:
    """Step 0 tunables. TODO: port fields from
    `meeting_pipeline/config.py::TranscriptionConfig`."""

    model_size: str = "base.en"
    device: str = "cpu"
    # TODO: beam_size, temperatures, condition_on_previous_text,
    # repetition_penalty, ffmpeg_path, audio_filter, etc.


@dataclass
class FrameExtractionConfig:
    """Steps 1-3 tunables. TODO: port fields from
    `meeting_pipeline/config.py::FrameExtractionConfig`
    (ssim_threshold, mse_threshold, chunk/gap timing, content_score_threshold, ...)."""


@dataclass
class OCRConfig:
    """OCR backend selection + spatial-layout tuning. TODO: port fields from
    `meeting_pipeline/config.py::OCRConfig`."""

    backend: str | None = None  # None = auto-detect priority chain


@dataclass
class ContextConfig:
    """Step 4 tunables. TODO: port fields from
    `meeting_pipeline/config.py::ContextConfig`
    (topic clustering thresholds, boilerplate filtering, keyword extraction)."""


@dataclass
class AlignmentConfig:
    """Step 5 tunables. TODO: port fields from
    `meeting_pipeline/config.py::AlignmentConfig`
    (scoring weights/thresholds for the two-stage alignment)."""


@dataclass
class EmbeddingConfig:
    """Shared embedding-provider config, consumed by `nlp/embeddings.py`.

    NEW relative to the original: `ContextConfig` and `AlignmentConfig` each
    independently declared embedding_model/embedding_device/embedding_batch_size.
    Since both stages depend on the same `core.interfaces.EmbeddingProvider`,
    this factors that out into one section -- override per-stage only if a
    real need arises, rather than duplicating the fields by default.
    """

    model_name: str = "all-MiniLM-L6-v2"
    device: str = "cpu"
    batch_size: int = 32


@dataclass
class RuntimeConfig:
    """Process-wide settings applied explicitly via `apply_thread_env` --
    never on import. TODO: port fields from
    `meeting_pipeline/config.py::RuntimeConfig`."""

    log_level: str = "INFO"


@dataclass
class PipelineConfig:
    """Top-level container bundling every section.

    TODO: port `from_dict`/`from_json`/`to_dict`/`to_json`/`replace` from
    `meeting_pipeline/config.py::PipelineConfig` -- that logic (nested
    dataclass reconstruction, unknown-field validation) is generic and can
    move here unchanged.
    """

    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    frames: FrameExtractionConfig = field(default_factory=FrameExtractionConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    alignment: AlignmentConfig = field(default_factory=AlignmentConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

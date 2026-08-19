"""Configuration dataclasses for every stage of the pipeline.

Every default here reproduces the exact value the original, monolithic
implementation used (see docs/configuration.md for the full field-by-field
reference and tuning guidance). Grouping them into dataclasses -- instead of
20+ loose constructor kwargs -- makes the tuned values discoverable,
serializable (``to_dict``/``from_dict``/``from_json``), and diffable across runs
(each ``PipelineResult`` records the exact config used, see ``pipeline.py``).

Three parameters that exist in the original source but are never actually
read by the logic they appear to configure have been intentionally dropped
rather than carried forward as dead knobs:

- ``DocumentAligner``'s ``semantic_weight``/``keyword_weight``/``ocr_overlap_weight``
  -- the alignment scoring formula hardcodes its own 0.35/0.15 boost weights
  regardless of what these were set to. The real knobs are
  ``AlignmentConfig.ocr_boost_weight`` / ``keyword_boost_weight``.
- ``MeetingContextBuilder``'s ``topic_window_sec`` -- only ever printed, never
  used to gate anything. ``ContextConfig.max_topic_duration_sec`` is the field
  that actually bounds topic length.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any, Mapping, get_origin, get_type_hints


def _from_dict(cls: type, data: Mapping[str, Any]) -> Any:
    """Build a dataclass instance from a (possibly nested) mapping.

    Raises ``ValueError`` on unknown keys instead of silently ignoring them,
    so a typo in a hand-written config JSON file fails fast. Resolves string
    annotations (this module uses ``from __future__ import annotations``) via
    ``get_type_hints`` so nested dataclass sections and tuple-typed fields are
    reconstructed as such, not left as plain dicts/lists (which matters after
    a JSON round-trip, since JSON has no tuple type).
    """
    known = {f.name: f for f in fields(cls)}
    unknown = set(data) - set(known)
    if unknown:
        raise ValueError(f"Unknown field(s) for {cls.__name__}: {sorted(unknown)}")

    hints = get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for name in known:
        if name not in data:
            continue
        value = data[name]
        hint = hints.get(name)
        if is_dataclass(hint) and isinstance(value, Mapping):
            kwargs[name] = _from_dict(hint, value)
        elif get_origin(hint) is tuple and isinstance(value, list):
            kwargs[name] = tuple(value)
        else:
            kwargs[name] = value
    return cls(**kwargs)


@dataclass
class TranscriptionConfig:
    """Step 0: audio extraction (ffmpeg) + speech recognition (faster-whisper)."""

    model_size: str = "base.en"
    device: str = "cpu"
    compute_type: str = "default"
    language: str = "en"
    initial_prompt: str | None = None
    beam_size: int = 5
    temperatures: tuple[float, ...] = (0.0, 0.2, 0.4)
    condition_on_previous_text: bool = False
    repetition_penalty: float = 1.1
    vad_filter: bool = False
    word_timestamps: bool = False
    ffmpeg_path: str = "ffmpeg"
    audio_filter: str = "highpass=f=80,loudnorm"
    audio_sample_rate: int = 16000
    audio_channels: int = 1

    DEFAULT_INITIAL_PROMPT = (
        "Meeting transcription with clear speech, presentations, discussions, "
        "and action items."
    )

    def resolved_initial_prompt(self) -> str | None:
        return self.initial_prompt if self.initial_prompt is not None else self.DEFAULT_INITIAL_PROMPT


@dataclass
class FrameExtractionConfig:
    """Steps 1-3: audio-anchored frame sampling + silent-gap scanning + dedup."""

    ssim_threshold: float = 0.92
    mse_threshold: float = 500.0
    chunk_gap_seconds: float = 5.0
    max_chunk_duration_seconds: float = 30.0
    min_gap_duration_seconds: float = 5.0
    gap_sample_interval_seconds: float = 5.0
    frame_sample_count: int = 5
    content_score_threshold: float = 0.15
    intra_chunk_ssim_threshold: float = 0.85
    delete_deduped_frames: bool = False


@dataclass
class OCRConfig:
    """OCR backend selection and spatial-layout decomposition tuning."""

    backend: str | None = None  # None = auto-detect: rapid -> paddle -> easy -> tesseract -> none
    enabled: bool = True
    spatial_mode: str = "spatial_hierarchical"  # or "flat"
    crop_margins: bool = True
    top_margin_cut: float = 0.03
    bottom_margin_cut: float = 0.07
    title_height_multiplier: float = 1.30
    title_height_floor: float = 0.024
    detail_height_multiplier: float = 0.75
    title_band_ratio: float = 0.22
    sidebar_x_ratio: float = 0.18
    max_clean_text_chars: int = 5000
    extra_noise_patterns: tuple[str, ...] = ()


@dataclass
class ContextConfig:
    """Step 4: topic clustering and multimodal context aggregation."""

    topic_gap_sec: float = 30.0
    max_topic_duration_sec: float = 120.0
    topic_similarity_threshold: float = 0.68
    min_segments_before_semantic_split: int = 2
    embeddings_enabled: bool = True
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32
    boilerplate_document_frequency: float = 0.65
    min_frames_for_boilerplate: int = 4
    dedup_jaccard_threshold: float = 0.65
    keyword_ngram_size: int = 2
    keyword_candidates: int = 6
    max_keywords: int = 8
    max_visual_content_lines: int = 15
    searchable_query_max_chars: int = 6000


@dataclass
class AlignmentConfig:
    """Step 5: two-stage document/section reverse alignment scoring."""

    similarity_threshold: float = 0.25
    high_confidence_threshold: float = 0.45
    stage1_promote_threshold: float = 0.40
    ocr_boost_weight: float = 0.35
    keyword_boost_weight: float = 0.15
    global_score_weight: float = 0.60
    chunk_score_weight: float = 0.40
    title_containment_threshold: float = 0.60
    title_containment_boost: float = 0.90
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_device: str = "cpu"
    embedding_batch_size: int = 32
    keyword_ngram_size: int = 2
    keyword_candidates: int = 10
    min_pdf_chunk_chars: int = 30
    min_pptx_chunk_chars: int = 20
    min_text_block_chars: int = 25
    min_image_ocr_chars: int = 20


@dataclass
class RuntimeConfig:
    """Process-wide settings applied explicitly via ``apply_thread_env`` -- never on import."""

    omp_num_threads: int | None = 1
    tokenizers_parallelism: bool = False
    kmp_duplicate_lib_ok: bool = True
    log_level: str = "INFO"


@dataclass
class PipelineConfig:
    """Top-level container bundling every stage's configuration."""

    transcription: TranscriptionConfig = field(default_factory=TranscriptionConfig)
    frames: FrameExtractionConfig = field(default_factory=FrameExtractionConfig)
    ocr: OCRConfig = field(default_factory=OCRConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    alignment: AlignmentConfig = field(default_factory=AlignmentConfig)
    runtime: RuntimeConfig = field(default_factory=RuntimeConfig)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PipelineConfig":
        return _from_dict(cls, data)

    @classmethod
    def from_json(cls, path: str | Path) -> "PipelineConfig":
        with open(path, encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, path: str | Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

    def replace(self, **nested_overrides: Mapping[str, Any]) -> "PipelineConfig":
        """Return a copy with per-section overrides, e.g. ``cfg.replace(frames={"ssim_threshold": 0.95})``."""
        data = self.to_dict()
        for section, overrides in nested_overrides.items():
            if section not in data:
                raise ValueError(f"Unknown config section: {section!r}")
            data[section] = {**data[section], **overrides}
        return PipelineConfig.from_dict(data)

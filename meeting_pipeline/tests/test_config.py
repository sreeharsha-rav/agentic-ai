"""Locks in every tuned default value carried over from the original implementation.

This is the primary regression guard proving the port preserved the
empirically-tuned thresholds (SSIM/MSE cutoffs, content-score weights,
alignment boost weights, etc.) byte-for-byte rather than approximately.
"""

from __future__ import annotations

import pytest

from meeting_pipeline.config import (
    AlignmentConfig,
    ContextConfig,
    FrameExtractionConfig,
    OCRConfig,
    PipelineConfig,
    RuntimeConfig,
    TranscriptionConfig,
)


def test_transcription_defaults():
    cfg = TranscriptionConfig()
    assert cfg.model_size == "base.en"
    assert cfg.device == "cpu"
    assert cfg.compute_type == "default"
    assert cfg.language == "en"
    assert cfg.initial_prompt is None
    assert cfg.beam_size == 5
    assert cfg.temperatures == (0.0, 0.2, 0.4)
    assert cfg.condition_on_previous_text is False
    assert cfg.repetition_penalty == 1.1
    assert cfg.vad_filter is False
    assert cfg.word_timestamps is False
    assert cfg.ffmpeg_path == "ffmpeg"
    assert cfg.audio_filter == "highpass=f=80,loudnorm"
    assert cfg.audio_sample_rate == 16000
    assert cfg.audio_channels == 1
    assert cfg.resolved_initial_prompt() == TranscriptionConfig.DEFAULT_INITIAL_PROMPT
    assert TranscriptionConfig(initial_prompt="custom").resolved_initial_prompt() == "custom"


def test_frame_extraction_defaults():
    cfg = FrameExtractionConfig()
    assert cfg.ssim_threshold == 0.92
    assert cfg.mse_threshold == 500.0
    assert cfg.chunk_gap_seconds == 5.0
    assert cfg.max_chunk_duration_seconds == 30.0
    assert cfg.min_gap_duration_seconds == 5.0
    assert cfg.gap_sample_interval_seconds == 5.0
    assert cfg.frame_sample_count == 5
    assert cfg.content_score_threshold == 0.15
    assert cfg.intra_chunk_ssim_threshold == 0.85
    assert cfg.delete_deduped_frames is False


def test_ocr_defaults():
    cfg = OCRConfig()
    assert cfg.backend is None
    assert cfg.enabled is True
    assert cfg.spatial_mode == "spatial_hierarchical"
    assert cfg.crop_margins is True
    assert cfg.top_margin_cut == 0.03
    assert cfg.bottom_margin_cut == 0.07
    assert cfg.title_height_multiplier == 1.30
    assert cfg.title_height_floor == 0.024
    assert cfg.detail_height_multiplier == 0.75
    assert cfg.title_band_ratio == 0.22
    assert cfg.sidebar_x_ratio == 0.18
    assert cfg.max_clean_text_chars == 5000
    assert cfg.extra_noise_patterns == ()


def test_context_defaults():
    cfg = ContextConfig()
    assert cfg.topic_gap_sec == 30.0
    assert cfg.max_topic_duration_sec == 120.0
    assert cfg.topic_similarity_threshold == 0.68
    assert cfg.min_segments_before_semantic_split == 2
    assert cfg.embeddings_enabled is True
    assert cfg.embedding_model == "all-MiniLM-L6-v2"
    assert cfg.embedding_device == "cpu"
    assert cfg.embedding_batch_size == 32
    assert cfg.boilerplate_document_frequency == 0.65
    assert cfg.min_frames_for_boilerplate == 4
    assert cfg.dedup_jaccard_threshold == 0.65
    assert cfg.keyword_ngram_size == 2
    assert cfg.keyword_candidates == 6
    assert cfg.max_keywords == 8
    assert cfg.max_visual_content_lines == 15
    assert cfg.searchable_query_max_chars == 6000


def test_alignment_defaults():
    cfg = AlignmentConfig()
    assert cfg.similarity_threshold == 0.25
    assert cfg.high_confidence_threshold == 0.45
    assert cfg.stage1_promote_threshold == 0.40
    assert cfg.ocr_boost_weight == 0.35
    assert cfg.keyword_boost_weight == 0.15
    assert cfg.global_score_weight == 0.60
    assert cfg.chunk_score_weight == 0.40
    assert cfg.title_containment_threshold == 0.60
    assert cfg.title_containment_boost == 0.90
    assert cfg.embedding_model == "all-MiniLM-L6-v2"
    assert cfg.keyword_candidates == 10
    assert cfg.min_pdf_chunk_chars == 30
    assert cfg.min_pptx_chunk_chars == 20
    assert cfg.min_text_block_chars == 25
    assert cfg.min_image_ocr_chars == 20


def test_runtime_defaults():
    cfg = RuntimeConfig()
    assert cfg.omp_num_threads == 1
    assert cfg.tokenizers_parallelism is False
    assert cfg.kmp_duplicate_lib_ok is True
    assert cfg.log_level == "INFO"


def test_pipeline_config_is_cheaply_constructible():
    cfg = PipelineConfig()
    assert isinstance(cfg.transcription, TranscriptionConfig)
    assert isinstance(cfg.frames, FrameExtractionConfig)
    assert isinstance(cfg.ocr, OCRConfig)
    assert isinstance(cfg.context, ContextConfig)
    assert isinstance(cfg.alignment, AlignmentConfig)
    assert isinstance(cfg.runtime, RuntimeConfig)


def test_to_dict_from_dict_roundtrip():
    cfg = PipelineConfig()
    restored = PipelineConfig.from_dict(cfg.to_dict())
    assert restored == cfg


def test_from_dict_rejects_unknown_top_level_key():
    with pytest.raises(ValueError):
        PipelineConfig.from_dict({"not_a_real_section": {}})


def test_from_dict_rejects_unknown_nested_key():
    with pytest.raises(ValueError):
        PipelineConfig.from_dict({"frames": {"not_a_real_field": 1}})


def test_replace_overrides_only_named_fields_leaves_siblings_default():
    cfg = PipelineConfig().replace(frames={"ssim_threshold": 0.5})
    assert cfg.frames.ssim_threshold == 0.5
    assert cfg.frames.mse_threshold == 500.0  # untouched sibling stays default
    assert cfg.context == ContextConfig()  # untouched section stays default


def test_from_json_roundtrip(tmp_path):
    cfg = PipelineConfig().replace(ocr={"backend": "rapid"})
    path = tmp_path / "config.json"
    cfg.to_json(path)
    restored = PipelineConfig.from_json(path)
    assert restored == cfg

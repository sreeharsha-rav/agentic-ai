# Configuration Reference

`PipelineConfig` (in `meeting_pipeline.config`) groups every tunable value
into six section dataclasses. All defaults reproduce the pipeline's
originally-tuned values -- treat changing them as an experiment, not a fix.

```python
from meeting_pipeline import PipelineConfig, FrameExtractionConfig

config = PipelineConfig(frames=FrameExtractionConfig(ssim_threshold=0.95))
config = config.replace(ocr={"backend": "easy"})   # or, to tweak an existing config
config.to_json("my_config.json")
config2 = PipelineConfig.from_json("my_config.json")
```

## `transcription` (`TranscriptionConfig`)

| Field | Default | Controls |
|---|---|---|
| `model_size` | `"base.en"` | faster-whisper model. Larger = more accurate, slower. `.en` variants are English-only and more accurate for English speech. |
| `device` | `"cpu"` | `"cpu"` or `"cuda"`. |
| `compute_type` | `"default"` | ctranslate2 compute type; `"default"` is safest/fastest on CPU. |
| `language` | `"en"` | Spoken language code. |
| `initial_prompt` | `None` | Domain/vocabulary priming text. `None` uses a neutral meeting primer (`TranscriptionConfig.DEFAULT_INITIAL_PROMPT`) to avoid biasing transcription toward one domain. |
| `beam_size` | `5` | Beam search width. Higher = more accurate, slower. |
| `temperatures` | `(0.0, 0.2, 0.4)` | Fallback temperature ladder faster-whisper tries in order. |
| `condition_on_previous_text` | `False` | Kept off to prevent repetitive hallucination loops on long silences. |
| `repetition_penalty` | `1.1` | Discourages repeated tokens. |
| `vad_filter` | `False` | Kept off for thread-safety on some platforms; enabling can trim silence but has caused hangs in testing. |
| `word_timestamps` | `False` | Segment-level only by default; this pipeline never uses word-level timing. |
| `ffmpeg_path` | `"ffmpeg"` | Override if ffmpeg isn't on `PATH` under that name. |
| `audio_filter` | `"highpass=f=80,loudnorm"` | ffmpeg audio filter graph. Falls back to no filter automatically if the local ffmpeg build rejects it. |
| `audio_sample_rate` | `16000` | Whisper's native sample rate -- don't change unless you know why. |
| `audio_channels` | `1` | Mono. |

## `frames` (`FrameExtractionConfig`)

| Field | Default | Controls |
|---|---|---|
| `ssim_threshold` | `0.92` | Cross-chunk/merge dedup: frames with SSIM above this are treated as duplicates. Lower = dedup more aggressively (risk of dropping genuinely different-but-similar slides). Higher = keep more near-duplicates. |
| `mse_threshold` | `500.0` | Gap-scanner: minimum pixel-difference (MSE) to save a new frame during a silence. Lower = more sensitive to small changes. |
| `chunk_gap_seconds` | `5.0` | Max silence between same-speaker captions still merged into one chunk. |
| `max_chunk_duration_seconds` | `30.0` | Caps how long a single merged chunk can grow, even with no gaps. |
| `min_gap_duration_seconds` | `5.0` | Silences shorter than this are never gap-scanned. |
| `gap_sample_interval_seconds` | `5.0` | Sampling cadence within a silence. |
| `frame_sample_count` | `5` | Candidate frames sampled per speech chunk before content/scene filtering. |
| `content_score_threshold` | `0.15` | Below this, a sampled frame is classified webcam-only and skipped. Lower = let more (possibly low-content) frames through. |
| `intra_chunk_ssim_threshold` | `0.85` | Below this, two samples within the same chunk are treated as different visual scenes. |
| `delete_deduped_frames` | `False` | If `True`, actually deletes the PNG file for a frame identified as a duplicate during the final merge pass (the original behavior only dropped the log entry, orphaning the file). |

## `ocr` (`OCRConfig`)

| Field | Default | Controls |
|---|---|---|
| `backend` | `None` | Force a specific backend (`"rapid"`/`"paddle"`/`"easy"`/`"tesseract"`/`"none"`), or `None` to auto-detect in that priority order. See `docs/ocr_backends.md`. |
| `enabled` | `True` | `False` disables OCR entirely (transcript-only context). |
| `spatial_mode` | `"spatial_hierarchical"` | `"spatial_hierarchical"` (titles/content/details) or `"flat"` (one text blob). Only `rapid`/`paddle` backends actually produce the hierarchical form; `easy`/`tesseract` always fall back to flat. |
| `crop_margins` | `True` | If `True`, boxes centered in the top/bottom margin bands are rejected as OS/browser chrome. |
| `top_margin_cut` / `bottom_margin_cut` | `0.03` / `0.07` | Margin band sizes (fraction of frame height). |
| `title_height_multiplier` | `1.30` | A box is a title if its height >= this x the frame's median text height. |
| `title_height_floor` | `0.024` | Absolute minimum height fraction for the multiplier rule (prevents tiny-text frames from making everything a "title"). |
| `detail_height_multiplier` | `0.75` | A small, far-left-column box below this x median height becomes a detail/nav label. |
| `title_band_ratio` | `0.22` | A box vertically above this fraction of frame height, at or above median height, is also treated as a title (top-banner heading rule). |
| `sidebar_x_ratio` | `0.18` | A box horizontally left of this fraction of frame width qualifies for the detail-column rule. |
| `max_clean_text_chars` | `5000` | Cap on cleaned OCR text length per box/frame. |
| `extra_noise_patterns` | `()` | Additional regexes stripped from OCR text, applied after the built-in cleaning rules. Use this for recording-specific noise (e.g. a recurring avatar-badge format) instead of editing the package. See `docs/ocr_backends.md` for a worked example. |

## `context` (`ContextConfig`)

| Field | Default | Controls |
|---|---|---|
| `topic_gap_sec` | `30.0` | Silence gap that forces a new topic. |
| `max_topic_duration_sec` | `120.0` | Cumulative duration cap per topic. |
| `topic_similarity_threshold` | `0.68` | Embedding cosine similarity floor to stay in the same topic. Lower = fewer, broader topics; higher = more, narrower topics. |
| `min_segments_before_semantic_split` | `2` | A topic needs at least this many segments before semantic drift alone can split it. |
| `embeddings_enabled` | `True` | `False` uses time-based grouping only (also the automatic fallback if the embedding model fails to load). |
| `embedding_model` | `"all-MiniLM-L6-v2"` | sentence-transformers model name. |
| `embedding_device` | `"cpu"` | |
| `embedding_batch_size` | `32` | |
| `boilerplate_document_frequency` | `0.65` | An OCR token appearing in more than this fraction of a meeting's frames is stripped as static UI chrome. |
| `min_frames_for_boilerplate` | `4` | The document-frequency filter only activates with at least this many OCR'd frames (too few frames make frequency statistics meaningless). |
| `dedup_jaccard_threshold` | `0.65` | Two visual text lines with token-set Jaccard similarity above this are treated as near-duplicates and collapsed to one. |
| `keyword_ngram_size` | `2` | YAKE keyword n-gram size. |
| `keyword_candidates` | `6` | YAKE candidates considered per topic. |
| `max_keywords` | `8` | Keywords kept per topic after extraction. |
| `max_visual_content_lines` | `15` | Cap on visual content lines embedded into `searchable_query` (the full deduped list is still kept in `visual_hierarchy.content`). |
| `searchable_query_max_chars` | `6000` | Overall cap on the `searchable_query` string. |

## `alignment` (`AlignmentConfig`)

| Field | Default | Controls |
|---|---|---|
| `similarity_threshold` | `0.25` | Minimum composite score for any candidate (document or chunk) to be considered at all. |
| `high_confidence_threshold` | `0.45` | Minimum combined score for a document to be recorded as a confirmed match. |
| `stage1_promote_threshold` | `0.40` | Minimum Stage-1 document score to be promoted to Stage-2 chunk-level scoring (falls back to the single best candidate if none clear this bar). |
| `ocr_boost_weight` | `0.35` | Weight of the OCR-overlap signal in the composite score. |
| `keyword_boost_weight` | `0.15` | Weight of the YAKE keyword-Jaccard signal. |
| `global_score_weight` / `chunk_score_weight` | `0.60` / `0.40` | How Stage 1's document score and Stage 2's best chunk score are combined. |
| `title_containment_threshold` | `0.60` | Minimum fraction of a visual title's tokens that must appear in a doc chunk to trigger the title-boost. |
| `title_containment_boost` | `0.90` | Score contributed when the title-containment rule fires. |
| `embedding_model` / `embedding_device` / `embedding_batch_size` | `"all-MiniLM-L6-v2"` / `"cpu"` / `32` | |
| `keyword_ngram_size` / `keyword_candidates` | `2` / `10` | YAKE settings for document/chunk keyword extraction. |
| `min_pdf_chunk_chars` | `30` | Minimum characters for a PDF page (or DOCX paragraph group, which shares this default) to become a chunk. |
| `min_pptx_chunk_chars` | `20` | Minimum characters for a PPTX slide's combined text. |
| `min_text_block_chars` | `25` | Minimum characters for a Markdown/text block. |
| `min_image_ocr_chars` | `20` | Minimum OCR'd characters for an image document to be ingested. |

**Note on composite scoring:** the semantic-cosine term always has an
implicit weight of `1.0` (it isn't a separate configurable field) --
`ocr_boost_weight` and `keyword_boost_weight` are *additive boosts* on top of
it, not weights in a normalized weighted average. This matches the
original scoring formula exactly: `score = min(cosine + ocr_boost_weight *
ocr_overlap + keyword_boost_weight * keyword_jaccard, 1.0)`.

## `runtime` (`RuntimeConfig`)

| Field | Default | Controls |
|---|---|---|
| `omp_num_threads` | `1` | Set to avoid a known CTranslate2/PyTorch thread-pool deadlock on some platforms. `None` leaves `OMP_NUM_THREADS` untouched. |
| `tokenizers_parallelism` | `False` | Maps to `TOKENIZERS_PARALLELISM`. |
| `kmp_duplicate_lib_ok` | `True` | Maps to `KMP_DUPLICATE_LIB_OK=TRUE`. |
| `log_level` | `"INFO"` | Used by the CLI's `configure_logging()`. |

**This section is never applied automatically.** A library must not mutate
`os.environ` on import. Call `meeting_pipeline.logging_utils.apply_thread_env(config.runtime)`
yourself, before importing torch/faster-whisper/sentence-transformers, or let
the CLI do it for you (it always calls this before running any stage).

## Fields intentionally not carried forward

Three parameters existed in the original, pre-packaging implementation but
were never actually read by the logic they appeared to configure. They were
dropped rather than shipped as dead knobs:

- `DocumentAligner`'s old `semantic_weight`/`keyword_weight`/`ocr_overlap_weight`
  constructor arguments -- the scoring formula hardcoded its own boost
  weights regardless of what these were set to. The real, effective knobs
  are `AlignmentConfig.ocr_boost_weight` / `keyword_boost_weight` above.
- `MeetingContextBuilder`'s old `topic_window_sec` argument -- only ever
  logged, never used to gate topic length. `ContextConfig.max_topic_duration_sec`
  is the field that actually bounds it.

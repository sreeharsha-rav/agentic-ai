# Architecture

## Core principle: time is the primary key

Every artifact in this pipeline carries `start_sec`/`end_sec`. There is no
separate "alignment engine" that joins transcript to video after the fact --
timestamps are the join key from the very first stage. Each stage reads the
previous stage's file from disk and writes its own; this file-based hand-off
is what makes stages independently resumable (`stages=`/`resume=` on
`MeetingPipeline.run()`).

```
video.mp4
   │
   ▼  Step 0
generated_transcript.vtt
   │
   ▼  Steps 1-3
hybrid_enriched_log.json + video/hybrid/*.png
   │
   ▼  Step 4
meeting_context.json
   │
   ▼  Step 5
aligned_context.json
```

## Step 0: Transcription

`AudioTranscriber` extracts mono 16kHz audio via ffmpeg (with an optional
high-pass + loudness-normalization filter, falling back to plain extraction
if the local ffmpeg build lacks the filter), then runs `faster-whisper`
locally with anti-hallucination decoding settings (multi-temperature
fallback, no cross-segment conditioning, repetition penalty). The output VTT
is treated purely as an intermediate artifact -- nothing downstream reads it
again; every later stage operates on the richer JSON structures below.

Word-level alignment and true speaker diarization are out of scope here:
transcription is segment-level only, and any speaker labels come from
WebVTT `<v Speaker>` tags already present in the source VTT (e.g. from a
Teams/Zoom export), not from a diarization model.

## Steps 1-3: Frame extraction

`HybridExtractor` is a purpose-built alternative to fixed-interval frame
sampling. It has two independent extraction passes that are then merged:

**Audio-anchored extraction.** For every merged speech chunk (same-speaker
VTT captions merged while the gap between them stays under
`chunk_gap_seconds`), sample `frame_sample_count` frames evenly across the
chunk's time range, then:

1. Score each sample with a composite **content score** -- a pure-OpenCV
   heuristic combining Laplacian edge-density variance, near-white pixel
   ratio, and horizontal-Sobel text-line density -- and drop any sample
   below `content_score_threshold` (classified as webcam-only, no slide/code
   on screen).
2. Detect intra-chunk scene changes via SSIM among the surviving samples,
   keeping the sharpest (highest Laplacian variance) frame per distinct
   scene.
3. Compare this chunk's first frame against the previous chunk's via SSIM;
   if near-identical, link to the same file instead of saving a new one
   (cross-chunk dedup).

**Visual gap scanner.** For silent windows between speech chunks (at least
`min_gap_duration_seconds` long), sample every `gap_sample_interval_seconds`
and save a frame whenever the MSE against the last-saved gap frame exceeds
`mse_threshold`. This scans all the way to the end of the video, not just the
last spoken word -- slides/code are often left on screen silently after a
meeting's last words.

**Merge + dedup.** The two frame sets are merged chronologically and one
final SSIM pass removes any residual near-duplicates across both sources.

So there are three distinct dedup layers in total: intra-chunk (SSIM),
cross-chunk (SSIM), and final merge (SSIM) -- each catching a different kind
of redundancy (scene changes within a chunk, static screens across
consecutive chunks, and static screens across a silence gap plus the
speech either side of it).

## Step 4: Context building

`MeetingContextBuilder` does two things: OCR + spatial decomposition of every
linked frame, and topic clustering of the speech-chunk timeline.

**OCR and spatial decomposition.** `OCREngine` tries backends in priority
order (see `docs/ocr_backends.md`) and, for backends that return bounding
boxes, `SpatialLayoutExtractor` buckets each box into **titles / content /
details** using percentile-based relative font height (a box significantly
taller than the frame's median text height, or in the top banner zone,
becomes a title; a small box in the far-left column becomes a detail/nav
label; everything else is content) plus perimeter rejection (top/bottom
margins are OS taskbar / browser chrome, not slide content).

**Topic clustering.** Speech segments are grouped into topics using three
independent split conditions, checked per segment:

1. The silence gap since the previous segment exceeds `topic_gap_sec`.
2. The topic's cumulative duration exceeds `max_topic_duration_sec`.
3. (If embeddings are enabled) the segment's embedding cosine similarity
   against the topic's running centroid drops below
   `topic_similarity_threshold` -- but only once the topic already has at
   least `min_segments_before_semantic_split` segments, so a single
   still-forming topic can't fracture on its second segment.

**Boilerplate filtering.** Across all of a meeting's frames, any OCR token
appearing in more than `boilerplate_document_frequency` of frames (e.g. a
recurring participant name, a persistent app title bar) is treated as static
UI chrome and stripped from every topic's visual text -- this is the general
mechanism that makes hardcoding specific noise strings unnecessary (see
`docs/ocr_backends.md`).

Each topic's transcript (grouped by speaker), deduplicated visual
titles/content/details, and YAKE keywords are combined into one
`searchable_query` string used by Step 5.

## Step 5: Document alignment

`DocumentAligner` ingests reference documents (`.pdf` per-page,
`.docx` per-paragraph-group, `.pptx` per-slide, `.md`/`.txt` per block with
header breadcrumbs, images via OCR) and reverse-aligns meeting topics against
them in two stages:

**Stage 1 (document-level).** Every topic is scored against a whole-document
"fingerprint" profile (title + section headers + first ~3000 chars,
embedded once per document) using a weighted composite:

```
doc_score = min(semantic_cosine + ocr_boost_weight * ocr_overlap + keyword_boost_weight * keyword_jaccard, 1.0)
```

Candidates scoring at or above `stage1_promote_threshold` are promoted to
Stage 2 (or, if none clear that bar, the single best-scoring document is
used as a fallback) -- this prevents a small generic chunk in an unrelated
document from producing a false-positive match before the document-level
signal has had a say.

**Stage 2 (section-level).** Within each promoted document, every chunk is
scored the same way against the topic, and the best chunk score is combined
with the Stage 1 document score:

```
combined_score = global_score_weight * stage1_document_score + chunk_score_weight * best_chunk_score
```

A document is only recorded as a confirmed match for a topic if
`combined_score >= high_confidence_threshold`.

The OCR-overlap signal itself gives visual **titles** on screen a much
higher weight than generic content overlap: if a title's tokens are at least
`title_containment_threshold` contained within a document chunk, that alone
contributes `title_containment_boost * overlap` to the score -- the
intuition being that a slide's own heading matching a document section
header is strong independent evidence, even before considering the rest of
the visual/transcript text.

## Roadmap / not implemented

These are real gaps relative to a fuller "meeting intelligence" vision, not
things this package claims to do:

- **Screen-type classification.** Nothing labels a frame as
  presentation/code/terminal/whiteboard; the content-score heuristic only
  makes a binary content-vs-webcam decision.
- **Visual understanding beyond OCR text.** No vision-language model
  description of what a diagram/screen represents -- OCR text and spatial
  position only.
- **Semantic event typing.** Topics are clustered by time/similarity only;
  nothing classifies a topic as a Decision, Action Item, Question, etc.
- **Markdown/notes generation.** The terminal artifact is structured JSON
  (`aligned_context.json`), not rendered meeting notes.
- **Diagram generation.** Nothing derives a Mermaid/Graphviz diagram from
  extracted entities or OCR'd content.
- **Adaptive, transcript-driven frame sampling.** Sampling density is fixed
  per chunk/gap, not triggered by detected topic transitions.
- **Persisted vector search index.** Embeddings are used transiently during
  scoring; `meeting_context_for_matching.jsonl` is a flat file, not a
  FAISS/Qdrant-style index.

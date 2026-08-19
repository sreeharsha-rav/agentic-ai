# meeting-pipeline

A temporal multimodal meeting-processing pipeline: it transcribes a meeting
recording, extracts the slide/screen frames that were visible while each
thing was said, builds topic-level multimodal context (transcript + OCR),
and aligns meeting topics against your own reference documents (specs,
decks, design docs).

Everything is local and CPU-friendly -- no LLM API calls, no cloud services.
The only "AI" in the pipeline is a local Whisper speech-to-text model, a
small sentence-embedding model, and a classical OCR backend.

```
video.mp4
   │
   ▼  Step 0 -- AudioTranscriber        (ffmpeg + faster-whisper)
generated_transcript.vtt
   │
   ▼  Steps 1-3 -- HybridExtractor      (OpenCV: SSIM/MSE scene detection)
hybrid_enriched_log.json + video/hybrid/*.png
   │
   ▼  Step 4 -- MeetingContextBuilder   (OCR + topic clustering)
meeting_context.json
   │
   ▼  Step 5 -- DocumentAligner         (semantic + keyword + OCR scoring)
aligned_context.json
```

See `docs/architecture.md` for how each stage actually works, `docs/outputs.md`
for the JSON schema of every file produced, `docs/configuration.md` for every
tunable parameter, and `docs/ocr_backends.md` for OCR backend selection.

## Requirements

- Python >= 3.10 (developed and tested on 3.12)
- **ffmpeg** on `PATH`:
  - Windows: `winget install Gyan.FFmpeg`
  - macOS: `brew install ffmpeg`
  - Linux: `apt install ffmpeg` (or your distro's package manager)
- An OCR backend (optional, but recommended -- see below)

## Install

```bash
pip install -e .
# or, for a fixed dependency list:
pip install -r requirements.txt
```

Sentence embeddings (used for topic clustering and document alignment) pull
in `torch` transitively via `sentence-transformers`. If you only need CPU
inference, install the CPU-only wheel to save ~2GB:

```bash
pip install -e . --extra-index-url https://download.pytorch.org/whl/cpu
```

### OCR backend

No OCR backend is a hard requirement -- the pipeline degrades gracefully to
transcript-only context if none is installed. But you'll get much richer
output with one:

```bash
pip install -e ".[ocr]"        # rapidocr-onnxruntime -- recommended for Windows/Linux
pip install -e ".[easyocr]"    # heavier, but the most portable fallback
pip install -e ".[paddleocr]"  # alternative, works well on macOS
pip install -e ".[tesseract]"  # lightest, needs the Tesseract binary installed separately
```

See `docs/ocr_backends.md` for the full backend priority chain and what
you get with each.

## Quickstart

### As a function

```python
from meeting_pipeline import run_pipeline

result = run_pipeline(
    video_path="meeting.mp4",
    output_dir="./output/my_meeting",
    documents=["spec.md", "slides.pptx"],
)
print(result.aligned_path)       # ./output/my_meeting/aligned_context.json
print(result.topic_count, result.aligned_topic_count)
```

### As a class, with custom configuration

```python
from meeting_pipeline import MeetingPipeline, PipelineConfig, FrameExtractionConfig, OCRConfig

config = PipelineConfig(
    frames=FrameExtractionConfig(ssim_threshold=0.95),   # dedup frames more aggressively
    ocr=OCRConfig(backend="easy"),                        # force a specific OCR backend
)
pipeline = MeetingPipeline(config)
result = pipeline.run("meeting.mp4", "./output/my_meeting", documents="./reference_docs/")
```

### From the command line

```bash
meeting-pipeline run --video meeting.mp4 --out ./output/my_meeting --docs spec.md slides.pptx
# or, equivalently:
python -m meeting_pipeline run --video meeting.mp4 --out ./output/my_meeting --docs-dir ./reference_docs
```

## Output files

Written under your `output_dir`:

| File | Produced by | Contents |
|---|---|---|
| `extracted_audio.wav` | Step 0 | Mono 16kHz WAV extracted from the video |
| `generated_transcript.vtt` | Step 0 | Time-aligned transcript |
| `video/hybrid/*.png` | Steps 1-3 | Extracted keyframes |
| `hybrid_enriched_log.json` | Steps 1-3 | Per-chunk log: speaker, text, linked frame(s), timestamps |
| `meeting_timeline_clean.json` | Step 4 | Clean per-segment timeline with OCR + spatial hierarchy |
| `meeting_context.json` | Step 4 | Per-topic aggregated context (transcript, visuals, keywords) |
| `meeting_context_for_matching.jsonl` | Step 4 | Slim per-topic search index |
| `aligned_context_intermediate_detailed.json` | Step 5 | Full per-topic scoring detail |
| `aligned_context.json` | Step 5 | **Final deliverable**: topic -> linked document + confidence |
| `run_manifest.json` | `MeetingPipeline.run()` | Config used, stage timings, artifact paths |

Full JSON schemas: `docs/outputs.md`.

## Running stages individually, or resuming

```python
from meeting_pipeline import MeetingPipeline, Stage

pipeline = MeetingPipeline()

# Run only Steps 4-5 against already-generated Step 0-3 artifacts:
pipeline.run("meeting.mp4", "./out", documents="./docs/", stages=[Stage.CONTEXT, Stage.ALIGN])

# Skip any stage whose primary output file already exists on disk:
pipeline.run("meeting.mp4", "./out", documents="./docs/", resume=True)

# Or call one stage directly:
vtt_path = pipeline.transcribe("meeting.mp4", "./out")
```

Equivalent CLI subcommands: `meeting-pipeline transcribe|frames|context|align`.

## Configuration

`PipelineConfig` groups every tunable value into six sections. All defaults
match the pipeline's originally-tuned values.

| Section | Controls |
|---|---|
| `transcription` | Whisper model size/device, decoding parameters, ffmpeg audio filter |
| `frames` | SSIM/MSE thresholds, chunk/gap timing, content-score threshold |
| `ocr` | Backend selection, spatial-layout tuning, noise-pattern cleanup |
| `context` | Topic clustering thresholds, boilerplate filtering, keyword extraction |
| `alignment` | Document/section matching weights and thresholds |
| `runtime` | Thread-pool env vars (never applied automatically -- see below) |

Full reference: `docs/configuration.md`. Load/save as JSON:

```python
config = PipelineConfig.from_json("my_config.json")
config.to_json("my_config.json")
```

## Troubleshooting

- **`FFmpegNotFoundError`**: ffmpeg isn't on `PATH`. Install it (see
  Requirements above) and restart your shell/terminal.
- **No OCR backend detected**: the pipeline still runs, but topics get
  transcript-only context (no visual text). Install one of the OCR extras.
- **First run is slow**: the Whisper and sentence-embedding models are
  downloaded and cached on first use (`~/.cache/huggingface`, or wherever
  faster-whisper caches its models). Subsequent runs are fast.
- **Windows console encoding errors**: this package logs via the standard
  `logging` module (ASCII-only messages) specifically to avoid the
  `UnicodeEncodeError` a default Windows console raises on non-ASCII output.
  If you see one, it's likely coming from a dependency, not this package.
- **Thread-pool deadlock on CTranslate2/PyTorch**: a known issue on some
  platforms. This package never mutates `os.environ` on import (a library
  shouldn't). If you hit it, call
  `meeting_pipeline.logging_utils.apply_thread_env()` yourself, before
  importing anything else, or set `OMP_NUM_THREADS=1` in your environment.
  The CLI does this automatically.

## Development

```bash
pip install -e ".[dev]"
pytest                       # fast suite: no model downloads, no real video needed
```

Two environment variables unlock the slower, opt-in integration tests under
`tests/integration/` (skipped by default):

- `MEETING_PIPELINE_RUN_SLOW=1` -- runs `test_stage_chaining.py` (needs the
  `all-MiniLM-L6-v2` embedding model to download on first run).
- `MEETING_PIPELINE_TEST_VIDEO=/path/to/video.mp4` -- additionally runs
  `test_end_to_end.py`, a full pipeline run against a real video (needs
  ffmpeg and an OCR backend installed too).

```bash
ruff check src tests
mypy src
```

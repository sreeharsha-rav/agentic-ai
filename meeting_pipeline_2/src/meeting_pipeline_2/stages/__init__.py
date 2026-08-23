"""One subpackage per pipeline stage: transcribe, frames, context, align.

Each stage subpackage:
  - implements the corresponding protocol from `core.interfaces` in its
    `service.py`;
  - depends on `core/` + the shared `media`/`text`/`nlp`/`storage` packages;
  - never imports from a sibling stage package.

Heavy per-stage dependencies (faster-whisper, opencv, an OCR backend) are
imported lazily inside the module that uses them, not at package-init time,
so `import meeting_pipeline_2.stages` stays cheap.
"""

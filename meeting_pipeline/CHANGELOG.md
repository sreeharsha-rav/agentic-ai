# Changelog

## 0.1.0 -- Initial standalone package

Extracted from an internal monorepo app (`apps/meeting_processor`) as a
clean, independently-installable package. The extraction is a copy-and-adapt
port, not a rewrite: SSIM/MSE thresholds, content-score weights, font-size
percentiles, and alignment score weights are all preserved exactly from the
original tuned implementation. `apps/meeting_processor` itself was left
untouched -- this package has no runtime dependency on it.

### Behavior differences from the original implementation

- **Removed**: a regex in the OCR text-cleaning pipeline that hardcoded a
  handful of specific contributors' names. It was a debug artifact from
  cleaning one contributor's own screen recordings, not a general
  requirement.
- **Removed**: a regex stripping "SR"/"MD"/"PR" + word (originally meant to
  strip avatar-badge initials), which also incidentally stripped legitimate
  engineering text like "PR review" or "MD file". Available again via the
  new `OCRConfig.extra_noise_patterns` if you need it for your own
  recordings -- see `docs/ocr_backends.md`.
- **Dropped as dead configuration**: `DocumentAligner`'s old
  `semantic_weight`/`keyword_weight`/`ocr_overlap_weight` constructor
  arguments and `MeetingContextBuilder`'s old `topic_window_sec` argument --
  none were actually read by the scoring/clustering logic they appeared to
  configure. See `docs/configuration.md`'s "Fields intentionally not carried
  forward" section.
- **Fixed**: a latent crash in the frame merge/dedup pass when a meeting's
  first speech chunk had no linked frame (`frame_file: null`) -- it would
  previously raise `TypeError` from `os.path.join(dir, None)`.
- **Fixed**: a duplicated OCR-engine-initialization block in
  `MeetingContextBuilder.__init__` (harmless dead code, now removed).
- **Changed**: all `print()` output replaced with the standard `logging`
  module, and non-ASCII characters removed from log messages (avoids
  `UnicodeEncodeError` on a default Windows console).
- **Changed**: `DocumentAligner`'s cross-module OCR reuse now uses a normal
  package-relative import instead of a `sys.path.insert` + parent-directory
  reach-around.
- **New**: `PipelineConfig` and its six section dataclasses, replacing ~25
  previously-hardcoded magic numbers with named, documented, overridable
  fields (see `docs/configuration.md`).
- **New**: `MeetingPipeline`/`run_pipeline()` orchestration API and a
  `meeting-pipeline` CLI, replacing a hardcoded, single-developer-machine
  driver script. `stages=`/`resume=` replace the old module-level
  `SKIP_STEPS_0_TO_3`/`SKIP_STEP_4` boolean toggles.
- **New**: this package never mutates `os.environ` on import (the original
  driver script set thread-pool env vars at import time). Call
  `meeting_pipeline.logging_utils.apply_thread_env()` yourself, or use the
  CLI, which does it automatically before running any stage.

"""OCR subsystem: backend-agnostic engine (auto-fallback chain) + spatial
layout decomposition.

Port reference: `meeting_pipeline/ocr_engine.py` in full, split here into
`engine.py` (fallback-chain selection + dispatch), `spatial_layout.py`
(geometry-based titles/content/details classification), and one file per
backend under `backends/` -- versus the original's single file mixing all
of these concerns together. Shared between `stages/context/` (OCR on video
keyframes) and `stages/align/` (OCR on image-format reference documents) --
both import `stages.context.ocr.engine`, there is only one OCR
implementation in the whole codebase.
"""

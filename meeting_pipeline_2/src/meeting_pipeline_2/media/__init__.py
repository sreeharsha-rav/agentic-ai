"""Shared low-level media utilities: ffmpeg subprocess wrapping, video frame
reading, and pure image-comparison metrics.

Used by `stages/transcribe/` (ffmpeg) and `stages/frames/` (video I/O +
metrics). Nothing here should import from `stages/` -- these are leaf
utilities in the dependency graph, one level above `core/`.
"""

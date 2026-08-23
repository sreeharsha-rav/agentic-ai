"""Visual gap scanner: MSE-based scene detection within silent windows
between (and after) speech chunks.

Port reference: `meeting_pipeline/hybrid_extractor.py::_compute_silent_gaps()`
and `_scan_gaps()`. Isolated because it's a distinct signal from
audio-anchored extraction (silence, not speech, is the anchor) using a
different metric (MSE, not SSIM) -- see
../../../../meeting_pipeline/docs/frames_stage.md section 5.4-5.5 for why.
"""

from __future__ import annotations

from ...core.models import FrameLogEntry, SpeechChunk
from ...media.video_capture import VideoCapture


def compute_silent_gaps(chunks: list[SpeechChunk], video_duration_sec: float, *, min_gap_duration_seconds: float) -> list[tuple[float, float]]:
    """Silent windows between speech chunks, including trailing silence to
    `video_duration_sec` (not just the last spoken word).

    TODO: port from `hybrid_extractor.py::_compute_silent_gaps()`.
    """
    raise NotImplementedError


def scan_gaps(cap: VideoCapture, gaps: list[tuple[float, float]], frames_dir, *, sample_interval_seconds: float, mse_threshold: float) -> list[FrameLogEntry]:
    """Sample each gap at `sample_interval_seconds`, saving a frame whenever
    MSE against the last-saved gap frame exceeds `mse_threshold`.

    TODO: port from `hybrid_extractor.py::_scan_gaps()`, including the
    deliberate inlined-MSE-with-cached-last-frame optimization noted in that
    method's comments (avoids reprocessing the same frame twice per step).
    """
    raise NotImplementedError

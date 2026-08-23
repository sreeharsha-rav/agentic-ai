"""Audio-anchored keyframe extraction: sample frames within each speech
chunk's time range, content-filter, and detect intra-chunk scene changes.

Port reference: `meeting_pipeline/hybrid_extractor.py::_extract_chunk_frames()`
and `_extract_audio_anchored()`. Isolated from `gap_scanner.py` and
`dedup.py` because it's a distinct algorithm (content-score gating +
intra-chunk SSIM scene detection + cross-chunk SSIM linking), independently
testable against a fake `VideoCapture` and synthetic frame arrays.
"""

from __future__ import annotations

from ...core.models import FrameLogEntry, SpeechChunk
from ...media.video_capture import VideoCapture


def extract_chunk_frames(cap: VideoCapture, start_sec: float, end_sec: float, *, sample_count: int, content_score_threshold: float, intra_chunk_ssim_threshold: float):
    """Sample `sample_count` frames evenly across [start_sec, end_sec],
    content-filter, and return one (frame, timestamp) per distinct scene.

    TODO: port from `hybrid_extractor.py::_extract_chunk_frames()`.
    """
    raise NotImplementedError


def extract_audio_anchored(
    cap: VideoCapture,
    chunks: list[SpeechChunk],
    frames_dir,
    *,
    sample_count: int,
    content_score_threshold: float,
    intra_chunk_ssim_threshold: float,
    cross_chunk_ssim_threshold: float,
) -> list[FrameLogEntry]:
    """Per speech chunk: extract scene frames, save new ones, cross-chunk
    dedup against the previous chunk's first frame.

    TODO: port from `hybrid_extractor.py::_extract_audio_anchored()`,
    including the fix (documented in ../meeting_pipeline/CHANGELOG.md) for
    the case where the meeting's first chunk has no linked frame at all.
    """
    raise NotImplementedError

"""Thin wrapper around video frame-reading (OpenCV `VideoCapture` today).

Port reference: the `cv2.VideoCapture` usage scattered through
`meeting_pipeline/hybrid_extractor.py` (`run()`, `_extract_chunk_frames()`,
`_scan_gaps()`). Isolating it behind a small class means `stages/frames/`'s
sampling/dedup logic can be unit-tested against a fake capture object instead
of a real video file, and the underlying video-decoding library could be
swapped without touching frame-selection logic.
"""

from __future__ import annotations

from pathlib import Path


class VideoCapture:
    """Seekable frame reader for one video file.

    TODO: port from the `cv2.VideoCapture` calls in `hybrid_extractor.py`:
    open-on-construct (raise `VideoOpenError` if it fails), `duration_sec`
    property (`total_frames / fps`), `read_at(timestamp_sec)` (seek via
    `CAP_PROP_POS_MSEC` + `.read()`), and `release()`/context-manager support.
    """

    def __init__(self, video_path: Path) -> None:
        raise NotImplementedError

    @property
    def duration_sec(self) -> float:
        raise NotImplementedError

    def read_at(self, timestamp_sec: float):
        """Seek to `timestamp_sec` and decode one frame. Returns an ndarray
        or `None` if the read failed."""
        raise NotImplementedError

    def release(self) -> None:
        raise NotImplementedError

    def __enter__(self) -> "VideoCapture":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()

"""Typed exceptions raised across the meeting_pipeline package."""

from __future__ import annotations


class MeetingPipelineError(Exception):
    """Base class for all errors raised by meeting_pipeline."""


class FFmpegNotFoundError(MeetingPipelineError):
    """Raised when the ffmpeg CLI is not available on PATH."""

    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        super().__init__(
            f"ffmpeg executable '{ffmpeg_path}' was not found on PATH.\n"
            "Install it:\n"
            "  Windows : winget install Gyan.FFmpeg\n"
            "  macOS   : brew install ffmpeg\n"
            "  Linux   : apt install ffmpeg  (or your distro's package manager)"
        )


class FFmpegError(MeetingPipelineError):
    """Raised when ffmpeg runs but exits with a non-zero status."""


class VideoOpenError(MeetingPipelineError):
    """Raised when OpenCV cannot open a video file."""

    def __init__(self, video_path: str) -> None:
        super().__init__(f"Cannot open video: {video_path}")


class MissingDependencyError(MeetingPipelineError):
    """Raised when an optional dependency (e.g. an OCR backend) is required but absent."""


class ArtifactNotFoundError(MeetingPipelineError):
    """Raised when a pipeline stage's expected input artifact does not exist on disk."""

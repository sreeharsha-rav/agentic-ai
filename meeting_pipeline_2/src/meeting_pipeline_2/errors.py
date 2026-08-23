"""Typed exceptions raised across meeting_pipeline_2.

Port reference: `meeting_pipeline/errors.py` -- same exception set, same
rationale (typed, catchable via a common base class, actionable messages).
Keep this file free of imports from the rest of the package so every module
can raise these without risking a circular import.
"""

from __future__ import annotations


class MeetingPipelineError(Exception):
    """Base class for all errors raised by meeting_pipeline_2."""


class FFmpegNotFoundError(MeetingPipelineError):
    """Raised when the ffmpeg CLI is not available on PATH.

    TODO: port the per-OS install-instructions message from
    `meeting_pipeline/errors.py::FFmpegNotFoundError`.
    """


class FFmpegError(MeetingPipelineError):
    """Raised when ffmpeg runs but exits with a non-zero status."""


class VideoOpenError(MeetingPipelineError):
    """Raised when the video backend cannot open the source video file."""


class MissingDependencyError(MeetingPipelineError):
    """Raised when a required optional dependency (e.g. an OCR backend) is
    absent and no graceful degradation path applies."""


class ArtifactNotFoundError(MeetingPipelineError):
    """Raised when a stage's expected input artifact does not exist on disk."""

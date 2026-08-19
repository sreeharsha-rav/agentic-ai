"""meeting_pipeline: temporal multimodal meeting processing.

Transcribes a meeting recording, extracts slide/screen frames anchored to
speech, builds topic-level multimodal context (transcript + OCR), and aligns
meeting topics against reference documents.

Importing this package is cheap -- it does not import torch, opencv, or any
other heavy dependency. The four stage classes (``AudioTranscriber``,
``HybridExtractor``, ``MeetingContextBuilder``, ``DocumentAligner``) are
resolved lazily on first attribute access.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version
from typing import TYPE_CHECKING

from .config import (
    AlignmentConfig,
    ContextConfig,
    FrameExtractionConfig,
    OCRConfig,
    PipelineConfig,
    RuntimeConfig,
    TranscriptionConfig,
)
from .errors import (
    ArtifactNotFoundError,
    FFmpegError,
    FFmpegNotFoundError,
    MeetingPipelineError,
    MissingDependencyError,
    VideoOpenError,
)
from .pipeline import MeetingPipeline, PipelineResult, Stage, run_pipeline

try:
    __version__ = version("meeting-pipeline")
except PackageNotFoundError:  # pragma: no cover - not installed, e.g. running from source
    __version__ = "0.0.0+unknown"

if TYPE_CHECKING:
    from .audio_transcriber import AudioTranscriber
    from .context_builder import MeetingContextBuilder
    from .document_aligner import DocumentAligner
    from .hybrid_extractor import HybridExtractor

_LAZY_ATTRS = {
    "AudioTranscriber": (".audio_transcriber", "AudioTranscriber"),
    "HybridExtractor": (".hybrid_extractor", "HybridExtractor"),
    "MeetingContextBuilder": (".context_builder", "MeetingContextBuilder"),
    "DocumentAligner": (".document_aligner", "DocumentAligner"),
}


def __getattr__(name: str):
    try:
        module_name, attr_name = _LAZY_ATTRS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    import importlib

    module = importlib.import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value  # cache on the module so repeated access is instant
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_LAZY_ATTRS))


__all__ = [
    "MeetingPipeline",
    "run_pipeline",
    "PipelineResult",
    "Stage",
    "PipelineConfig",
    "TranscriptionConfig",
    "FrameExtractionConfig",
    "OCRConfig",
    "ContextConfig",
    "AlignmentConfig",
    "RuntimeConfig",
    "MeetingPipelineError",
    "FFmpegNotFoundError",
    "FFmpegError",
    "VideoOpenError",
    "MissingDependencyError",
    "ArtifactNotFoundError",
    "AudioTranscriber",
    "HybridExtractor",
    "MeetingContextBuilder",
    "DocumentAligner",
    "__version__",
]

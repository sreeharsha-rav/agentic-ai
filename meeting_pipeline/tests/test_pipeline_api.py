from __future__ import annotations

import inspect
import sys

import pytest

import meeting_pipeline as mp


def test_import_does_not_load_heavy_dependencies():
    assert "torch" not in sys.modules
    assert "cv2" not in sys.modules
    assert "sentence_transformers" not in sys.modules
    assert "faster_whisper" not in sys.modules


def test_public_api_surface_present():
    for name in (
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
        "__version__",
    ):
        assert name in mp.__all__
        assert hasattr(mp, name)


def test_stage_classes_are_lazily_resolvable():
    # Resolvable via __getattr__ without importing anything heavy at package
    # import time -- these imports do pull in cv2/faster_whisper/etc, but
    # only now, on first access, not when `import meeting_pipeline` ran.
    assert "AudioTranscriber" in mp.__all__
    assert "HybridExtractor" in mp.__all__
    assert "MeetingContextBuilder" in mp.__all__
    assert "DocumentAligner" in mp.__all__
    with pytest.raises(AttributeError):
        getattr(mp, "NotARealAttribute")


def test_meeting_pipeline_constructs_cheaply():
    pipeline = mp.MeetingPipeline(mp.PipelineConfig())
    assert isinstance(pipeline.config, mp.PipelineConfig)
    # Default construction (no config passed) works too.
    assert isinstance(mp.MeetingPipeline().config, mp.PipelineConfig)


def test_stage_enum_values():
    assert mp.Stage("context") is mp.Stage.CONTEXT
    assert mp.Stage("transcribe") is mp.Stage.TRANSCRIBE
    assert list(mp.Stage) == [mp.Stage.TRANSCRIBE, mp.Stage.FRAMES, mp.Stage.CONTEXT, mp.Stage.ALIGN]


def test_run_pipeline_signature():
    sig = inspect.signature(mp.run_pipeline)
    params = list(sig.parameters)
    assert params[:3] == ["video_path", "output_dir", "documents"]
    assert "config" in sig.parameters


def test_version_is_a_string():
    assert isinstance(mp.__version__, str)

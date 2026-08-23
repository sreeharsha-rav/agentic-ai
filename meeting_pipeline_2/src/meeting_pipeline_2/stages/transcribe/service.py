"""`WhisperTranscriber`: implements `core.interfaces.Transcriber`.

Port reference: `meeting_pipeline/audio_transcriber.py::AudioTranscriber.run()`.
Orchestrates `media.ffmpeg_runner.extract_audio()` (shared, not
transcribe-specific) and `whisper_backend.WhisperBackend.transcribe()`
(transcribe-specific), then writes the VTT file via
`text.timecodes.format_vtt_timestamp()`.
"""

from __future__ import annotations

from pathlib import Path

from ...config.schema import TranscriptionConfig
from ...core.interfaces import Transcriber
from ...core.models import ArtifactPaths
from ...media import ffmpeg_runner
from .whisper_backend import WhisperBackend


class WhisperTranscriber(Transcriber):
    """Default `Transcriber` implementation: ffmpeg + local faster-whisper.

    TODO: port the `run()` body from `AudioTranscriber.run()`:
      1. `ffmpeg_runner.extract_audio(video_path, paths.audio_path, ...)`.
      2. `self._backend.transcribe(paths.audio_path)`.
      3. Write `paths.transcript_path` as WEBVTT, one cue per segment, using
         `text.timecodes.format_vtt_timestamp()` for cue timestamps.
      4. Return `paths.transcript_path`.
    """

    def __init__(self, config: TranscriptionConfig) -> None:
        self.config = config
        self._backend = WhisperBackend(config)

    def run(self, video_path: Path, paths: ArtifactPaths) -> Path:
        raise NotImplementedError

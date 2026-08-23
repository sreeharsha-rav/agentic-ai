"""ffmpeg subprocess wrapper: video -> extracted audio WAV.

Port reference: `meeting_pipeline/audio_transcriber.py::extract_audio()`.
Factored out of the transcribe stage specifically because it's pure
"run an external process" logic with no dependency on Whisper or any
transcription concern -- isolating it here makes it independently testable
(mock `subprocess.run`) and reusable if a future stage ever needs audio
extraction without transcription.
"""

from __future__ import annotations

from pathlib import Path


def is_ffmpeg_available(ffmpeg_path: str = "ffmpeg") -> bool:
    """Check whether the ffmpeg CLI is reachable on PATH.

    TODO: port from the `shutil.which(...)` check in
    `audio_transcriber.py::extract_audio()`.
    """
    raise NotImplementedError


def extract_audio(
    video_path: Path,
    audio_path: Path,
    *,
    ffmpeg_path: str = "ffmpeg",
    audio_filter: str = "highpass=f=80,loudnorm",
    sample_rate: int = 16000,
    channels: int = 1,
) -> Path:
    """Extract mono PCM WAV audio from a video via ffmpeg.

    TODO: port from `audio_transcriber.py::extract_audio()`, including the
    filtered-extraction-with-fallback-to-basic-extraction behavior (some
    ffmpeg builds lack libebur128, needed by the loudnorm filter) and the
    idempotent early-return if `audio_path` already exists.

    Raises:
        FFmpegNotFoundError: if ffmpeg isn't on PATH.
        FFmpegError: if both the filtered and fallback extraction attempts fail.
    """
    raise NotImplementedError

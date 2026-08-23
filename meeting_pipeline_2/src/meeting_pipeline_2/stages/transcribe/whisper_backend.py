"""faster-whisper model wrapper: audio -> timestamped segments.

Port reference: `meeting_pipeline/audio_transcriber.py::_load_model()` and
`transcribe()`. Separated from `service.py` (which owns the
extract-then-transcribe-then-write-VTT orchestration) so the Whisper-specific
decoding parameters and lazy model loading are isolated from VTT
serialization -- a future alternative STT backend would implement the same
shape without touching VTT-writing logic.
"""

from __future__ import annotations

from pathlib import Path

from ...config.schema import TranscriptionConfig


class WhisperBackend:
    """Lazy-loaded faster-whisper model wrapper.

    TODO:
      - `__init__`: store config, set `self._model = None`.
      - `_load_model()`: lazy `from faster_whisper import WhisperModel`,
        construct with `model_size`/`device`/`compute_type`, cache on `self`.
      - `transcribe(audio_path)`: call `model.transcribe(...)` with the
        anti-hallucination settings from `TranscriptionConfig` (beam_size,
        temperature list, condition_on_previous_text=False,
        repetition_penalty), return the raw `(segments, info)` for
        `service.py` to serialize.
    """

    def __init__(self, config: TranscriptionConfig) -> None:
        self.config = config
        self._model = None

    def transcribe(self, audio_path: Path):
        raise NotImplementedError

"""WebVTT transcript parsing: captions -> merged same-speaker speech chunks.

Port reference: `meeting_pipeline/transcript.py::parse_vtt_chunks()` in full,
including the `<v Speaker>text</v>` voice-tag stripping regex and the
merge rule (same speaker + gap <= chunk_gap_seconds + duration <
max_chunk_duration_seconds).
"""

from __future__ import annotations

from pathlib import Path

from ..core.models import SpeechChunk


def parse_vtt_chunks(
    vtt_path: Path,
    *,
    chunk_gap_seconds: float = 5.0,
    max_chunk_duration_seconds: float = 30.0,
) -> list[SpeechChunk]:
    """Parse a WebVTT file into merged same-speaker speech chunks.

    TODO: port from `transcript.py::parse_vtt_chunks()`.
    """
    raise NotImplementedError

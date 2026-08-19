"""WebVTT transcript parsing: captions -> speech chunks.

Lifted out of ``HybridExtractor`` so it can be exercised in tests with only
``webvtt-py`` installed (no OpenCV/video required).
"""

from __future__ import annotations

import re

import webvtt

from .timecodes import parse_vtt_timestamp

_VOICE_TAG_RE = re.compile(r"<v\s+([^>]+)>(.*?)(?:</v>)?$", re.DOTALL)


def parse_vtt_chunks(
    vtt_path: str,
    chunk_gap_seconds: float = 5.0,
    max_chunk_duration_seconds: float = 30.0,
) -> list[dict]:
    """Parse a WebVTT file into merged same-speaker speech chunks.

    Consecutive captions from the same speaker are merged into one chunk as
    long as the gap between them stays under ``chunk_gap_seconds`` and the
    chunk's total duration stays under ``max_chunk_duration_seconds``. A
    speaker change, an over-long gap, or hitting the duration cap all force a
    new chunk to start.

    Captions using the WebVTT ``<v Speaker>text</v>`` voice tag have the tag
    stripped and ``speaker`` set accordingly; captions without a voice tag get
    ``speaker="Unknown"``.

    Returns a list of dicts with keys: ``transcript_start``, ``transcript_end``
    (``HH:MM:SS``, milliseconds stripped), ``start_sec``, ``end_sec``,
    ``speaker``, ``text``.
    """
    chunks: list[dict] = []
    current: dict | None = None

    for caption in webvtt.read(vtt_path):
        start_sec = parse_vtt_timestamp(caption.start)
        end_sec = parse_vtt_timestamp(caption.end)
        raw_text = caption.text.strip()

        speaker = "Unknown"
        text = raw_text
        match = _VOICE_TAG_RE.match(raw_text)
        if match:
            speaker = match.group(1).strip()
            text = match.group(2).strip()
        text = text.replace("\n", " ")

        if current is None:
            current = {
                "transcript_start": caption.start.split(".")[0],
                "transcript_end": caption.end.split(".")[0],
                "start_sec": start_sec,
                "end_sec": end_sec,
                "speaker": speaker,
                "text": text,
            }
            continue

        dur = current["end_sec"] - current["start_sec"]
        gap = start_sec - current["end_sec"]
        if speaker == current["speaker"] and gap <= chunk_gap_seconds and dur < max_chunk_duration_seconds:
            current["end_sec"] = end_sec
            current["transcript_end"] = caption.end.split(".")[0]
            current["text"] += " " + text
        else:
            chunks.append(current)
            current = {
                "transcript_start": caption.start.split(".")[0],
                "transcript_end": caption.end.split(".")[0],
                "start_sec": start_sec,
                "end_sec": end_sec,
                "speaker": speaker,
                "text": text,
            }

    if current is not None:
        chunks.append(current)
    return chunks

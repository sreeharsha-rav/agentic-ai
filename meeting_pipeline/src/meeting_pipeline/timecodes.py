"""Time-formatting helpers used across the pipeline.

The original implementation had three different, slightly incompatible time
formatters scattered across three files, all producing output that ends up
baked into filenames or persisted JSON fields. Their exact string output is
load-bearing (frame filenames, ``transcript_start``/``transcript_end`` fields,
WebVTT cues) and is preserved byte-for-byte here under precise names instead
of "fixing" them into one consistent format.
"""

from __future__ import annotations

import datetime


def format_vtt_timestamp(seconds: float) -> str:
    """``3661.5 -> "01:01:01.500"``. Used for WebVTT cue timestamps."""
    td = datetime.timedelta(seconds=seconds)
    total_seconds = int(td.total_seconds())
    millis = int((seconds - int(seconds)) * 1000)
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}.{millis:03d}"


def parse_vtt_timestamp(time_str: str) -> float:
    """``"00:01:23.500" -> 83.5``. Inverse of ``format_vtt_timestamp`` (approx)."""
    parts = time_str.split(":")
    return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])


def format_hms(seconds: float) -> str:
    """``83 -> "0:01:23"``. Unpadded hour, ``str(timedelta(...))`` formatting.

    Used for gap-scanner log messages and ``hybrid_enriched_log.json``'s
    ``start_time_format``/``end_time_format`` fields -- do not zero-pad the
    hour field, that would change the persisted JSON format.
    """
    td = datetime.timedelta(seconds=int(seconds))
    return str(td)


def format_clock(seconds: float) -> str:
    """``83 -> "01:23"``, ``3723 -> "01:02:03"``. Used for topic/segment display times.

    Returns ``"00:00"`` if ``seconds`` cannot be converted to a number.
    """
    try:
        s = int(float(seconds))
    except (TypeError, ValueError):
        return "00:00"
    m, sec = divmod(s, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"

"""Time-formatting helpers used across the pipeline.

Port reference: `meeting_pipeline/timecodes.py` in full. That module's
docstring explains why there are three near-but-not-quite-identical
formatters (`format_vtt_timestamp`, `format_hms`, `format_clock`) instead of
one -- their exact string output is load-bearing (filenames, persisted JSON
fields, WebVTT cues), so preserve each byte-for-byte rather than
consolidating them.
"""

from __future__ import annotations


def format_vtt_timestamp(seconds: float) -> str:
    """``3661.5 -> "01:01:01.500"``. TODO: port from `timecodes.py`."""
    raise NotImplementedError


def parse_vtt_timestamp(time_str: str) -> float:
    """``"00:01:23.500" -> 83.5``. TODO: port from `timecodes.py`."""
    raise NotImplementedError


def format_hms(seconds: float) -> str:
    """``83 -> "0:01:23"``. TODO: port from `timecodes.py`."""
    raise NotImplementedError


def format_clock(seconds: float) -> str:
    """``83 -> "01:23"``. TODO: port from `timecodes.py`."""
    raise NotImplementedError

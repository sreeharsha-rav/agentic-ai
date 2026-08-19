from __future__ import annotations

import pytest

from meeting_pipeline.timecodes import (
    format_clock,
    format_hms,
    format_vtt_timestamp,
    parse_vtt_timestamp,
)


def test_format_vtt_timestamp():
    assert format_vtt_timestamp(3661.5) == "01:01:01.500"
    assert format_vtt_timestamp(0.0) == "00:00:00.000"


def test_format_hms_unpadded_hour():
    # Unpadded hour is intentional -- this format is persisted into
    # hybrid_enriched_log.json's start_time_format/end_time_format fields.
    assert format_hms(83) == "0:01:23"
    assert format_hms(3600) == "1:00:00"


def test_format_clock():
    assert format_clock(83) == "01:23"
    assert format_clock(3723) == "01:02:03"
    assert format_clock("not-a-number") == "00:00"


def test_parse_vtt_timestamp():
    assert parse_vtt_timestamp("00:01:23.500") == pytest.approx(83.5)


def test_vtt_timestamp_roundtrip():
    # format_vtt_timestamp truncates (not rounds) to milliseconds, so up to
    # ~1ms of error is expected and acceptable here.
    for t in (0.0, 1.25, 83.5, 3661.5, 7325.999):
        parsed = parse_vtt_timestamp(format_vtt_timestamp(t))
        assert parsed == pytest.approx(t, abs=0.002)

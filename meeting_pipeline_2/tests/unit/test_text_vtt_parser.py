"""Unit tests for `text/vtt_parser.py`.

Port reference: `../../../meeting_pipeline/tests/test_transcript_parsing.py`
-- uses `tests/fixtures/sample_meeting.vtt`. Cases to port: same-speaker
captions merge within `chunk_gap_seconds`; a speaker change forces a new
chunk; exceeding `max_chunk_duration_seconds` forces a new chunk even for
the same speaker; `<v Speaker>` tags are stripped correctly; captions with
no voice tag get `speaker="Unknown"`.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="text/vtt_parser.py not yet implemented")
def test_same_speaker_captions_merge_within_gap():
    ...


@pytest.mark.skip(reason="text/vtt_parser.py not yet implemented")
def test_speaker_change_forces_new_chunk():
    ...


@pytest.mark.skip(reason="text/vtt_parser.py not yet implemented")
def test_duration_cap_forces_new_chunk():
    ...


@pytest.mark.skip(reason="text/vtt_parser.py not yet implemented")
def test_missing_voice_tag_yields_unknown_speaker():
    ...

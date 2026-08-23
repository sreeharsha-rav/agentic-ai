"""Unit tests for `stages/transcribe/service.py` (`WhisperTranscriber`).

Test against a fake `WhisperBackend`/`media.ffmpeg_runner` (monkeypatched or
injected) so no real ffmpeg binary or model download is required for the
default `pytest` run -- reserve a real end-to-end check for
`tests/integration/`, gated the same way
`../../../meeting_pipeline/tests/integration/` gates its slow tests
(`MEETING_PIPELINE_RUN_SLOW`/`MEETING_PIPELINE_TEST_VIDEO`-equivalent env vars).
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="stages/transcribe/service.py not yet implemented")
def test_run_writes_vtt_with_one_cue_per_segment():
    ...


@pytest.mark.skip(reason="stages/transcribe/service.py not yet implemented")
def test_run_raises_ffmpeg_not_found_when_ffmpeg_missing():
    ...

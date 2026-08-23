"""Integration tests: multiple stages (or the full `Pipeline`) chained together.

Port reference: `../../../meeting_pipeline/tests/integration/test_stage_chaining.py`
and `test_end_to_end.py`, including their env-var gating convention
(`MEETING_PIPELINE_RUN_SLOW` for stage-chaining with a real embedding model,
`MEETING_PIPELINE_TEST_VIDEO` for a full run against a real video). Mirror
that gating here under equivalent `MEETING_PIPELINE_2_*` env vars once these
are implemented, so CI can skip them by default the same way.

Prefer testing `pipeline.orchestrator.Pipeline` here with *real* stage
implementations (once they exist) against small fixtures -- unit tests
already cover `Pipeline`'s resume/stage-selection logic against fakes (see
a future tests/unit/pipeline/test_orchestrator.py), so this file's job is
verifying real stages actually chain correctly end to end.
"""

from __future__ import annotations

import os

import pytest

_RUN_SLOW = os.environ.get("MEETING_PIPELINE_2_RUN_SLOW") == "1"


@pytest.mark.integration
@pytest.mark.skipif(not _RUN_SLOW, reason="set MEETING_PIPELINE_2_RUN_SLOW=1 to run")
def test_transcribe_then_frames_then_context_chain_against_fixture():
    ...


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.skipif(
    "MEETING_PIPELINE_2_TEST_VIDEO" not in os.environ,
    reason="set MEETING_PIPELINE_2_TEST_VIDEO=/path/to/video.mp4 to run",
)
def test_full_pipeline_run_against_real_video():
    ...

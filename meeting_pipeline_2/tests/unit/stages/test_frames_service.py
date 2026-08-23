"""Unit tests for `stages/frames/` (audio_anchored / gap_scanner / dedup / service).

Port reference: `../../../meeting_pipeline/tests/test_frame_aligned_timeline.py`
for the overall shape -- test `audio_anchored.py`/`gap_scanner.py`/`dedup.py`
independently against a fake `VideoCapture` returning synthetic frames
(reuse `media/image_metrics.py`'s test patterns), before testing
`service.py`'s orchestration of all three.
"""

from __future__ import annotations

import pytest


@pytest.mark.skip(reason="stages/frames/audio_anchored.py not yet implemented")
def test_webcam_only_chunk_is_skipped_via_content_score():
    ...


@pytest.mark.skip(reason="stages/frames/gap_scanner.py not yet implemented")
def test_gap_scanning_covers_trailing_silence_to_video_end():
    ...


@pytest.mark.skip(reason="stages/frames/dedup.py not yet implemented")
def test_merge_dedup_passes_through_entry_with_no_linked_frame():
    ...

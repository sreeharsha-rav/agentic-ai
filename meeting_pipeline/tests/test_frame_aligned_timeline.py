from __future__ import annotations

from meeting_pipeline.config import OCRConfig
from meeting_pipeline.context_builder import MeetingContextBuilder


def _builder(tmp_path):
    # ocr_config disabled and frames_dir=None together guarantee no OCR
    # backend is ever imported; embeddings_enabled=False keeps this test
    # independent of sentence-transformers.
    return MeetingContextBuilder(
        output_dir=str(tmp_path),
        embeddings_enabled=False,
        ocr_config=OCRConfig(enabled=False),
    )


def test_frame_aligned_timeline_against_fixture(tmp_path, fixtures_dir):
    builder = _builder(tmp_path)
    log_path = str(fixtures_dir / "hybrid_enriched_log.sample.json")

    clean_timeline, gap_entries = builder.build_frame_aligned_timeline(log_path, frames_dir=None)

    # 2 gap entries returned separately, excluded from the timeline.
    assert len(gap_entries) == 2
    assert {g["frame_file"] for g in gap_entries} == {
        "frame_00_00_57_gap.png",
        "frame_00_01_02_gap.png",
    }

    # 6 raw audio entries in the fixture, but one has empty text and must be excluded.
    assert len(clean_timeline) == 5
    assert [s["segment_id"] for s in clean_timeline] == [
        "seg_000",
        "seg_001",
        "seg_002",
        "seg_003",
        "seg_004",
    ]

    # Sorted by start_sec regardless of the fixture's on-disk (jumbled) order.
    starts = [s["start_sec"] for s in clean_timeline]
    assert starts == sorted(starts)
    assert starts == [0.0, 5.0, 40.0, 45.0, 50.0]

    seg0, seg1, seg2, seg3, seg4 = clean_timeline

    # seg0: single frame, marked primary.
    assert seg0["frame_count"] == 1
    assert seg0["frames"][0]["file"] == "frame_00_00_02.png"
    assert seg0["frames"][0]["is_primary"] is True
    assert seg0["duration_sec"] == 5.0

    # seg1: frame_file is null -> no frames at all for this segment.
    assert seg1["frames"] == []
    assert seg1["frame_count"] == 0
    assert seg1["duration_sec"] == 12.34  # round(17.337 - 5.0, 2)

    # seg2: 3 frame_files, only the one matching frame_file is primary,
    # timestamps mapped positionally from frame_timestamps_sec.
    assert seg2["frame_count"] == 3
    assert [f["is_primary"] for f in seg2["frames"]] == [True, False, False]
    assert [f["timestamp_sec"] for f in seg2["frames"]] == [42.0, 43.0, 44.0]

    # seg3: normal single-frame segment.
    assert seg3["frame_count"] == 1

    # seg4: frame_files present but frame_timestamps_sec is absent entirely
    # -> falls back to [start_sec] for every listed frame.
    assert seg4["frame_count"] == 1
    assert seg4["frames"][0]["timestamp_sec"] == 50.0

    # With frames_dir=None, no OCR is attempted regardless of ocr_config.
    for seg in clean_timeline:
        for frame in seg["frames"]:
            assert frame["ocr_text"] == ""

from __future__ import annotations

from meeting_pipeline.config import OCRConfig
from meeting_pipeline.context_builder import MeetingContextBuilder


def _builder(tmp_path):
    return MeetingContextBuilder(
        output_dir=str(tmp_path),
        embeddings_enabled=False,
        ocr_config=OCRConfig(enabled=False),
    )


def _frame(file, ts, content, titles=None, details=None, ocr_text=None):
    return {
        "file": file,
        "timestamp_sec": ts,
        "ocr_text": ocr_text if ocr_text is not None else content,
        "spatial_titles": titles or [],
        "spatial_content": [content] if content else [],
        "spatial_details": details or [],
    }


def _segment(segment_id, start, end, speaker, transcript, frames):
    return {
        "segment_id": segment_id,
        "start_sec": float(start),
        "end_sec": float(end),
        "speaker": speaker,
        "transcript": transcript,
        "frames": frames,
    }


def test_boilerplate_token_stripped_and_primary_frame_is_earliest(tmp_path):
    frames = [
        _frame("f0.png", 1.0, "zoom recording started for the roadmap discussion"),
        _frame("f1.png", 2.0, "zoom session covered the pricing model updates"),
        _frame("f2.png", 3.0, "zoom call included budget planning notes today"),
        _frame("f3.png", 4.0, "zoom review touched on staffing timeline questions"),
        _frame("f4.png", 5.0, "zoom sync addressed vendor contract renewal details"),
    ]
    segment = _segment("seg_000", 0.0, 10.0, "Alice", "Discussed the roadmap in Zoom", frames)
    contexts = _builder(tmp_path).build_matchable_context([[segment]])

    assert len(contexts) == 1
    ctx = contexts[0]
    assert ctx["topic_id"] == "topic_000"
    # "zoom" appeared in 5/5 frames (> 0.65 default threshold) -> boilerplate, stripped.
    assert "zoom" not in " ".join(ctx["visual_texts"]).lower()
    assert "zoom" not in ctx["searchable_query"].lower()
    # Distinct remaining content per frame should survive (low pairwise overlap).
    assert len(ctx["visual_hierarchy"]["content"]) == 5
    # Earliest-timestamp frame (f0.png, ts=1.0) is primary, regardless of any
    # is_primary flag (none is even present on these synthetic frame dicts).
    assert ctx["primary_frame"] == "f0.png"


def test_boilerplate_filter_inactive_below_min_frames_threshold(tmp_path):
    # Only 3 frames, below the default min_frames_for_boilerplate=4 -- the
    # document-frequency filter must not activate even though "zoom" is in
    # every frame.
    frames = [
        _frame("f0.png", 1.0, "zoom recording started for the roadmap discussion"),
        _frame("f1.png", 2.0, "zoom session covered the pricing model updates"),
        _frame("f2.png", 3.0, "zoom call included budget planning notes today"),
    ]
    segment = _segment("seg_000", 0.0, 10.0, "Alice", "Discussed the roadmap in Zoom", frames)
    contexts = _builder(tmp_path).build_matchable_context([[segment]])
    assert "zoom" in " ".join(contexts[0]["visual_texts"]).lower()


def test_near_duplicate_content_lines_collapse_via_jaccard_dedup(tmp_path):
    frames = [
        _frame("f0.png", 1.0, "The team reviewed the system architecture diagram together"),
        _frame("f1.png", 2.0, "The team reviewed the system architecture diagram again together"),
    ]
    segment = _segment("seg_000", 0.0, 10.0, "Alice", "Architecture walkthrough", frames)
    contexts = _builder(tmp_path).build_matchable_context([[segment]])
    content = contexts[0]["visual_hierarchy"]["content"]
    assert len(content) == 1
    assert content[0] == "The team reviewed the system architecture diagram together"


def test_speakers_preserve_insertion_order_across_segments(tmp_path):
    seg_bob = _segment("seg_000", 0.0, 5.0, "Bob", "Bob speaks first", [])
    seg_alice = _segment("seg_001", 5.0, 10.0, "Alice", "Alice speaks second", [])
    contexts = _builder(tmp_path).build_matchable_context([[seg_bob, seg_alice]])
    assert contexts[0]["speakers"] == ["Bob", "Alice"]


def test_searchable_query_omits_visual_sections_when_no_frames(tmp_path):
    seg = _segment("seg_000", 0.0, 5.0, "Alice", "Just talking, nothing shown on screen", [])
    contexts = _builder(tmp_path).build_matchable_context([[seg]])
    query = contexts[0]["searchable_query"]
    assert "[VISUAL_TITLES]:" not in query
    assert "[VISUAL_CONTENT]:" not in query
    assert "Just talking" in query


DISTINCT_SENTENCES = [
    "Marketing reviewed quarterly campaign performance across three regions today",
    "Engineering discussed database migration timeline for the payments service",
    "Finance walked through the updated budget allocation for next quarter",
    "Design presented new onboarding flow mockups for mobile users",
    "Support team shared customer escalation trends from the past month",
    "Sales highlighted key wins from the enterprise renewal pipeline",
    "Operations reviewed warehouse capacity planning for the holiday season",
    "Legal summarized contract updates required for the new vendor",
    "Security outlined findings from the recent penetration testing round",
    "Data team presented dashboard improvements for churn analysis",
    "Product reviewed roadmap priorities for the upcoming release cycle",
    "HR discussed updated policies for remote work arrangements",
    "Infrastructure covered plans for the upcoming cloud migration project",
    "Analytics shared insights from the latest user behavior study",
    "Compliance reviewed audit findings from the external assessment",
    "Growth team discussed experiments planned for the next sprint",
]


def test_visual_content_capped_in_searchable_query_but_not_in_visual_hierarchy(tmp_path):
    assert len(DISTINCT_SENTENCES) == 16  # one more than max_visual_content_lines default (15)
    frames = [_frame(f"frame_{i}.png", float(i + 1), text) for i, text in enumerate(DISTINCT_SENTENCES)]
    segment = _segment("seg_000", 0.0, 60.0, "Alice", "Cross-team sync", frames)
    contexts = _builder(tmp_path).build_matchable_context([[segment]])
    ctx = contexts[0]

    # Full deduped list is kept in visual_hierarchy (not capped)...
    assert len(ctx["visual_hierarchy"]["content"]) == 16
    assert any("Growth team" in c for c in ctx["visual_hierarchy"]["content"])

    # ...but only the first 15 are embedded into the searchable_query string.
    assert "Growth team" not in ctx["searchable_query"]
    assert "Marketing reviewed" in ctx["searchable_query"]


def test_searchable_query_max_chars_is_respected(tmp_path):
    builder = MeetingContextBuilder(
        output_dir=str(tmp_path),
        embeddings_enabled=False,
        ocr_config=OCRConfig(enabled=False),
        searchable_query_max_chars=50,
    )
    long_transcript = "This is a very long transcript sentence. " * 20
    seg = _segment("seg_000", 0.0, 5.0, "Alice", long_transcript, [])
    contexts = builder.build_matchable_context([[seg]])
    assert len(contexts[0]["searchable_query"]) <= 50

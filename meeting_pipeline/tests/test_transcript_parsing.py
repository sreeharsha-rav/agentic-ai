from __future__ import annotations

from meeting_pipeline.transcript import parse_vtt_chunks


def test_parse_vtt_chunks_against_fixture(fixtures_dir):
    vtt_path = str(fixtures_dir / "sample_meeting.vtt")
    chunks = parse_vtt_chunks(vtt_path, chunk_gap_seconds=5.0, max_chunk_duration_seconds=30.0)

    # Cues 1+2: same speaker (Alice), gap of 0.5s <= 5.0s -> merged into one chunk.
    assert chunks[0]["speaker"] == "Alice"
    assert "architecture" in chunks[0]["text"]
    assert "Redis" in chunks[0]["text"]
    assert chunks[0]["transcript_start"] == "00:00:00"
    assert chunks[0]["transcript_end"] == "00:00:05"

    # Cue 3: different speaker (Bob) -> forces a split even though the gap is tiny.
    assert chunks[1]["speaker"] == "Bob"
    assert chunks[1]["text"] == "Can you go back to the previous slide?"

    # Cue 4: same speaker as chunk[0] (Alice) but the gap since chunk[1] (Bob)
    # ended is 40s, far over chunk_gap_seconds=5.0 -> new chunk, not merged
    # back into chunk[0].
    assert chunks[2]["speaker"] == "Alice"
    assert chunks[2]["text"] == "Sorry, this is where we cache the responses."

    # Cue 5: no <v> tag at all -> speaker defaults to "Unknown".
    assert chunks[3]["speaker"] == "Unknown"

    # Cues 6+7: same speaker (Bob), tiny gaps throughout, but cue 6 alone is a
    # ~30.3s monologue which already exceeds max_chunk_duration_seconds=30.0
    # by the time cue 7 arrives, so cue 7 must start a new chunk.
    assert chunks[4]["speaker"] == "Bob"
    assert "cross the maximum chunk duration threshold" in chunks[4]["text"]
    assert chunks[5]["speaker"] == "Bob"
    assert chunks[5]["text"] == "And that's the end of it."

    assert len(chunks) == 6


def test_parse_vtt_chunks_embedded_newlines_become_spaces(tmp_path):
    vtt_path = tmp_path / "newline.vtt"
    vtt_path.write_text(
        "WEBVTT\n\n1\n00:00:00.000 --> 00:00:02.000\n<v Alice>line one\nline two</v>\n",
        encoding="utf-8",
    )
    chunks = parse_vtt_chunks(str(vtt_path))
    assert chunks[0]["text"] == "line one line two"


def test_parse_vtt_chunks_empty_file(tmp_path):
    vtt_path = tmp_path / "empty.vtt"
    vtt_path.write_text("WEBVTT\n\n", encoding="utf-8")
    assert parse_vtt_chunks(str(vtt_path)) == []

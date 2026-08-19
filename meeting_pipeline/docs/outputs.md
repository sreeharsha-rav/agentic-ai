# Output File Reference

All paths below are relative to the `output_dir` passed to
`MeetingPipeline.run()` (or an individual stage method).

## `generated_transcript.vtt` (Step 0)

Standard WebVTT. Intermediate only -- nothing downstream reads this file
again after Step 1-3 parses it once.

```
WEBVTT

0
00:00:00.000 --> 00:00:02.400
Let's look at the architecture.
```

## `hybrid_enriched_log.json` (Steps 1-3)

A flat list of per-chunk (or per-gap) entries, sorted by `start_sec`.

```json
[
  {
    "source": "audio",
    "start_sec": 10.2,
    "end_sec": 18.7,
    "transcript_start": "00:00:10",
    "transcript_end": "00:00:18",
    "speaker": "Alice",
    "text": "Let's look at the architecture.",
    "frame_file": "frame_00_00_12.png",
    "frame_files": ["frame_00_00_12.png"],
    "frame_timestamps_sec": [12.0],
    "scene_count": 1,
    "content_frames_found": 1,
    "is_duplicate": false,
    "start_time_format": "0:00:10",
    "end_time_format": "0:00:18"
  },
  {
    "source": "gap",
    "start_sec": 45.0,
    "end_sec": 50.0,
    "transcript_start": "0:00:45",
    "transcript_end": "0:00:50",
    "speaker": null,
    "text": null,
    "frame_file": "frame_00_00_45_gap.png",
    "is_duplicate": false
  }
]
```

- `source`: `"audio"` (speech-chunk-anchored) or `"gap"` (silent-window scan).
- `frame_file`: primary frame for this entry (backward-compat single value);
  may be `null` if no content screen was detected during this chunk.
- `frame_files` / `frame_timestamps_sec`: all frames from this chunk (there
  can be more than one if an intra-chunk scene change was detected).
- `is_duplicate`: `true` if this entry's frame(s) were identified as visually
  identical to an earlier chunk's (linked, not re-saved).
- `start_time_format`/`end_time_format`: unpadded-hour `H:MM:SS` strings
  (added by the final merge/dedup pass), distinct in format from
  `transcript_start`/`transcript_end`.

## `meeting_timeline_clean.json` (Step 4)

```json
{
  "meta": {
    "total_segments": 42,
    "ocr_backend": "rapid",
    "embedding_used": true,
    "spatial_ocr_mode": "spatial_hierarchical"
  },
  "timeline": [
    {
      "segment_id": "seg_000",
      "start_sec": 10.2,
      "end_sec": 18.7,
      "start_time": "00:00:10",
      "end_time": "00:00:18",
      "duration_sec": 8.5,
      "speaker": "Alice",
      "transcript": "Let's look at the architecture.",
      "frames": [
        {
          "file": "frame_00_00_12.png",
          "timestamp_sec": 12.0,
          "timestamp": "00:12",
          "is_primary": true,
          "ocr_text": "System Architecture API Gateway Redis",
          "spatial_titles": ["System Architecture"],
          "spatial_content": ["API Gateway", "Redis"],
          "spatial_details": []
        }
      ],
      "frame_count": 1
    }
  ],
  "gap_visuals": ["... gap-sourced entries from hybrid_enriched_log.json, unchanged ..."]
}
```

## `meeting_context.json` (Step 4 -- input to Step 5)

A list of topic objects (one per clustered group of segments):

```json
[
  {
    "topic_id": "topic_003",
    "start_sec": 610.2,
    "end_sec": 682.4,
    "start_time": "10:10",
    "end_time": "11:22",
    "duration_sec": 72.2,
    "speakers": ["Alice"],
    "segment_ids": ["seg_014", "seg_015"],
    "segment_count": 2,
    "transcript_aggregated": "Alice: Let's look at the architecture. We use Redis for caching.",
    "visual_hierarchy": {
      "titles": ["System Architecture"],
      "content": ["API Gateway", "Redis Cache"],
      "details": []
    },
    "visual_texts": ["System Architecture", "API Gateway", "Redis Cache"],
    "keywords": ["redis cache", "api gateway"],
    "frames": ["... all unique frames across this topic's segments ..."],
    "frame_count": 3,
    "primary_frame": "frame_00_10_12.png",
    "searchable_query": "Alice: Let's look at the architecture...\n[VISUAL_TITLES]: System Architecture\n[VISUAL_CONTENT]: API Gateway | Redis Cache\n[KEYWORDS]: redis cache, api gateway"
  }
]
```

## `meeting_context_for_matching.jsonl` (Step 4)

One JSON object per line -- a slim index of the same topics, for lightweight
lookups without loading the full context file:

```json
{"topic_id": "topic_003", "start_sec": 610.2, "end_sec": 682.4, "searchable_query": "...", "frame_count": 3, "primary_frame": "frame_00_10_12.png"}
```

## `aligned_context_intermediate_detailed.json` (Step 5)

The full `meeting_context.json` topic list, each topic additionally carrying:

- `document_matches`: list of confirmed document-level matches (score >=
  `high_confidence_threshold`), each with `document`, `highest_confidence_score`,
  `global_document_score`, `combined_score`, `sections_matched`, `match_count`.
- `detailed_chunk_matches`: every individual chunk that cleared
  `similarity_threshold`, with a full `score_breakdown` (semantic/ocr_boost/keyword_boost)
  and a text preview -- useful for debugging why (or why not) a topic matched.

## `aligned_context.json` (Step 5 -- final deliverable)

One clean entry per topic:

```json
[
  {
    "topic_id": "topic_003",
    "start_time": "10:10",
    "end_time": "11:22",
    "duration_sec": 72.2,
    "speakers": ["Alice"],
    "transcript": "Alice: Let's look at the architecture. We use Redis for caching.",
    "primary_frame": "frame_00_10_12.png",
    "has_document_alignment": true,
    "primary_linked_document": "system_design.md",
    "highest_confidence_score": 0.61,
    "sections_matched": ["Architecture > Caching Layer"],
    "all_high_confidence_documents": ["... full document_matches list ..."]
  }
]
```

## `run_manifest.json` (written by `MeetingPipeline.run()`)

```json
{
  "output_dir": "./output/my_meeting",
  "audio_path": "./output/my_meeting/extracted_audio.wav",
  "transcript_path": "./output/my_meeting/generated_transcript.vtt",
  "frames_dir": "./output/my_meeting/video/hybrid",
  "hybrid_log_path": "./output/my_meeting/hybrid_enriched_log.json",
  "timeline_path": "./output/my_meeting/meeting_timeline_clean.json",
  "context_path": "./output/my_meeting/meeting_context.json",
  "context_jsonl_path": "./output/my_meeting/meeting_context_for_matching.jsonl",
  "aligned_path": "./output/my_meeting/aligned_context.json",
  "aligned_detailed_path": "./output/my_meeting/aligned_context_intermediate_detailed.json",
  "segment_count": 42,
  "topic_count": 9,
  "frame_count": 27,
  "aligned_topic_count": 6,
  "stages_run": ["transcribe", "frames", "context", "align"],
  "stages_skipped": [],
  "stage_seconds": {"transcribe": 12.3, "frames": 45.1, "context": 8.7, "align": 3.2},
  "config": ["... the exact PipelineConfig used for this run, as a dict ..."]
}
```

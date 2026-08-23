"""Resolves the fixed on-disk artifact layout for one pipeline run.

Port reference: the path-construction block at the top of
`meeting_pipeline/pipeline.py::MeetingPipeline.run()` (lines computing
`transcript_path`, `audio_path`, `frames_dir`, `hybrid_log_path`, etc. from
`output_dir`). Pulling this out of the orchestrator and into its own module
means both `pipeline/orchestrator.py` and any stage's standalone/CLI
invocation resolve paths identically, from one source of truth.
"""

from __future__ import annotations

from pathlib import Path

from ..core.models import ArtifactPaths


def resolve_artifact_paths(output_dir: Path) -> ArtifactPaths:
    """Compute every artifact's path under `output_dir`, without creating
    any of them.

    TODO: port the exact filenames from `pipeline.py::MeetingPipeline.run()`:
      - extracted_audio.wav
      - generated_transcript.vtt
      - video/hybrid/  (+ hybrid_enriched_log.json)
      - meeting_context.json  (+ meeting_timeline_clean.json,
        meeting_context_for_matching.jsonl)
      - aligned_context.json  (+ aligned_context_intermediate_detailed.json)
    """
    raise NotImplementedError

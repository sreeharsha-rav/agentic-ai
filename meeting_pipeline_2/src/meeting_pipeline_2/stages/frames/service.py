"""`HybridFrameExtractor`: implements `core.interfaces.FrameExtractor`.

Port reference: `meeting_pipeline/hybrid_extractor.py::HybridExtractor.run()`.
Orchestrates `text.vtt_parser.parse_vtt_chunks()` (shared) +
`audio_anchored.py` + `gap_scanner.py` + `dedup.py` (this stage's own
algorithm modules), writing the unified frame log via `storage.json_store`.
"""

from __future__ import annotations

from pathlib import Path

from ...config.schema import FrameExtractionConfig
from ...core.interfaces import FrameExtractor
from ...core.models import ArtifactPaths
from ...media.video_capture import VideoCapture
from ...text.vtt_parser import parse_vtt_chunks
from . import audio_anchored, dedup, gap_scanner


class HybridFrameExtractor(FrameExtractor):
    """Default `FrameExtractor` implementation: audio-anchored sampling +
    silent-gap scanning + 3-layer SSIM dedup.

    TODO: port the `run()` body from `HybridExtractor.run()`:
      1. `parse_vtt_chunks(transcript_path, ...)`.
      2. Open `VideoCapture(video_path)` (raises `VideoOpenError`).
      3. `audio_anchored.extract_audio_anchored(...)`.
      4. `gap_scanner.compute_silent_gaps(...)` + `scan_gaps(...)`
         (gap scanning spans to `cap.duration_sec`, not the last chunk's end).
      5. `dedup.merge_and_dedup(...)`.
      6. Write `paths.frame_log_path` via `storage.json_store.write_json()`.
    """

    def __init__(self, config: FrameExtractionConfig) -> None:
        self.config = config

    def run(self, video_path: Path, transcript_path: Path, paths: ArtifactPaths) -> Path:
        raise NotImplementedError

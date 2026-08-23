"""Final merge + dedup: interleave audio-anchored and gap-scanned frames
chronologically, then remove residual near-duplicates via SSIM.

Port reference: `meeting_pipeline/hybrid_extractor.py::_merge_and_dedup()`.
This is the third of the three dedup layers described in
../../../../meeting_pipeline/docs/frames_stage.md section 8 -- kept as its
own module because "merge two independently-produced lists and remove
cross-source duplicates" is a distinct concern from either extraction pass.
"""

from __future__ import annotations

from pathlib import Path

from ...core.models import FrameLogEntry


def merge_and_dedup(
    audio_frames: list[FrameLogEntry],
    gap_frames: list[FrameLogEntry],
    frames_dir: Path,
    *,
    ssim_threshold: float,
    delete_deduped_frames: bool = False,
) -> list[FrameLogEntry]:
    """Sort by start time, drop any entry whose linked frame is a
    near-duplicate (SSIM > threshold) of the previous kept entry's frame.

    TODO: port from `hybrid_extractor.py::_merge_and_dedup()`, including
    passing through entries with no linked frame at all unchanged (rather
    than crashing on a `None` path -- see ../meeting_pipeline/CHANGELOG.md).
    """
    raise NotImplementedError
